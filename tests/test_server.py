from fastapi.testclient import TestClient

from aegis.server import app

client = TestClient(app)


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


def test_healthz() -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_adjudicate_valid_claim() -> None:
    response = client.post("/api/v1/adjudicate", json=valid_claim())

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["decision"]["approved"] is True


def test_adjudicate_placeholder_claim() -> None:
    response = client.post(
        "/api/v1/adjudicate",
        json={**valid_claim(), "patient_id": "unknown"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "escalated"
    assert response.json()["stage"] == "pre_action_guard"
