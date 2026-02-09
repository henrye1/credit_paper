"""SSE log streaming infrastructure using asyncio queues."""

import asyncio
import json
from typing import Optional


# In-memory store of active log queues, keyed by assessment/run ID
_log_queues: dict[str, asyncio.Queue] = {}


def create_log_queue(task_id: str) -> asyncio.Queue:
    """Create a new log queue for a task."""
    q = asyncio.Queue()
    _log_queues[task_id] = q
    return q


def get_log_queue(task_id: str) -> Optional[asyncio.Queue]:
    """Get an existing log queue."""
    return _log_queues.get(task_id)


def remove_log_queue(task_id: str):
    """Remove a log queue after task completes."""
    _log_queues.pop(task_id, None)


def push_log(task_id: str, event: str, data: str):
    """Push a log event to the queue (thread-safe for sync callers)."""
    q = _log_queues.get(task_id)
    if q:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.call_soon_threadsafe(q.put_nowait, {"event": event, "data": data})
            else:
                q.put_nowait({"event": event, "data": data})
        except RuntimeError:
            # No event loop in this thread — just put directly
            q.put_nowait({"event": event, "data": data})


async def event_generator(task_id: str):
    """Async generator that yields SSE events from a log queue."""
    q = get_log_queue(task_id)
    if not q:
        yield f"event: error\ndata: No active task for {task_id}\n\n"
        return

    while True:
        try:
            msg = await asyncio.wait_for(q.get(), timeout=30.0)
        except asyncio.TimeoutError:
            # Send keepalive to prevent connection drop
            yield ": keepalive\n\n"
            continue

        event_type = msg.get("event", "log")
        data = msg.get("data", "")

        if event_type == "done":
            yield f"event: complete\ndata: {data}\n\n"
            remove_log_queue(task_id)
            break
        elif event_type == "error":
            yield f"event: error\ndata: {data}\n\n"
            remove_log_queue(task_id)
            break
        else:
            yield f"event: {event_type}\ndata: {data}\n\n"
