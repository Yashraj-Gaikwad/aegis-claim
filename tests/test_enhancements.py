import json
import os
from datetime import datetime
from pathlib import Path
import subprocess
import sys

from aegis.deid import scrub_phi
from aegis.orchestrator import AegisAdjudicator
from aegis.tools import GitHubPolicyTool, SlackAuditTool, StripeLedgerTool

ROOT = Path(__file__).resolve().parents[1]


def valid_claim() -> dict:
    return {
        "claim_id": "CLM-1092",
        "patient_id": "PAT-9841",
        "icd10_code": "I35.0",
        "cpt_code": "33361",
        "claimed_amount": 14500.0,
        "clinical_notes": (
            "The patient has severe symptomatic aortic stenosis with NYHA Class III symptoms, "
            "a valve area of 0.7 cm2, a mean aortic gradient of 46 mmHg, and heart team sign-off."
        ),
    }


def test_phi_deidentification_scrubbing() -> None:
    scrubbed, redaction_types = scrub_phi(
        "DOB: 04/12/1952; SSN 123-45-6789; phone (404) 555-0198; email patient@example.com."
    )

    assert "[REDACTED_DATE]" in scrubbed
    assert "[REDACTED_SSN]" in scrubbed
    assert "[REDACTED_PHONE]" in scrubbed
    assert "[REDACTED_EMAIL]" in scrubbed
    assert "123-45-6789" not in scrubbed
    assert "(404) 555-0198" not in scrubbed
    assert "patient@example.com" not in scrubbed
    assert redaction_types == ["SSN", "DATE", "PHONE", "EMAIL"]

    adjudicator = AegisAdjudicator()
    result = adjudicator.adjudicate_claim(
        {
            **valid_claim(),
            "clinical_notes": valid_claim()["clinical_notes"]
            + " Contact patient@example.com or 404-555-0198.",
        }
    )
    assert result["status"] == "completed"
    assert result["phi_redactions"] == ["PHONE", "EMAIL"]
    assert "[REDACTED_PHONE]" in result["decision"]["exact_evidence_quote"]
    assert "[REDACTED_EMAIL]" in result["decision"]["exact_evidence_quote"]
    assert "patient@example.com" not in result["decision"]["exact_evidence_quote"]


def test_audit_json_export_structure() -> None:
    slack = SlackAuditTool(twin_mode=True)
    adjudicator = AegisAdjudicator(
        GitHubPolicyTool(twin_mode=True),
        StripeLedgerTool(twin_mode=True),
        slack,
    )
    result = adjudicator.adjudicate_claim(valid_claim())

    artifact_path = Path(
        slack.export_audit_json(result["decision"], result["verification"])
    )
    audit = json.loads(artifact_path.read_text(encoding="utf-8"))

    assert artifact_path == ROOT / "audit_artifact.json"
    assert datetime.fromisoformat(audit["timestamp"]).tzinfo is not None
    assert len(audit["claim_fingerprint"]) == 64
    int(audit["claim_fingerprint"], 16)
    assert audit["fingerprint_algorithm"] == "SHA-256"
    assert audit["claim_id"] == "CLM-1092"
    assert audit["patient_id"] == "PAT-9841"
    assert audit["cpt_code"] == "33361"
    assert audit["icd10_code"] == "I35.0"
    assert audit["policy_commit_sha"] == "sha_c9f482a"
    assert audit["stripe_dispute_state"] == {
        "expected": "settled_approved",
        "observed": "settled_approved",
    }
    assert audit["verification_status"] == "verified"
    assert audit["verified"] is True
    assert audit["event_trail"]


def test_cli_scenario_flags() -> None:
    environment = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    for scenario, expected_output in (
        ("nominal", "Pipeline Execution Stages (Nominal Path)"),
        ("placeholder", "Safety Interlock Activation"),
    ):
        completed = subprocess.run(
            [sys.executable, "main.py", "--scenario", scenario],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr
        assert expected_output in completed.stdout
