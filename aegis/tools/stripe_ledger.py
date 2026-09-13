import os
from copy import deepcopy

import httpx

from aegis.schemas import StateVerificationResult


class StripeLedgerTool:
    def __init__(
        self,
        twin_mode: bool | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.twin_mode = (
            os.getenv("TWIN_MODE", "true").strip().lower() == "true"
            if twin_mode is None
            else twin_mode
        )
        self.secret_key = os.getenv("STRIPE_SECRET_KEY")
        self.client = client or httpx.Client(timeout=15.0)
        self.claims: dict[str, dict] = {
            "CLM-1092": {
                "claim_id": "CLM-1092",
                "status": "on_hold",
                "amount": 14500.00,
                "patient_id": "PAT-9841",
                "disbursed_amount": 0.0,
            }
        }
        self._last_action = "read_state"

    def place_hold(self, claim_id: str, amount: float) -> dict:
        self._last_action = "place_hold"
        if self.twin_mode:
            claim = self.claims.setdefault(claim_id, {"claim_id": claim_id})
            claim.update(status="on_hold", amount=amount, disbursed_amount=0.0)
            return deepcopy(claim)
        return self._update_live_claim(
            claim_id,
            {"metadata[aegis_status]": "on_hold", "metadata[claim_amount]": str(amount)},
        )

    def release_claim_payout(self, claim_id: str, amount: float) -> dict:
        self._last_action = "release_claim_payout"
        if self.twin_mode:
            claim = self._get_twin_claim(claim_id)
            claim.update(status="settled_approved", disbursed_amount=amount)
            return deepcopy(claim)
        return self._update_live_claim(
            claim_id,
            {
                "metadata[aegis_status]": "settled_approved",
                "metadata[disbursed_amount]": str(amount),
            },
        )

    def reject_claim(self, claim_id: str, reason: str) -> dict:
        self._last_action = "reject_claim"
        if self.twin_mode:
            claim = self._get_twin_claim(claim_id)
            claim.update(status="denied_closed", denial_reason=reason)
            return deepcopy(claim)
        return self._update_live_claim(
            claim_id,
            {"metadata[aegis_status]": "denied_closed", "metadata[denial_reason]": reason},
        )

    def verify_state(self, claim_id: str, expected_status: str) -> StateVerificationResult:
        if self.twin_mode:
            observed_status = self._get_twin_claim(claim_id)["status"]
        else:
            response = self.client.get(
                self._payment_intent_url(claim_id), headers=self._headers()
            )
            response.raise_for_status()
            observed_status = response.json().get("metadata", {}).get("aegis_status", "")
        return StateVerificationResult(
            service="stripe",
            action=self._last_action,
            expected_state=expected_status,
            observed_state=observed_status,
            verified=observed_status == expected_status,
        )

    def _get_twin_claim(self, claim_id: str) -> dict:
        if claim_id not in self.claims:
            raise KeyError(f"Claim not found: {claim_id}")
        return self.claims[claim_id]

    def _update_live_claim(self, claim_id: str, data: dict[str, str]) -> dict:
        response = self.client.post(
            self._payment_intent_url(claim_id), headers=self._headers(), data=data
        )
        response.raise_for_status()
        return response.json()

    def _payment_intent_url(self, claim_id: str) -> str:
        return f"https://api.stripe.com/v1/payment_intents/{claim_id}"

    def _headers(self) -> dict[str, str]:
        if not self.secret_key:
            raise ValueError("STRIPE_SECRET_KEY is required when TWIN_MODE=false")
        return {"Authorization": f"Bearer {self.secret_key}"}
