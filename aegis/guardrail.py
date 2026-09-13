from aegis.schemas import ClaimDisputeInput


class LemmaPlaceholderViolation(Exception):
    pass


class LemmaUngroundedEvidenceError(Exception):
    pass


class ArgaStateDivergenceError(Exception):
    pass


class LemmaGuardrail:
    forbidden_placeholders = {
        "unknown",
        "n/a",
        "none",
        "placeholder",
        "tbd",
        "pending",
        "undefined",
    }

    def validate_claim_integrity(self, claim: ClaimDisputeInput) -> None:
        for field_name in ("claim_id", "patient_id", "icd10_code", "cpt_code"):
            value = getattr(claim, field_name)
            normalized = value.strip().lower()
            if any(token in normalized for token in self.forbidden_placeholders):
                raise LemmaPlaceholderViolation(
                    f"[Lemma Safety Violation] {field_name} contains a forbidden placeholder: {value!r}"
                )

    def verify_clinical_grounding(
        self,
        evidence_quote: str,
        clinical_notes: str,
        policy_text: str,
    ) -> bool:
        quote = evidence_quote.strip()
        if len(quote) < 12 or quote.lower() in self.forbidden_placeholders:
            raise LemmaUngroundedEvidenceError(
                "[Lemma Safety Violation] Evidence quote is empty, trivial, or synthetic"
            )
        if quote not in clinical_notes and quote not in policy_text:
            raise LemmaUngroundedEvidenceError(
                "[Lemma Safety Violation] Evidence quote is not verbatim-grounded in clinical notes or policy"
            )
        return True

    def audit_confidence_threshold(
        self,
        confidence_score: float,
        threshold: float = 0.75,
    ) -> bool:
        return confidence_score >= threshold
