"""A port another integration provides: send through its text entity, receive from its sensor.

Built for the HA-WF485-V3 (ESPHome firmware): `text.*_hex_data_tx` puts HEX on its RS485 /
RS232 line, `sensor.*_uart_net_hex` shows each frame the board hears and then goes back to
IDLE. Any integration that exposes a pair like that can be bound the same way, and from then
on the panel, services, entities and automations treat it like an on-board port.

Limitation of binding through a sensor: Home Assistant only records a state *change*, so the
same frame twice in a row is seen once unless the sensor goes back to its idle value between
them (the WF485 does).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import async_track_state_change_event

from .codec import parse_hex, to_hex
from .const import (
    CONF_DEVICE_ID,
    CONF_IDLE_VALUES,
    CONF_LINE_ENDING,
    CONF_RX_ENTITY,
    CONF_RX_FORMAT,
    CONF_SETTINGS_ENTITY,
    CONF_STATUS_ENTITY,
    CONF_TX_ECHO_ENTITY,
    CONF_TX_ENTITY,
    CONF_TX_FORMAT,
    DOMAIN,
    EXTERNAL_DEFAULTS,
    EXTERNAL_LATENCY,
    LINE_ENDINGS,
)
from .hub import Hub

_LOGGER = logging.getLogger(__name__)
SEND_SPACING = 0.05  # s between two sends, so the board puts them on the line as separate frames
_NOT_DATA = {"", STATE_UNKNOWN, STATE_UNAVAILABLE}


class _Counters:
    """The counters a SerialPort keeps, for the same diagnostic sensors."""

    def __init__(self) -> None:
        self.rx_bytes = self.tx_bytes = self.rx_frames = self.tx_frames = 0


class ExternalHub(Hub):
    """Bytes in and out through another integration's entities."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry)
        opts = {**EXTERNAL_DEFAULTS, **entry.options}
        self.tx_entity: str = opts[CONF_TX_ENTITY]
        self.rx_entity: str = opts[CONF_RX_ENTITY]
        self.tx_format: str = opts[CONF_TX_FORMAT]
        self.rx_format: str = opts[CONF_RX_FORMAT]
        self.tx_echo_entity: str | None = opts.get(CONF_TX_ECHO_ENTITY) or None
        self.settings_entity: str | None = opts.get(CONF_SETTINGS_ENTITY) or None
        self.status_entity: str | None = opts.get(CONF_STATUS_ENTITY) or None
        self.idle = {v.strip().casefold() for v in str(opts[CONF_IDLE_VALUES]).split(",")} | _NOT_DATA
        self.line_ending = LINE_ENDINGS.get(opts[CONF_LINE_ENDING], b"")
        self.io = _Counters()
        self._waiters: list[asyncio.Future[bytes]] = []
        self._send_lock = asyncio.Lock()
        self._state_unsub = None

    # ---- what the port looks like ---------------------------------------------------
    def _device(self) -> dr.DeviceEntry | None:
        device_id = self.entry.data.get(CONF_DEVICE_ID)
        return dr.async_get(self.hass).async_get(device_id) if device_id else None

    @property
    def model(self) -> str:
        device = self._device()
        if device is not None:
            return f"{device.name_by_user or device.name} ({device.model or 'external'})"
        return f"{self.tx_entity} / {self.rx_entity}"

    @property
    def via_device_id(self) -> str | None:
        device = self._device()
        return device.id if device is not None else None

    @property
    def settings(self) -> str:
        state = self.hass.states.get(self.settings_entity) if self.settings_entity else None
        return "" if state is None or state.state in _NOT_DATA else state.state

    def counters(self) -> dict[str, Any]:
        io = self.io
        return {"rx_frames": io.rx_frames, "tx_frames": io.tx_frames,
                "rx_bytes": io.rx_bytes, "tx_bytes": io.tx_bytes}

    def info(self) -> dict[str, Any]:
        return {**super().info(), "tx_entity": self.tx_entity, "rx_entity": self.rx_entity}

    def _online(self) -> bool:
        for entity_id in (self.tx_entity, self.rx_entity):
            state = self.hass.states.get(entity_id)
            if state is None or state.state == STATE_UNAVAILABLE:
                return False
        if self.status_entity:
            state = self.hass.states.get(self.status_entity)
            if state is not None and state.state == "off":
                return False
        return True

    # ---- open / close ---------------------------------------------------------------
    async def _async_open(self) -> None:
        missing = [e for e in (self.tx_entity, self.rx_entity) if self.hass.states.get(e) is None]
        if missing:
            raise OSError(f"entity not found: {', '.join(missing)}")
        watch = [e for e in (self.rx_entity, self.tx_entity, self.tx_echo_entity, self.status_entity) if e]
        self._state_unsub = async_track_state_change_event(self.hass, watch, self._on_state)

    async def _async_close(self) -> None:
        if self._state_unsub:
            self._state_unsub()
            self._state_unsub = None
        for fut in self._waiters:
            if not fut.done():
                fut.set_exception(OSError("port closed"))

    async def async_start(self) -> None:
        await super().async_start()
        self.available = self._online()  # the bound device may still be connecting

    # ---- receive --------------------------------------------------------------------
    @callback
    def _on_state(self, event: Event[EventStateChangedData]) -> None:
        new, old = event.data["new_state"], event.data["old_state"]
        if (
            event.data["entity_id"] == self.rx_entity
            and new is not None
            and new.state.casefold() not in self.idle
            # A device reconnecting replays its last value: only a change while online is a frame.
            and old is not None
            and old.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
            and old.state != new.state
        ):
            self._on_value(new.state)
        online = self._online()
        if online != self.available:
            self.available = online
            self.notify("availability")

    def _decode(self, value: str) -> bytes | None:
        if self.rx_format == "text":
            return value.encode()
        try:
            return parse_hex(value)
        except ValueError:
            _LOGGER.debug("%s: %s is not HEX: %r", self.name, self.rx_entity, value)
            return None

    @callback
    def _on_value(self, value: str) -> None:
        data = self._decode(value)
        if not data:
            return
        self.io.rx_bytes += len(data)
        self.io.rx_frames += 1
        for fut in self._waiters:
            if not fut.done():
                fut.set_result(data)
        self._received(data)

    # ---- transmit -------------------------------------------------------------------
    def _encode(self, data: bytes) -> str:
        if self.tx_format == "text":
            return data.decode("utf-8", "replace")
        if self.tx_format == "hex":
            return data.hex().upper()
        return to_hex(data)

    async def async_send(self, data: bytes, wait: float = 0, origin: str = "service") -> bytes | None:
        """Send bytes; with wait > 0 return the next received frame (None on timeout)."""
        if not data:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="no_payload")
        if not self.available:
            raise self._error("not_available")
        value = self._encode(data)
        state = self.hass.states.get(self.tx_entity)
        limit = int(state.attributes.get("max", 255)) if state is not None else 255
        if len(value) > limit:
            raise self._error("too_long", limit=str(limit))
        fut: asyncio.Future[bytes] | None = None
        # With a wait, the line stays ours until the answer (or the timeout): a request sent meanwhile
        # would collide with the answer on a half-duplex RS485 line.
        async with self._send_lock:
            if wait > 0:
                fut = self.hass.loop.create_future()
                self._waiters.append(fut)
            try:
                await self.hass.services.async_call(
                    "text", "set_value", {"entity_id": self.tx_entity, "value": value}, blocking=True)
                self.io.tx_bytes += len(data)
                self.io.tx_frames += 1
                self._sent(data, origin)
                if fut is None:
                    await asyncio.sleep(SEND_SPACING)
                    return None
                try:  # the device answers in time, but the answer travels through the other integration
                    return await asyncio.wait_for(fut, wait + EXTERNAL_LATENCY)
                except TimeoutError:
                    return None
            except HomeAssistantError as err:
                raise self._error("send_failed", error=str(err)) from err
            finally:
                if fut is not None:
                    self._waiters.remove(fut)
