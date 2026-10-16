"""Activity log: who did what, for people checking on what an AI agent (or anyone) changed.

Agents work through Home Assistant services (e.g. over MCP); people mostly through the panel.
Every change and every send made through either door is recorded with its actor, the user
behind the call, and an optional note the caller gives ("why"). The panel shows the log live.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, field
import time
from typing import Any

from homeassistant.core import CALLBACK_TYPE, Context, HomeAssistant, callback
from homeassistant.helpers.storage import Store

from .const import DOMAIN, LIVE_PUSH

MAX_ENTRIES = 1000
SAVE_DELAY = 30

# One English line per message; the panel shows the same message translated (log_<msg>) with the entry's args.
MESSAGES = {
    "sent": "sent {hex} on {port}",
    "device_created": 'created device "{device}" ({type}) on {port}',
    "device_updated": 'updated device "{device}" ({type}) on {port}',
    "device_from_template": 'created device "{device}" from template {template} on {port}',
    "device_save_failed": 'could not save device "{device}": {error}',
    "device_deleted": 'deleted device "{device}"',
    "command_sent": '{device}: sent "{command}" {hex}',
    "command_tested": '{device}: tested "{command}" {hex}',
    "command_failed": '{device}: "{command}" failed: {error}',
    "command_learned": '{device}: learned command "{name}" from {hex}',
    "button_learned": '{device}: learned button "{name}" from {hex}',
    "entity_action": "{device}: {action}{value}",
    "entity_action_failed": "{device}: {action}{value} failed: {error}",
    "entity_command": '{device}: pressed "{command}"',
    "entity_option": "{device}: {field} → {option}",
}


class _Blank(dict):
    def __missing__(self, key: str) -> str:
        return "?"


def summarize(msg: str, args: dict[str, Any]) -> str:
    return MESSAGES.get(msg, msg).format_map(_Blank(args))


@dataclass
class Activity:
    t: float
    channel: str  # "service" (agents, scripts, automations), "panel", "entity" (an entity action)
    action: str  # save_device, delete_device, run_command, send, create_from_template, learn_command ...
    summary: str  # one English line, e.g. 'created device "Living room curtain" (cover) on RS485-1'
    ok: bool = True
    user: str | None = None  # Home Assistant user behind the call, when known
    note: str = ""  # the caller's own explanation (agents are asked to give one)
    device_id: str | None = None
    port_id: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)
    msg: str = ""  # MESSAGES key; the panel translates it
    args: dict[str, Any] = field(default_factory=dict)  # values for the message


class ActivityLog:
    """Ring buffer of activities, persisted, with batched pushes to the panel."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store: Store[dict[str, Any]] = Store(hass, 1, f"{DOMAIN}.activity")
        self.entries: list[Activity] = []
        self._listeners: list[Callable[[dict[str, Any]], None]] = []
        self._pending: list[Activity] = []
        self._push_handle = None
        self._users: dict[str, str | None] = {}

    async def async_load(self) -> None:
        data = await self._store.async_load() or {}
        names = set(Activity.__dataclass_fields__)
        self.entries = [Activity(**{k: v for k, v in raw.items() if k in names}) for raw in data.get("entries", [])]

    def _data(self) -> dict[str, Any]:
        return {"entries": [asdict(e) for e in self.entries]}

    async def async_flush(self) -> None:
        await self._store.async_save(self._data())

    async def async_user_name(self, context: Context | None) -> str | None:
        user_id = context.user_id if context is not None else None
        if not user_id:
            return None
        if user_id not in self._users:
            user = await self.hass.auth.async_get_user(user_id)
            self._users[user_id] = user.name if user is not None else None
        return self._users[user_id]

    async def async_record(self, channel: str, action: str, msg: str, args: dict[str, Any], *,
                           context: Context | None = None, user: str | None = None, ok: bool = True, note: str = "",
                           device_id: str | None = None, port_id: str | None = None, **detail: Any) -> None:
        if user is None:
            user = await self.async_user_name(context)
        self.record(Activity(time.time(), channel, action, summarize(msg, args), ok, user, note or "", device_id,
                             port_id, detail, msg, args))

    @callback
    def record(self, entry: Activity) -> None:
        self.entries.append(entry)
        del self.entries[:-MAX_ENTRIES]
        self._store.async_delay_save(self._data, SAVE_DELAY)
        if not self._listeners:
            return
        self._pending.append(entry)
        if self._push_handle is None:
            self._push_handle = self.hass.loop.call_later(LIVE_PUSH, self._push)

    def recent(self, limit: int = 100, device_id: str | None = None) -> list[dict[str, Any]]:
        rows = [e for e in self.entries if device_id is None or e.device_id == device_id]
        return [asdict(e) for e in reversed(rows[-limit:])]

    @callback
    def subscribe(self, cb: Callable[[dict[str, Any]], None]) -> CALLBACK_TYPE:
        self._listeners.append(cb)
        return lambda: self._listeners.remove(cb)

    @callback
    def _push(self) -> None:
        self._push_handle = None
        entries, self._pending = self._pending, []
        for cb in list(self._listeners):
            cb({"entries": [asdict(e) for e in entries]})
