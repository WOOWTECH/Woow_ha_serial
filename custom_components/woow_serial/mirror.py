"""Send log (HAIR's Mirror): every frame Home Assistant sent, who sent it, and what came back.

Two things are read off the frames that follow a send:
- a reply: the first frame on the same port within the reply window;
- heard by: the same bytes arriving on *another* port shortly after (an RS485 line watched by
  both an on-board port and an HA-WF485-V3, say). That proves the send reached the wire, and
  such an echo is kept out of the monitor and, later, out of triggers, so nothing can fire on
  Home Assistant's own output.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.storage import Store

from .bus import BusFrame
from .catalog import _load, is_text, make_id
from .codec import printable, to_hex
from .const import DOMAIN, HEARD_WINDOW, LIVE_PUSH, MIRROR_ROWS

SAVE_DELAY = 30


@dataclass
class Sent:
    id: str
    port_id: str
    hex: str
    length: int
    text: str | None = None
    count: int = 0
    first_sent: float = 0.0
    last_sent: float = 0.0
    origin: str = ""  # who sent it last: service, entity, panel, device:<id> ...
    origins: dict[str, int] = field(default_factory=dict)
    replies: int = 0  # sends that got an answer on the same port
    reply: str | None = None  # the last answer (HEX)
    reply_ms: int | None = None
    heard_by: dict[str, int] = field(default_factory=dict)  # other ports that heard it


class Mirror:
    """Rows per (port, content), newest first, persisted, with batched pushes."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store: Store[dict[str, Any]] = Store(hass, 1, f"{DOMAIN}.mirror")
        self.rows: dict[str, Sent] = {}
        self._pending: dict[str, tuple[float, str]] = {}  # port -> (send time, row id) awaiting a reply
        self._recent: deque[tuple[str, str, float, str]] = deque(maxlen=64)  # (content key, port, time, row)
        self._listeners: list[Callable[[dict[str, Any]], None]] = []
        self._dirty: set[str] = set()
        self._removed: set[str] = set()
        self._push_handle = None

    async def async_load(self) -> None:
        data = await self._store.async_load() or {}
        for raw in data.get("rows", []):
            row = _load(Sent, raw)
            self.rows[row.id] = row

    def _data(self) -> dict[str, Any]:
        return {"rows": [asdict(r) for r in self.rows.values()]}

    async def async_flush(self) -> None:
        await self._store.async_save(self._data())

    # ---- intake ---------------------------------------------------------------------
    @callback
    def on_frame(self, frame: BusFrame, reply_window: float) -> bool:
        """Log a send, or match a received frame to one. True = our own send heard back."""
        if frame.direction == "tx":
            self._sent(frame)
            return False
        return self._heard(frame, reply_window)

    def _sent(self, frame: BusFrame) -> None:
        row_id = make_id(frame.port_id, frame.key)
        row = self.rows.get(row_id)
        if row is None:
            row = self.rows[row_id] = Sent(
                row_id, frame.port_id, to_hex(frame.data), len(frame.data),
                text=printable(frame.data) if is_text(frame.data) else None, first_sent=frame.time)
            if len(self.rows) > MIRROR_ROWS:
                oldest = min(self.rows.values(), key=lambda r: r.last_sent)
                self.rows.pop(oldest.id)
                self._removed.add(oldest.id)
        origin = frame.origin or "unknown"
        row.count += 1
        row.last_sent = frame.time
        row.origin = origin
        row.origins[origin] = row.origins.get(origin, 0) + 1
        self._pending[frame.port_id] = (frame.time, row_id)
        self._recent.append((frame.key, frame.port_id, frame.time, row_id))
        self._touch(row_id)

    def _heard(self, frame: BusFrame, reply_window: float) -> bool:
        now = frame.time
        for key, port_id, sent_at, row_id in reversed(self._recent):
            if now - sent_at > HEARD_WINDOW:
                break
            if port_id != frame.port_id and key == frame.key and row_id in self.rows:
                row = self.rows[row_id]
                row.heard_by[frame.port_id] = row.heard_by.get(frame.port_id, 0) + 1
                self._touch(row_id)
                return True
        pending = self._pending.get(frame.port_id)
        if pending is not None and now - pending[0] <= reply_window:
            del self._pending[frame.port_id]
            row = self.rows.get(pending[1])
            if row is not None:
                row.replies += 1
                row.reply = to_hex(frame.data)
                row.reply_ms = round((now - pending[0]) * 1000)
                self._touch(row.id)
        return False

    # ---- panel ----------------------------------------------------------------------
    def snapshot(self) -> dict[str, Any]:
        return {"rows": [asdict(r) for r in sorted(self.rows.values(), key=lambda r: -r.last_sent)]}

    def delete(self, row_id: str | None = None) -> None:
        """One row, or everything. A deleted row comes back with its next send."""
        for rid in [row_id] if row_id else list(self.rows):
            if self.rows.pop(rid, None) is not None:
                self._dirty.discard(rid)
                self._removed.add(rid)
        self._changed()

    @callback
    def subscribe(self, cb: Callable[[dict[str, Any]], None]) -> CALLBACK_TYPE:
        self._listeners.append(cb)
        return lambda: self._listeners.remove(cb)

    def _touch(self, row_id: str) -> None:
        self._dirty.add(row_id)
        self._changed()

    def _changed(self) -> None:
        self._store.async_delay_save(self._data, SAVE_DELAY)
        if self._listeners and self._push_handle is None:
            self._push_handle = self.hass.loop.call_later(LIVE_PUSH, self._push)

    @callback
    def _push(self) -> None:
        self._push_handle = None
        payload = {"rows": [asdict(self.rows[i]) for i in self._dirty if i in self.rows],
                   "removed": sorted(self._removed)}
        self._dirty.clear()
        self._removed.clear()
        for cb in list(self._listeners):
            cb(payload)
