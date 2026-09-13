import os
from html import escape
from pathlib import Path

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

    def render_html_audit_card(
        self,
        decision: dict,
        verification: dict,
        filename: str = "audit_artifact.html",
    ) -> str:
        claim_id = escape(str(decision["claim_id"]))
        patient_id = escape(str(decision["patient_id"]))
        evidence = escape(str(decision["exact_evidence_quote"]))
        policy_reference = escape(str(decision["policy_reference"]))
        expected_state = escape(str(verification["expected_state"]))
        observed_state = escape(str(verification["observed_state"]))
        verified = verification.get("verified") is True
        authorized_amount = float(decision.get("authorized_amount", 0.0))
        badge = "[ARGA VERIFIED]" if verified else "[ARGA DIVERGENCE]"
        badge_class = "verified" if verified else "divergent"
        match_indicator = "100% MATCH" if verified else "STATE MISMATCH"
        artifact_path = Path(__file__).resolve().parents[2] / Path(filename).name
        document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AegisClaim Clinical-Financial Audit Trail</title>
  <style>
    :root {{ color-scheme: dark; --bg: #070b14; --panel: #101827; --line: #26344d; --text: #eef5ff; --muted: #96a7c0; --cyan: #4dd8ff; --green: #3ce6a0; --red: #ff6680; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; min-height: 100vh; background: radial-gradient(circle at top, #14213a 0, var(--bg) 48%); color: var(--text); font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    main {{ width: min(1080px, calc(100% - 32px)); margin: 48px auto; }}
    .card {{ background: rgba(16, 24, 39, .94); border: 1px solid var(--line); border-radius: 20px; box-shadow: 0 24px 80px rgba(0, 0, 0, .45); overflow: hidden; }}
    header {{ display: flex; align-items: center; justify-content: space-between; gap: 24px; padding: 28px 32px; border-bottom: 1px solid var(--line); background: linear-gradient(135deg, rgba(77, 216, 255, .11), rgba(60, 230, 160, .05)); }}
    h1 {{ margin: 0; font-size: clamp(1.25rem, 3vw, 2rem); letter-spacing: -.02em; }}
    .verified, .divergent {{ flex: 0 0 auto; padding: 9px 13px; border-radius: 999px; font: 700 .78rem ui-monospace, SFMono-Regular, Consolas, monospace; letter-spacing: .06em; }}
    .verified {{ color: #06170f; background: var(--green); box-shadow: 0 0 24px rgba(60, 230, 160, .35); }}
    .divergent {{ color: white; background: var(--red); }}
    .content {{ padding: 30px 32px 34px; }}
    .badges {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 28px; }}
    .badge {{ padding: 9px 12px; color: #c9d8ed; background: #0a111f; border: 1px solid #2a3c59; border-radius: 9px; font: 600 .82rem ui-monospace, SFMono-Regular, Consolas, monospace; }}
    section {{ margin-top: 24px; }}
    h2 {{ margin: 0 0 12px; color: var(--cyan); font-size: .78rem; letter-spacing: .14em; text-transform: uppercase; }}
    blockquote {{ margin: 0; padding: 22px 24px; background: #091422; border: 1px solid rgba(77, 216, 255, .4); border-left: 4px solid var(--cyan); border-radius: 12px; color: #e9f8ff; font-size: 1.02rem; line-height: 1.7; box-shadow: inset 0 0 28px rgba(77, 216, 255, .05), 0 0 24px rgba(77, 216, 255, .06); }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }}
    .metric {{ padding: 18px; background: #0a111f; border: 1px solid var(--line); border-radius: 12px; }}
    .label {{ display: block; margin-bottom: 7px; color: var(--muted); font-size: .77rem; letter-spacing: .08em; text-transform: uppercase; }}
    .value {{ color: var(--text); font: 700 1rem ui-monospace, SFMono-Regular, Consolas, monospace; overflow-wrap: anywhere; }}
    .ledger {{ color: var(--green); }}
    .comparison {{ display: grid; grid-template-columns: 1fr auto 1fr; align-items: stretch; gap: 14px; }}
    .equals {{ display: grid; place-items: center; color: var(--green); font-weight: 900; font-size: 1.4rem; }}
    .match {{ margin-top: 14px; padding: 12px; text-align: center; border: 1px solid rgba(60, 230, 160, .45); border-radius: 10px; color: var(--green); background: rgba(60, 230, 160, .06); font-weight: 800; letter-spacing: .1em; }}
    footer {{ padding: 18px 32px; border-top: 1px solid var(--line); color: var(--muted); font-size: .8rem; text-align: center; }}
    @media (max-width: 680px) {{ header {{ align-items: flex-start; flex-direction: column; }} .content {{ padding: 24px 20px; }} .grid, .comparison {{ grid-template-columns: 1fr; }} .equals {{ min-height: 20px; }} }}
  </style>
</head>
<body>
  <main>
    <article class="card">
      <header>
        <h1>AegisClaim <span style="color:#62738d">•</span> Clinical-Financial Audit Trail</h1>
        <span class="{badge_class}">{badge}</span>
      </header>
      <div class="content">
        <div class="badges">
          <span class="badge">Claim ID: {claim_id}</span>
          <span class="badge">Patient ID: {patient_id}</span>
          <span class="badge">Procedure: CPT-33361 (TAVR)</span>
        </div>
        <section>
          <h2>Clinical Evidence · Verbatim Source</h2>
          <blockquote>“{evidence}”</blockquote>
        </section>
        <section class="grid">
          <div class="metric">
            <span class="label">Policy Provenance</span>
            <span class="value">CMS Coverage Guideline · Git commit {policy_reference}</span>
          </div>
          <div class="metric">
            <span class="label">Ledger Mutation Status</span>
            <span class="value ledger">Stripe Ledger · {observed_state}<br>${authorized_amount:,.2f} disbursed</span>
          </div>
        </section>
        <section>
          <h2>Arga Read-After-Write State Verification</h2>
          <div class="comparison">
            <div class="metric"><span class="label">Expected State</span><span class="value">{expected_state}</span></div>
            <div class="equals">=</div>
            <div class="metric"><span class="label">Observed External State</span><span class="value">{observed_state}</span></div>
          </div>
          <div class="match">{match_indicator}</div>
        </section>
      </div>
      <footer>Deterministic audit artifact · GitHub policy provenance · Stripe state verification · Slack compliance dispatch</footer>
    </article>
  </main>
</body>
</html>
"""
        artifact_path.write_text(document, encoding="utf-8")
        return str(artifact_path.resolve())

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
