import os

import httpx

from aegis.schemas import AdjudicationDecision, StateVerificationResult


class SlackAuditTool:
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
        self.webhook_url = os.getenv("SLACK_WEBHOOK_URL")
        self.client = client or httpx.Client(timeout=15.0)
        self.dispatched_messages: list[dict] = []

    def post_adjudication_audit(
        self,
        decision: AdjudicationDecision,
        verification: StateVerificationResult,
    ) -> dict:
        badge = "VERIFIED" if verification.verified else "VERIFICATION FAILED"
        payload = {
            "text": f"Adjudication audit for {decision.claim_id}: {badge}",
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "AegisClaim Adjudication Audit"},
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Claim ID*\n{decision.claim_id}"},
                        {"type": "mrkdwn", "text": f"*Decision*\n{'Approved' if decision.approved else 'Denied'}"},
                        {"type": "mrkdwn", "text": f"*Policy*\n{decision.policy_reference}"},
                        {"type": "mrkdwn", "text": f"*Financial status*\n{verification.observed_state}"},
                    ],
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Verbatim evidence*\n> {decision.exact_evidence_quote}",
                    },
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"*State verification:* {badge} | Expected `{verification.expected_state}`",
                        }
                    ],
                },
            ],
        }
        return self._dispatch(payload)

    def post_escalation_alert(self, claim_id: str, issue_reason: str) -> dict:
        payload = {
            "channel": "#compliance-escalations",
            "text": f"HIGH PRIORITY compliance escalation for {claim_id}",
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "HIGH PRIORITY: Compliance Escalation"},
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Claim ID*\n{claim_id}"},
                        {"type": "mrkdwn", "text": f"*Issue*\n{issue_reason}"},
                    ],
                },
            ],
        }
        return self._dispatch(payload)

    def _dispatch(self, payload: dict) -> dict:
        if self.twin_mode:
            self.dispatched_messages.append(payload)
            return payload
        if not self.webhook_url:
            raise ValueError("SLACK_WEBHOOK_URL is required when TWIN_MODE=false")
        response = self.client.post(self.webhook_url, json=payload)
        response.raise_for_status()
        if response.content:
            try:
                return response.json()
            except ValueError:
                pass
        return {"ok": True, "status_code": response.status_code, "payload": payload}
