"""SSE event streaming route for live updates."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["events"])


async def _event_generator(listeners: list[asyncio.Queue] | None) -> AsyncIterator[dict]:
    """Yield SSE-formatted events from a per-client queue.

    Registers a private queue on connect, removes it on disconnect, so that
    every connected client receives every event (fan-out).
    """
    if listeners is None:
        return

    queue: asyncio.Queue = asyncio.Queue()
    listeners.append(queue)
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield {
                    "event": event.get("type", "message"),
                    "data": json.dumps(event.get("data", {})),
                }
            except asyncio.TimeoutError:
                # Send keepalive comment to prevent connection timeout
                yield {"comment": "keepalive"}
            except asyncio.CancelledError:
                break
    finally:
        listeners.remove(queue)


@router.get("/events")
async def event_stream(request: Request):
    """SSE endpoint for real-time events (reindex_start, reindex_complete, file_changed)."""
    listeners = request.app.state.event_listeners
    return EventSourceResponse(_event_generator(listeners))
