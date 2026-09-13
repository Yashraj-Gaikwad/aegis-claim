from copy import deepcopy

from aegis.orchestrator import AegisAdjudicator
from aegis.tools import GitHubPolicyTool, SlackAuditTool, StripeLedgerTool


def main() -> None:
    github = GitHubPolicyTool(twin_mode=True)
    stripe = StripeLedgerTool(twin_mode=True)
    slack = SlackAuditTool(twin_mode=True)
    adjudicator = AegisAdjudicator(github, stripe, slack)

    valid_claim = {
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
    approved_result = adjudicator.adjudicate_claim(valid_claim)
    print("VALID CLAIM")
    print(f"  Pipeline status: {approved_result['status']}")
    print(f"  Approved: {approved_result['decision']['approved']}")
    print(f"  Stripe status: {approved_result['verification']['observed_state']}")
    print(f"  Arga verified: {approved_result['verification']['verified']}")
    print(f"  Slack messages dispatched: {len(slack.dispatched_messages)}")

    stripe_before_invalid = deepcopy(stripe.claims)
    invalid_claim = {
        **valid_claim,
        "claim_id": "CLM-PLACEHOLDER-TEST",
        "patient_id": "unknown",
    }
    invalid_result = adjudicator.adjudicate_claim(invalid_claim)
    stripe_untouched = stripe.claims == stripe_before_invalid
    print("\nPLACEHOLDER CLAIM")
    print(f"  Pipeline status: {invalid_result['status']}")
    print(f"  Blocked at: {invalid_result['stage']}")
    print(f"  Stripe mutation prevented: {stripe_untouched}")
    print(f"  HITL channel: {invalid_result['dispatch']['channel']}")
    print(f"  Total Slack messages dispatched: {len(slack.dispatched_messages)}")

    assert approved_result["status"] == "completed"
    assert approved_result["verification"]["verified"] is True
    assert invalid_result["stage"] == "pre_action_guard"
    assert stripe_untouched


if __name__ == "__main__":
    main()
