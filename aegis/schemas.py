from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ClaimDisputeInput(BaseModel):
    model_config = ConfigDict(strict=True)

    claim_id: str
    patient_id: str
    icd10_code: str
    cpt_code: str
    claimed_amount: float
    clinical_notes: str

    forbidden_placeholders: ClassVar[set[str]] = {
        "unknown",
        "n/a",
        "none",
        "placeholder",
        "tbd",
        "pending",
        "undefined",
    }

    @field_validator("claim_id", "patient_id", "icd10_code", "cpt_code")
    @classmethod
    def reject_placeholder_identifiers(cls, value: str) -> str:
        if value.strip().lower() in cls.forbidden_placeholders:
            raise ValueError(
                f"[Lemma Safety Violation] Placeholder identifier or code is forbidden: {value!r}"
            )
        return value


class AdjudicationDecision(BaseModel):
    model_config = ConfigDict(strict=True)

    claim_id: str
    patient_id: str
    approved: bool
    authorized_amount: float
    rationale: str
    exact_evidence_quote: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    policy_reference: str
    requires_human_escalation: bool


class StateVerificationResult(BaseModel):
    model_config = ConfigDict(strict=True)

    service: str
    action: str
    expected_state: str
    observed_state: str
    verified: bool
