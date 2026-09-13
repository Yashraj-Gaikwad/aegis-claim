from copy import deepcopy

import pytest

from aegis.guardrail import LemmaGuardrail, LemmaUngroundedEvidenceError
from aegis.orchestrator import AegisAdjudicator
from aegis.tools import GitHubPolicyTool, SlackAuditTool, StripeLedgerTool


def valid_claim() -> dict:
    return {
        "claim_id": "CLM-1092",
        "patient_id": "PAT-9841",
        "icd10_code": "I35.0",
        "cpt_code": "33361",
        "claimed_amount": 14500.0,
        "clinical_notes": (
            "The 74-year-old patient has severe symptomatic aortic stenosis with NYHA Class III "
            "heart failure symptoms. Echocardiography documents a valve area of 0.7 cm2 and a "
            "mean aortic gradient of 46 mmHg. The multidisciplinary heart team signed off on TAVR."
        ),
    }


def twin_adjudicator() -> tuple[AegisAdjudicator, StripeLedgerTool, SlackAuditTool]:
    stripe = StripeLedgerTool(twin_mode=True)
    slack = SlackAuditTool(twin_mode=True)
    adjudicator = AegisAdjudicator(
        github_tool=GitHubPolicyTool(twin_mode=True),
        stripe_tool=stripe,
        slack_tool=slack,
    )
    return adjudicator, stripe, slack


def test_nominal_adjudication_success() -> None:
    adjudicator, stripe, slack = twin_adjudicator()
    claim = valid_claim()

    result = adjudicator.adjudicate_claim(claim)

    assert result["status"] == "completed"
    assert result["decision"]["approved"] is True
    assert result["decision"]["exact_evidence_quote"] in claim["clinical_notes"]
    assert stripe.claims[claim["claim_id"]]["status"] == "settled_approved"
    assert result["verification"]["verified"] is True
    assert result["verification"]["observed_state"] == "settled_approved"
    assert result["idempotency_key"] in stripe.idempotency_keys
    cached_result = stripe.release_claim_payout(
        claim["claim_id"],
        claim["claimed_amount"],
        idempotency_key=result["idempotency_key"],
    )
    assert cached_result == result["mutation"]
    assert len(stripe.idempotency_keys) == 1
    assert len(slack.dispatched_messages) == 1
    audit_payload = slack.dispatched_messages[0]
    assert result["decision"]["policy_reference"] == "sha_c9f482a"
    assert "sha_c9f482a" in str(audit_payload)
    assert "VERIFIED" in str(audit_payload)


@pytest.mark.parametrize(
    ("field_name", "placeholder"),
    [("patient_id", "unknown"), ("claim_id", "TBD")],
)
def test_lemma_silent_failure_prevention(field_name: str, placeholder: str) -> None:
    adjudicator, stripe, slack = twin_adjudicator()
    initial_ledger = deepcopy(stripe.claims)
    claim = {**valid_claim(), field_name: placeholder}

    result = adjudicator.adjudicate_claim(claim)

    assert result["status"] == "escalated"
    assert result["stage"] == "pre_action_guard"
    assert "[Lemma Safety Violation]" in result["error"]
    assert result["mutation"] is None
    assert stripe.claims == initial_ledger
    assert len(slack.dispatched_messages) == 1
    escalation = slack.dispatched_messages[0]
    assert escalation["channel"] == "#compliance-escalations"
    assert "HIGH PRIORITY" in str(escalation)


def test_ungrounded_evidence_rejection(monkeypatch: pytest.MonkeyPatch) -> None:
    guardrail = LemmaGuardrail()
    fabricated_quote = "The heart team unanimously approved a fabricated surgical finding."
    clinical_notes = valid_claim()["clinical_notes"]
    policy_text = GitHubPolicyTool(twin_mode=True).fetch_policy("33361")

    with pytest.raises(LemmaUngroundedEvidenceError, match="not verbatim-grounded"):
        guardrail.verify_clinical_grounding(
            fabricated_quote,
            clinical_notes,
            policy_text,
        )

    adjudicator, stripe, slack = twin_adjudicator()
    initial_ledger = deepcopy(stripe.claims)

    def reject_fabricated_evidence(*args: str) -> bool:
        raise LemmaUngroundedEvidenceError(
            "[Lemma Safety Violation] Evidence quote is not verbatim-grounded in clinical notes or policy"
        )

    monkeypatch.setattr(
        adjudicator.guardrail,
        "verify_clinical_grounding",
        reject_fabricated_evidence,
    )
    result = adjudicator.adjudicate_claim(valid_claim())

    assert result["status"] == "escalated"
    assert result["stage"] == "grounding_check"
    assert result["mutation"] is None
    assert stripe.claims == initial_ledger
    assert slack.dispatched_messages[0]["channel"] == "#compliance-escalations"


def test_clinical_criteria_denial() -> None:
    adjudicator, stripe, slack = twin_adjudicator()
    claim = {
        **valid_claim(),
        "clinical_notes": (
            "The patient has asymptomatic aortic stenosis, NYHA Class I symptoms, a valve area "
            "of 1.8 cm2, and a mean aortic gradient of 22 mmHg. The multidisciplinary heart team "
            "signed off after review."
        ),
    }

    result = adjudicator.adjudicate_claim(claim)

    assert result["status"] == "completed"
    assert result["decision"]["approved"] is False
    assert result["decision"]["authorized_amount"] == 0.0
    assert stripe.claims[claim["claim_id"]]["status"] == "denied_closed"
    assert result["verification"]["expected_state"] == "denied_closed"
    assert result["verification"]["observed_state"] == "denied_closed"
    assert result["verification"]["verified"] is True
    assert "VERIFIED" in str(slack.dispatched_messages[0])


def test_arga_state_divergence_detection() -> None:
    class StaleStripeTwin(StripeLedgerTool):
        def release_claim_payout(
            self,
            claim_id: str,
            amount: float,
            idempotency_key: str | None = None,
        ) -> dict:
            self._last_action = "release_claim_payout"
            return deepcopy(self.claims[claim_id])

    stripe = StaleStripeTwin(twin_mode=True)
    slack = SlackAuditTool(twin_mode=True)
    adjudicator = AegisAdjudicator(
        github_tool=GitHubPolicyTool(twin_mode=True),
        stripe_tool=stripe,
        slack_tool=slack,
    )

    result = adjudicator.adjudicate_claim(valid_claim())

    assert result["status"] == "compensated_rolled_back"
    assert result["stage"] == "state_verification"
    assert result["verification"]["verified"] is False
    assert result["verification"]["expected_state"] == "settled_approved"
    assert result["verification"]["observed_state"] == "on_hold"
    assert "[Arga State Divergence]" in result["error"]
    assert stripe.claims["CLM-1092"]["status"] == "on_hold_frozen"
    assert result["compensation"]["status"] == "on_hold_frozen"
    assert len(slack.dispatched_messages) == 1
    emergency_alert = slack.dispatched_messages[0]
    assert emergency_alert["channel"] == "#compliance-escalations"
    assert "CRITICAL Saga compensation executed" in str(emergency_alert)


def test_saga_compensating_rollback_on_divergence() -> None:
    class AuditFailureSlackTwin(SlackAuditTool):
        def post_adjudication_audit(self, decision: object, verification: object) -> dict:
            raise RuntimeError("Injected downstream audit dispatch failure")

    stripe = StripeLedgerTool(twin_mode=True)
    slack = AuditFailureSlackTwin(twin_mode=True)
    adjudicator = AegisAdjudicator(
        github_tool=GitHubPolicyTool(twin_mode=True),
        stripe_tool=stripe,
        slack_tool=slack,
    )

    result = adjudicator.adjudicate_claim(valid_claim())

    assert result["status"] == "compensated_rolled_back"
    assert result["stage"] == "audit_dispatch"
    assert result["mutation"]["status"] == "settled_approved"
    assert stripe.claims["CLM-1092"]["status"] == "on_hold_frozen"
    assert result["compensation"]["status"] == "on_hold_frozen"
    compensation_event = stripe.claims["CLM-1092"]["audit_record"][-1]
    assert compensation_event["event"] == "saga_compensation"
    assert compensation_event["from_status"] == "settled_approved"
    assert compensation_event["to_status"] == "on_hold_frozen"
    assert result["verification"]["verified"] is True
    assert slack.dispatched_messages[0]["channel"] == "#compliance-escalations"
