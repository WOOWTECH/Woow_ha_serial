"""The admin layer (one per Home Assistant): bus monitor, send log, and the panel's live feed.

Modelled on HAIR, which sits on top of Home Assistant's infrared platform; here the serial ports
of this integration (on-board and bound external ones) play that platform's part.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_FINAL_WRITE
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .activity import ActivityLog
from .bus import BusFrame, get_bus
from .catalog import Catalog, is_text
from .codec import parse_hex, printable, to_hex, unescape
from .devices import DeviceManager
from .const import (
    KIND_EXTERNAL,
    KIND_HUB,
    LIVE_MAX,
    LIVE_PUSH,
    REPLY_WINDOW,
    REPLY_WINDOW_EXTERNAL,
)
from .mirror import Mirror
from .panel import async_register_panel, async_remove_panel
from .templates import TemplateLibrary


def frame_dict(frame: BusFrame, echo: bool) -> dict[str, Any]:
    return {
        "t": frame.time,
        "port": frame.port_id,
        "dir": frame.direction,
        "hex": to_hex(frame.data),
        "text": printable(frame.data) if is_text(frame.data) else None,
        "origin": frame.origin,
        "echo": echo,
    }


class AdminHub:
    """Owns the monitor catalog and the send log, and streams both to the panel."""

    kind = KIND_HUB

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.bus = get_bus(hass)
        self.catalog = Catalog(hass)
        self.mirror = Mirror(hass)
        self.devices = DeviceManager(hass, entry, self.bus)
        self.activity = ActivityLog(hass)
        self.devices.activity = self.activity
        self.templates = TemplateLibrary(hass)
        self._subs: list[Callable[[str, dict[str, Any]], None]] = []
        self._live: list[dict[str, Any]] = []
        self._live_dropped = 0
        self._live_handle = None
        # port -> waiting listen calls, each with an optional test a frame must pass
        self._listening: dict[str, list[tuple[asyncio.Future[bytes], Callable[[bytes], bool] | None]]] = {}
        self._unsubs: list[CALLBACK_TYPE] = []

    async def async_start(self) -> None:
        await self.catalog.async_load()
        await self.mirror.async_load()
        await self.devices.async_load()
        await self.activity.async_load()
        await self.templates.async_load()
        # Entity rows left by commands, sensors or devices deleted earlier; before any platform
        # registers, so nothing live can be mistaken for one.
        self.devices.prune_registry()
        self._unsubs += [
            self.bus.subscribe(self._on_frame),
            self.bus.subscribe_ports(self._on_port),
            self.catalog.subscribe(lambda payload: self._send("catalog", payload)),
            self.mirror.subscribe(lambda payload: self._send("mirror", payload)),
            self.devices.subscribe(self._send),
            self.activity.subscribe(lambda payload: self._send("activity", payload)),
            # A graceful restart does not unload entries; FINAL_WRITE is where stores get saved.
            self.hass.bus.async_listen(EVENT_HOMEASSISTANT_FINAL_WRITE, self._async_final_write),
        ]
        self.devices.start()
        await async_register_panel(self.hass)

    async def async_stop(self) -> None:
        self.devices.stop()
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._live_handle is not None:
            self._live_handle.cancel()
            self._live_handle = None
        async_remove_panel(self.hass)
        await self.catalog.async_flush()
        await self.mirror.async_flush()
        await self.activity.async_flush()

    async def _async_final_write(self, _event: Event) -> None:
        await self.catalog.async_flush()
        await self.mirror.async_flush()
        await self.activity.async_flush()

    # ---- frames ---------------------------------------------------------------------
    @callback
    def _on_frame(self, frame: BusFrame) -> None:
        port = self.bus.ports.get(frame.port_id)
        external = port is not None and port.kind == KIND_EXTERNAL
        echo = self.mirror.on_frame(frame, REPLY_WINDOW_EXTERNAL if external else REPLY_WINDOW)
        if frame.direction == "tx":
            self.devices.on_sent(frame)
        elif not echo:
            self.catalog.on_frame(frame)
            self.devices.on_frame(frame)  # state feedback, sensors and keypads of the devices on this port
            if waiting := self._listening.get(frame.port_id):
                keep = []
                for fut, match in waiting:
                    if fut.done():
                        continue
                    if match is None or match(frame.data):
                        fut.set_result(frame.data)
                    else:
                        keep.append((fut, match))
                self._listening[frame.port_id] = keep
        if not self._subs:
            return
        if len(self._live) < LIVE_MAX:
            self._live.append(frame_dict(frame, echo))
        else:
            self._live_dropped += 1
        if self._live_handle is None:
            self._live_handle = self.hass.loop.call_later(LIVE_PUSH, self._push_live)

    @callback
    def _push_live(self) -> None:
        self._live_handle = None
        frames, dropped = self._live, self._live_dropped
        self._live, self._live_dropped = [], 0
        self._send("frames", {"frames": frames, "dropped": dropped})

    @callback
    def _on_port(self, port_id: str) -> None:
        hub = self.bus.ports.get(port_id)
        if hub is not None:
            self._send("ports", {"ports": [hub.info()], "removed": []})
        else:
            self._send("ports", {"ports": [], "removed": [port_id]})

    # ---- panel feed -----------------------------------------------------------------
    @callback
    def subscribe(self, cb: Callable[[str, dict[str, Any]], None]) -> CALLBACK_TYPE:
        self._subs.append(cb)
        return lambda: self._subs.remove(cb)

    @callback
    def _send(self, kind: str, payload: dict[str, Any]) -> None:
        for cb in list(self._subs):
            cb(kind, payload)

    def snapshot(self) -> dict[str, Any]:
        return {
            "ports": [hub.info() for hub in self.bus.ports.values()],
            "catalog": self.catalog.snapshot(),
            "mirror": self.mirror.snapshot(),
            "devices": self.devices.snapshot(),
            "activity": self.activity.recent(200),
            "templates": self.templates.summaries(self.hass.config.language or "en"),
        }

    @callback
    def expect_frame(self, port_id: str, match: Callable[[bytes], bool] | None = None) -> asyncio.Future[bytes]:
        """A future for the next frame a port hears that passes `match` (not one of our own sends).
        Taken before sending, so a fast answer is not missed; hand it to async_wait_frame."""
        fut: asyncio.Future[bytes] = self.hass.loop.create_future()
        self._listening.setdefault(port_id, []).append((fut, match))
        return fut

    async def async_wait_frame(self, port_id: str, fut: asyncio.Future[bytes], timeout: float) -> bytes | None:
        try:
            return await asyncio.wait_for(fut, timeout)
        except TimeoutError:
            return None
        finally:
            self.forget_frame(port_id, fut)

    @callback
    def forget_frame(self, port_id: str, fut: asyncio.Future[bytes]) -> None:
        self._listening[port_id] = [w for w in self._listening.get(port_id, []) if w[0] is not fut]

    async def async_listen(self, port_id: str, timeout: float,
                           match: Callable[[bytes], bool] | None = None) -> bytes | None:
        """The next frame a port hears, e.g. a keypad press to learn."""
        return await self.async_wait_frame(port_id, self.expect_frame(port_id, match), timeout)

    def recent_frames(self, port_id: str) -> list[bytes]:
        """Frames the monitor holds for a port, for trying a receive pattern in the editor."""
        return [bytes.fromhex(r.hex.replace(" ", "")) for r in self.catalog.rows.values() if r.port_id == port_id]

    async def async_send(self, port_id: str, *, hex_data: str | None = None, text: str | None = None,
                         wait_ms: int = 0) -> dict[str, Any]:
        """A send typed into the panel."""
        hub = self.bus.ports.get(port_id)
        if hub is None:
            raise HomeAssistantError(f"port {port_id} is not loaded")
        wait = wait_ms / 1000
        if hex_data is not None:
            data = parse_hex(hex_data)
        else:
            data = unescape(text or "") + hub.line_ending
        reply = await hub.async_send(data, wait, origin="panel")
        return {"sent": to_hex(data), "reply": to_hex(reply) if reply is not None else None,
                "timeout": wait > 0 and reply is None}
