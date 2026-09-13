import re
from typing import Any

from pydantic import ValidationError

from aegis.guardrail import (
    ArgaStateDivergenceError,
    LemmaGuardrail,
    LemmaPlaceholderViolation,
    LemmaUngroundedEvidenceError,
)
from aegis.schemas import AdjudicationDecision, ClaimDisputeInput
from aegis.tools import GitHubPolicyTool, SlackAuditTool, StripeLedgerTool


class AegisAdjudicator:
    def __init__(
        self,
        github_tool: GitHubPolicyTool | None = None,
        stripe_tool: StripeLedgerTool | None = None,
        slack_tool: SlackAuditTool | None = None,
    ) -> None:
        self.github_tool = github_tool or GitHubPolicyTool(twin_mode=True)
        self.stripe_tool = stripe_tool or StripeLedgerTool(twin_mode=True)
        self.slack_tool = slack_tool or SlackAuditTool(twin_mode=True)
        self.guardrail = LemmaGuardrail()

    def adjudicate_claim(self, claim_input: dict) -> dict:
        claim_id = str(claim_input.get("claim_id", "invalid-claim-id"))
        try:
            claim = ClaimDisputeInput.model_validate(claim_input)
            self.guardrail.validate_claim_integrity(claim)
        except (ValidationError, LemmaPlaceholderViolation) as exc:
            return self._escalation_failure(claim_id, "pre_action_guard", str(exc))

        policy_text = self.github_tool.fetch_policy(claim.cpt_code)
        policy_sha = self.github_tool.get_policy_commit_sha()
        criteria = self._evaluate_coverage(claim)
        evidence_quote = claim.clinical_notes.strip()
        try:
            self.guardrail.verify_clinical_grounding(
                evidence_quote,
                claim.clinical_notes,
                policy_text,
            )
        except LemmaUngroundedEvidenceError as exc:
            return self._escalation_failure(claim.claim_id, "grounding_check", str(exc))

        approved = all(criteria.values())
        missing_criteria = [name for name, met in criteria.items() if not met]
        confidence_score = 0.98 if approved else 0.90
        requires_escalation = not self.guardrail.audit_confidence_threshold(confidence_score)
        rationale = (
            "All CMS TAVR coverage criteria are satisfied."
            if approved
            else f"CMS TAVR coverage criteria not satisfied: {', '.join(missing_criteria)}."
        )
        decision = AdjudicationDecision(
            claim_id=claim.claim_id,
            patient_id=claim.patient_id,
            approved=approved,
            authorized_amount=claim.claimed_amount if approved else 0.0,
            rationale=rationale,
            exact_evidence_quote=evidence_quote,
            confidence_score=confidence_score,
            policy_reference=policy_sha,
            requires_human_escalation=requires_escalation,
        )

        if requires_escalation:
            return self._escalation_failure(
                claim.claim_id,
                "confidence_guard",
                f"Confidence {confidence_score:.2f} is below the automated action threshold",
                decision=decision,
            )

        if approved:
            mutation = self.stripe_tool.release_claim_payout(
                claim.claim_id,
                claim.claimed_amount,
            )
            expected_status = "settled_approved"
        else:
            mutation = self.stripe_tool.reject_claim(claim.claim_id, rationale)
            expected_status = "denied_closed"

        verification = self.stripe_tool.verify_state(claim.claim_id, expected_status)
        if not verification.verified:
            error = ArgaStateDivergenceError(
                f"[Arga State Divergence] Expected {expected_status!r}, observed {verification.observed_state!r}"
            )
            dispatch = self.slack_tool.post_escalation_alert(claim.claim_id, str(error))
            return {
                "status": "failed",
                "stage": "state_verification",
                "error": str(error),
                "decision": decision.model_dump(),
                "mutation": mutation,
                "verification": verification.model_dump(),
                "dispatch": dispatch,
            }

        dispatch = self.slack_tool.post_adjudication_audit(decision, verification)
        return {
            "status": "completed",
            "stage": "audit_dispatch",
            "decision": decision.model_dump(),
            "mutation": mutation,
            "verification": verification.model_dump(),
            "dispatch": dispatch,
        }

    def _evaluate_coverage(self, claim: ClaimDisputeInput) -> dict[str, bool]:
        notes = claim.clinical_notes
        normalized_cpt = claim.cpt_code.upper().removeprefix("CPT-")
        indication = all(
            term in notes.lower()
            for term in ("severe", "symptomatic", "aortic stenosis")
        )
        nyha = bool(re.search(r"\bNYHA(?:\s+CLASS)?\s+(?:II|III|IV)\b", notes, re.IGNORECASE))
        gradient_values = [
            float(value)
            for value in re.findall(
                r"(?:mean\s+)?(?:aortic\s+)?gradient[^\d]{0,20}(\d+(?:\.\d+)?)\s*mmhg",
                notes,
                re.IGNORECASE,
            )
        ]
        valve_areas = [
            float(value)
            for value in re.findall(
                r"valve\s+area[^\d]{0,20}(\d+(?:\.\d+)?)\s*(?:cm2|cm\^2|cm²)",
                notes,
                re.IGNORECASE,
            )
        ]
        heart_team = bool(
            re.search(
                r"heart\s+team.{0,40}(?:sign[ -]?off|signed\s+off|approv|consensus)",
                notes,
                re.IGNORECASE,
            )
        )
        return {
            "CPT-33361": normalized_cpt == "33361",
            "ICD-10 I35.0": claim.icd10_code.upper() == "I35.0",
            "severe symptomatic aortic stenosis": indication,
            "NYHA Class II-IV symptoms": nyha,
            "hemodynamic threshold": any(value >= 40.0 for value in gradient_values)
            or any(value <= 1.0 for value in valve_areas),
            "multidisciplinary heart team sign-off": heart_team,
        }

    def _escalation_failure(
        self,
        claim_id: str,
        stage: str,
        reason: str,
        decision: AdjudicationDecision | None = None,
    ) -> dict[str, Any]:
        dispatch = self.slack_tool.post_escalation_alert(claim_id, reason)
        return {
            "status": "escalated",
            "stage": stage,
            "error": reason,
            "decision": decision.model_dump() if decision else None,
            "mutation": None,
            "verification": None,
            "dispatch": dispatch,
        }
