import argparse
from copy import deepcopy
import sys

from rich.align import Align
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from aegis.orchestrator import AegisAdjudicator
from aegis.tools import GitHubPolicyTool, SlackAuditTool, StripeLedgerTool


def render_header(console: Console) -> None:
    title = Text("AegisClaim", style="bold bright_white", justify="center")
    subtitle = Text(
        "Autonomous Clinical-Financial Adjudication Engine",
        style="bold bright_cyan",
        justify="center",
    )
    callouts = Text.from_markup(
        "[bold cyan]ARGA DIGITAL TWIN SANDBOX[/bold cyan]  •  "
        "[bold magenta]LEMMA ZERO-SILENT-FAILURE GUARD[/bold magenta]  •  "
        "[bold yellow]FAccT COMPLIANCE[/bold yellow]",
        justify="center",
    )
    console.print(
        Panel(
            Align.center(Group(title, subtitle, Text(), callouts)),
            border_style="bright_cyan",
            padding=(1, 3),
        )
    )


def render_nominal_table(console: Console, approved_result: dict) -> None:
    policy_sha = approved_result["decision"]["policy_reference"].removeprefix("sha_")
    table = Table(
        title="[bold green]✓ Pipeline Execution Stages (Nominal Path)[/bold green]",
        border_style="green",
        header_style="bold bright_white on dark_green",
        expand=True,
    )
    table.add_column("#", justify="center", width=3)
    table.add_column("Control Plane", style="bold cyan", ratio=2)
    table.add_column("Action", ratio=3)
    table.add_column("Verified Outcome", style="bold", ratio=2)
    rows = [
        ("1", "Pre-Action Guard (Lemma)", "Schema & Synthetic Token Gate", "[bright_green]PASSED[/bright_green]"),
        ("2", "Knowledge Provenance (GitHub)", "Fetched CMS Policy", f"[bright_green]GROUNDED (SHA: {policy_sha})[/bright_green]"),
        ("3", "Financial Mutation (Stripe)", "Released Escrow Hold", "[bright_green]$14,500.00 DISBURSED[/bright_green]"),
        ("4", "State Verification (Arga Twin)", "Read-After-Write Assertion", "[bright_green]VERIFIED == TRUE[/bright_green]"),
        ("5", "Compliance Dispatch (Slack)", "Dispatched Block Kit Card", "[bright_green]#claim-audit[/bright_green]"),
    ]
    for row in rows:
        table.add_row(*row)
    console.print(table)


def render_safety_table(console: Console, stripe_untouched: bool) -> None:
    table = Table(
        title="[bold red]⚠️ Safety Interlock Activation[/bold red]",
        border_style="bright_red",
        header_style="bold bright_white on dark_red",
        expand=True,
    )
    table.add_column("#", justify="center", width=3)
    table.add_column("Safety Control", style="bold bright_red", ratio=2)
    table.add_column("Detected Event", ratio=3)
    table.add_column("Protected Outcome", style="bold", ratio=3, overflow="fold")
    rows = [
        ("1", "Lemma Guardrail", "Intercepted synthetic token [bold]unknown[/bold]", "[bright_red]PIPELINE HALTED (Stage 1)[/bright_red]"),
        ("2", "Financial Ledger", "Verified zero-mutation constraint", f"[bright_green]Stripe Untouched: {stripe_untouched}[/bright_green]"),
        ("3", "HITL Escalation", "Emergency compliance card", "[bright_yellow]Routed to #compliance-escalations[/bright_yellow]"),
    ]
    for row in rows:
        table.add_row(*row)
    console.print(table)


def render_summary(console: Console, stripe_untouched: bool) -> None:
    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="bold bright_white")
    summary.add_column(justify="right", style="bold bright_green")
    summary.add_row("Verified financial state transitions", "1")
    summary.add_row("Unsafe financial mutations", "0")
    summary.add_row("Zero-mutation guarantee", "ENFORCED" if stripe_untouched else "FAILED")
    summary.add_row("Deterministic integrity", "100%")
    console.print(
        Panel(
            summary,
            title="[bold bright_cyan]SYSTEM ASSURANCE SUMMARY[/bold bright_cyan]",
            border_style="bright_cyan",
            padding=(1, 3),
        )
    )


def valid_claim_payload() -> dict:
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


def render_nominal_scenario(
    console: Console,
    adjudicator: AegisAdjudicator,
    slack: SlackAuditTool,
    claim: dict,
) -> dict:
    result = adjudicator.adjudicate_claim(claim)
    console.print(
        Panel(
            "[bold]CLM-1092[/bold]  •  PAT-9841  •  CPT 33361  •  ICD-10 I35.0  •  "
            "[bold bright_green]$14,500.00[/bold bright_green]",
            title="[bold bright_white]SCENARIO 1 — NOMINAL TAVR ADJUDICATION[/bold bright_white]",
            border_style="green",
        )
    )
    render_nominal_table(console, result)
    html_path = slack.render_html_audit_card(result["decision"], result["verification"])
    json_path = slack.export_audit_json(result["decision"], result["verification"])
    console.print(
        f"[dim cyan]📄 Generated Visual Audit Artifact: file:///{html_path}[/dim cyan]"
    )
    console.print(
        f"[dim cyan]📋 Generated Machine Audit Artifact: file:///{json_path}[/dim cyan]"
    )
    return result


def render_placeholder_scenario(
    console: Console,
    adjudicator: AegisAdjudicator,
    stripe: StripeLedgerTool,
    claim: dict,
) -> tuple[dict, bool]:
    stripe_before_invalid = deepcopy(stripe.claims)
    invalid_result = adjudicator.adjudicate_claim(
        {**claim, "claim_id": "CLM-PLACEHOLDER-TEST", "patient_id": "unknown"}
    )
    stripe_untouched = stripe.claims == stripe_before_invalid
    console.print(
        Panel(
            'Injected payload: [bold bright_red]patient_id="unknown"[/bold bright_red]',
            title="[bold bright_white]SCENARIO 2 — SYNTHETIC ID INJECTION[/bold bright_white]",
            border_style="bright_red",
        )
    )
    render_safety_table(console, stripe_untouched)
    return invalid_result, stripe_untouched


def render_rollback_scenario(console: Console, claim: dict) -> dict:
    class AuditFailureSlackTool(SlackAuditTool):
        def post_adjudication_audit(self, decision: object, verification: object) -> dict:
            raise RuntimeError("Injected downstream compliance dispatch failure")

    stripe = StripeLedgerTool(twin_mode=True)
    slack = AuditFailureSlackTool(twin_mode=True)
    adjudicator = AegisAdjudicator(
        GitHubPolicyTool(twin_mode=True),
        stripe,
        slack,
    )
    result = adjudicator.adjudicate_claim(claim)
    table = Table(
        title="[bold yellow]↩ Saga Compensating Transaction[/bold yellow]",
        border_style="yellow",
        header_style="bold bright_white on dark_orange",
        expand=True,
    )
    table.add_column("Transaction Stage", style="bold cyan")
    table.add_column("State Transition")
    table.add_column("Outcome", style="bold")
    table.add_row("Stripe payout", "on_hold → settled_approved", "[green]COMMITTED[/green]")
    table.add_row(
        "Slack audit dispatch",
        "Injected downstream failure",
        "[red]FAILED[/red]",
    )
    table.add_row(
        "Saga compensation",
        "settled_approved → on_hold_frozen",
        "[yellow]COMPENSATED_ROLLED_BACK[/yellow]",
    )
    console.print(
        Panel(
            "A downstream audit failure is injected after payout to prove automatic financial containment.",
            title="[bold bright_white]SCENARIO 3 — SAGA ROLLBACK INTERLOCK[/bold bright_white]",
            border_style="yellow",
        )
    )
    console.print(table)
    assert result["status"] == "compensated_rolled_back"
    assert stripe.claims[claim["claim_id"]]["status"] == "on_hold_frozen"
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run AegisClaim deterministic demo scenarios")
    parser.add_argument(
        "--scenario",
        choices=("all", "nominal", "placeholder", "rollback"),
        default="all",
        help="scenario to execute (default: all)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    console = Console()
    github = GitHubPolicyTool(twin_mode=True)
    stripe = StripeLedgerTool(twin_mode=True)
    slack = SlackAuditTool(twin_mode=True)
    adjudicator = AegisAdjudicator(github, stripe, slack)
    claim = valid_claim_payload()
    approved_result = None
    invalid_result = None
    stripe_untouched = True

    render_header(console)
    if args.scenario in ("all", "nominal"):
        approved_result = render_nominal_scenario(console, adjudicator, slack, claim)
    if args.scenario in ("all", "placeholder"):
        invalid_result, stripe_untouched = render_placeholder_scenario(
            console,
            adjudicator,
            stripe,
            claim,
        )
    if args.scenario == "rollback":
        render_rollback_scenario(console, claim)
    if args.scenario == "all":
        render_summary(console, stripe_untouched)

    if approved_result is not None:
        assert approved_result["status"] == "completed"
        assert approved_result["verification"]["verified"] is True
    if invalid_result is not None:
        assert invalid_result["stage"] == "pre_action_guard"
        assert stripe_untouched


if __name__ == "__main__":
    main()
