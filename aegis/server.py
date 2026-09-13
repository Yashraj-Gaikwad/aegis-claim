import asyncio
import json
from collections.abc import AsyncGenerator, Awaitable, Callable
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from aegis.orchestrator import AegisAdjudicator

app = FastAPI(title="AegisClaim API", version="1.0.0")
adjudicator = AegisAdjudicator()
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


def run_adjudication(payload: dict[str, Any]) -> dict:
    with _adjudication_lock:
        return adjudicator.adjudicate_claim(payload)


async def event_generator() -> AsyncGenerator[str, None]:
    queue = broadcaster.subscribe()
    try:
        while True:
            event = await queue.get()
            yield f"data: {json.dumps(event, separators=(',', ':'))}\n\n"
    finally:
        broadcaster.unsubscribe(queue)


@app.post("/api/v1/adjudicate")
async def adjudicate(payload: dict[str, Any]) -> dict:
    await emit_event("CLAIM_RECEIVED")
    result = await asyncio.to_thread(run_adjudication, payload)
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


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "healthy", "service": "aegis-claim", "twin_mode": True}
