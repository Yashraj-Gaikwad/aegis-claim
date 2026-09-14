import asyncio
import json
import os
from collections.abc import AsyncGenerator, Awaitable, Callable
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import AliasChoices, BaseModel, Field

from aegis.orchestrator import AegisAdjudicator

app = FastAPI(title="AegisClaim API", version="1.0.0")
_cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "*").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
adjudicator = AegisAdjudicator()


class ClaimSubmission(BaseModel):
    claim_id: str
    patient_id: str
    cpt_code: str
    icd10_code: str
    amount: float = Field(validation_alias=AliasChoices("amount", "claimed_amount"))
    clinical_notes: str
    deidentify_phi: bool = True
    scenario: str | None = None

    def to_adjudicator_payload(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "patient_id": self.patient_id,
            "cpt_code": self.cpt_code,
            "icd10_code": self.icd10_code,
            "claimed_amount": self.amount,
            "clinical_notes": self.clinical_notes,
        }


_NOMINAL_SCENARIO = {
    "claim_id": "CLM-1092",
    "patient_id": "PAT-9841",
    "cpt_code": "33361",
    "icd10_code": "I35.0",
    "amount": 14500.0,
    "clinical_notes": (
        "The 74-year-old patient has severe symptomatic aortic stenosis with NYHA Class III "
        "heart failure symptoms. Echocardiography documents a valve area of 0.7 cm2 and a "
        "mean aortic gradient of 46 mmHg. The multidisciplinary heart team signed off on TAVR."
    ),
    "deidentify_phi": True,
}
_adjudication_lock = Lock()


class EventBroadcaster:
    def __init__(self) -> None:
        self.subscribers: set[asyncio.Queue[dict[str, str]]] = set()

    async def broadcast(self, event_name: str) -> None:
        event = {
            "event": event_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        for queue in tuple(self.subscribers):
            await queue.put(event)

    def subscribe(self) -> asyncio.Queue[dict[str, str]]:
        queue: asyncio.Queue[dict[str, str]] = asyncio.Queue()
        self.subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, str]]) -> None:
        self.subscribers.discard(queue)


broadcaster = EventBroadcaster()
_event_callbacks: list[Callable[[str], Awaitable[None]]] = [broadcaster.broadcast]


async def emit_event(event_name: str) -> None:
    await asyncio.gather(*(callback(event_name) for callback in _event_callbacks))


def run_adjudication(
    payload: dict[str, Any],
    deidentify_phi: bool = True,
    simulate_rollback: bool = False,
) -> dict:
    with _adjudication_lock:
        previous_setting = adjudicator.deidentify_phi
        adjudicator.deidentify_phi = deidentify_phi
        try:
            result = adjudicator.adjudicate_claim(payload)
            if simulate_rollback and result.get("status") == "completed":
                reason = "Simulated downstream audit failure"
                compensation = adjudicator.stripe_tool.compensate_freeze_hold(
                    payload["claim_id"],
                    reason=reason,
                )
                verification = dict(result["verification"])
                verification.update(observed_state="on_hold_frozen", verified=False)
                return {
                    **result,
                    "status": "compensated_rolled_back",
                    "error": reason,
                    "compensation": compensation,
                    "verification": verification,
                    "dispatch": adjudicator.slack_tool.post_escalation_alert(
                        payload["claim_id"],
                        f"CRITICAL Saga compensation executed: {reason}",
                    ),
                }
            return result
        finally:
            adjudicator.deidentify_phi = previous_setting


async def event_generator() -> AsyncGenerator[str, None]:
    queue = broadcaster.subscribe()
    try:
        while True:
            event = await queue.get()
            yield f"data: {json.dumps(event, separators=(',', ':'))}\n\n"
    finally:
        broadcaster.unsubscribe(queue)


@app.post("/api/v1/adjudicate")
async def adjudicate(submission: ClaimSubmission) -> dict:
    await emit_event("CLAIM_RECEIVED")
    payload = submission.to_adjudicator_payload()
    result = await asyncio.to_thread(
        run_adjudication,
        payload,
        submission.deidentify_phi,
        submission.scenario == "rollback",
    )
    completion_event = (
        "ADJUDICATION_COMPLETED"
        if result.get("status") == "completed"
        else "ADJUDICATION_ESCALATED"
    )
    await emit_event(completion_event)
    verification = result.get("verification")
    if verification and verification.get("verified") is True:
        await emit_event("STATE_VERIFIED")
    return result


@app.get("/api/v1/stream")
async def stream() -> StreamingResponse:
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/v1/scenarios/{scenario_name}")
async def scenario(scenario_name: str) -> dict:
    if scenario_name == "nominal":
        return dict(_NOMINAL_SCENARIO)
    if scenario_name == "placeholder":
        return {**_NOMINAL_SCENARIO, "claim_id": "CLM-PLACEHOLDER-TEST", "patient_id": "unknown"}
    if scenario_name == "rollback":
        return {**_NOMINAL_SCENARIO, "scenario": "rollback"}
    raise HTTPException(status_code=404, detail="Unknown scenario. Use nominal, placeholder, or rollback.")


@app.get("/healthz")
async def healthz() -> dict:
    return {
        "status": "healthy",
        "service": "aegis-claim",
        "twin_mode": True,
        "engine": "AegisClaim",
        "version": "1.0.0",
    }
