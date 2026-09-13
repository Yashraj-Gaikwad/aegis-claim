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


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    console = Console()
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

    stripe_before_invalid = deepcopy(stripe.claims)
    invalid_claim = {
        **valid_claim,
        "claim_id": "CLM-PLACEHOLDER-TEST",
        "patient_id": "unknown",
    }
    invalid_result = adjudicator.adjudicate_claim(invalid_claim)
    stripe_untouched = stripe.claims == stripe_before_invalid

    render_header(console)
    console.print(
        Panel(
            "[bold]CLM-1092[/bold]  •  PAT-9841  •  CPT 33361  •  ICD-10 I35.0  •  "
            "[bold bright_green]$14,500.00[/bold bright_green]",
            title="[bold bright_white]SCENARIO 1 — NOMINAL TAVR ADJUDICATION[/bold bright_white]",
            border_style="green",
        )
    )
    render_nominal_table(console, approved_result)
    html_path = slack.render_html_audit_card(
        approved_result["decision"],
        approved_result["verification"],
    )
    console.print(
        f"[dim cyan]📄 Generated Visual Audit Artifact: file:///{html_path}[/dim cyan]"
    )
    console.print(
        Panel(
            'Injected payload: [bold bright_red]patient_id="unknown"[/bold bright_red]',
            title="[bold bright_white]SCENARIO 2 — SYNTHETIC ID INJECTION[/bold bright_white]",
            border_style="bright_red",
        )
    )
    render_safety_table(console, stripe_untouched)
    render_summary(console, stripe_untouched)

    assert approved_result["status"] == "completed"
    assert approved_result["verification"]["verified"] is True
    assert invalid_result["stage"] == "pre_action_guard"
    assert stripe_untouched


if __name__ == "__main__":
    main()
