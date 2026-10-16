"""Runtime objects tying one port to Home Assistant: state, bus events, listeners."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.util import dt as dt_util, slugify

from .bus import BusFrame, get_bus
from .codec import describe
from .const import (
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_ECHO_FILTER,
    CONF_FRAME_GAP,
    CONF_KIND,
    CONF_LINE_ENDING,
    CONF_LOOP_FLUSH,
    CONF_PARITY,
    CONF_PORT,
    CONF_STOPBITS,
    DOMAIN,
    EVENT_FRAME,
    LINE_ENDINGS,
    SERIAL_DEFAULTS,
)
from .serial_port import SerialConfig, SerialPort

_LOGGER = logging.getLogger(__name__)
RETRY = 10  # seconds between reopen attempts after a port is lost


class Hub:
    """What every port (on-board or bound) has in common."""

    has_line_errors = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.bus = get_bus(hass)
        self.available = False
        self.line_ending = b""
        self.last_rx: tuple[bytes, datetime] | None = None
        self.last_tx: tuple[bytes, datetime] | None = None
        self.line_errors: dict[str, int] | None = None
        self._listeners: list[Callable[[str], None]] = []
        self._unsubs: list[CALLBACK_TYPE] = []
        self._retry: CALLBACK_TYPE | None = None

    @property
    def kind(self) -> str:
        return self.entry.data[CONF_KIND]

    @property
    def name(self) -> str:
        return self.entry.title

    @property
    def port(self) -> str:
        return self.entry.data[CONF_PORT]

    @property
    def slug(self) -> str:
        return slugify(self.entry.title) or slugify(self.port)

    @property
    def model(self) -> str:
        return f"{self.port} ({self.entry.data.get('driver') or 'unknown'})"

    @property
    def settings(self) -> str:
        return ""

    @property
    def via_device_id(self) -> str | None:
        """Registry id of the device that carries this port (bound external ports)."""
        return None

    def counters(self) -> dict[str, Any]:
        return {}

    def info(self) -> dict[str, Any]:
        """What the panel shows on a port card."""
        return {
            "id": self.entry.entry_id,
            "name": self.name,
            "kind": self.kind,
            "port": self.port,
            "model": self.model,
            "settings": self.settings,
            "available": self.available,
            **self.counters(),
        }

    @callback
    def add_listener(self, cb: Callable[[str], None]) -> CALLBACK_TYPE:
        self._listeners.append(cb)
        return lambda: self._listeners.remove(cb)

    @callback
    def notify(self, what: str) -> None:
        for cb in list(self._listeners):
            cb(what)
        if what in ("availability", "stats"):
            self.bus.port_changed(self.entry.entry_id)

    def _error(self, key: str, **placeholders: str) -> HomeAssistantError:
        return HomeAssistantError(translation_domain=DOMAIN, translation_key=key,
                                  translation_placeholders={"name": self.name, **placeholders})

    @callback
    def _received(self, data: bytes) -> None:
        """A frame came in: entities, HA event, and the frame bus."""
        self.last_rx = (data, dt_util.utcnow())
        self.bus.publish(BusFrame(self.entry.entry_id, "rx", data))
        self.hass.bus.async_fire(EVENT_FRAME, {
            "entry_id": self.entry.entry_id, "name": self.name, "port": self.port, **describe(data),
        })
        self.notify("rx")

    @callback
    def _sent(self, data: bytes, origin: str | None = None) -> None:
        self.last_tx = (data, dt_util.utcnow())
        self.bus.publish(BusFrame(self.entry.entry_id, "tx", data, origin=origin))
        self.notify("tx")

    async def async_send(self, data: bytes, wait: float = 0, origin: str = "service") -> bytes | None:
        raise NotImplementedError

    async def _async_open(self) -> None:
        raise NotImplementedError

    async def _async_close(self) -> None:
        raise NotImplementedError

    async def async_start(self) -> None:
        await self._async_open()
        self.available = True
        self.bus.add_port(self)

    async def async_stop(self) -> None:
        self.bus.remove_port(self.entry.entry_id)
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._retry:
            self._retry()
            self._retry = None
        await self._async_close()

    @callback
    def _on_lost(self, err: Exception) -> None:
        _LOGGER.warning("%s (%s) stopped working: %s; retrying every %ss", self.name, self.port, err, RETRY)
        self.available = False
        self.notify("availability")
        self._schedule_retry()

    @callback
    def _schedule_retry(self) -> None:
        self._retry = async_call_later(self.hass, RETRY, self._async_retry)

    async def _async_retry(self, _now: datetime) -> None:
        self._retry = None
        try:
            await self._async_close()
            await self._async_open()
        except (OSError, ValueError) as err:
            _LOGGER.debug("%s: reopen failed: %s", self.name, err)
            self._schedule_retry()
            return
        _LOGGER.info("%s (%s) is back", self.name, self.port)
        self.available = True
        self.notify("availability")


class SerialHub(Hub):
    """An on-board RS485 / RS232 port."""

    has_line_errors = True

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry)
        opts = {**SERIAL_DEFAULTS, **entry.options}
        self.cfg = SerialConfig(
            path=self.port,
            baudrate=int(opts[CONF_BAUDRATE]),
            bytesize=int(opts[CONF_BYTESIZE]),
            parity=opts[CONF_PARITY],
            stopbits=int(opts[CONF_STOPBITS]),
            frame_gap_ms=int(opts[CONF_FRAME_GAP]),
            echo_filter=bool(opts[CONF_ECHO_FILTER]),
            loop_flush=bool(opts[CONF_LOOP_FLUSH]),
        )
        self.line_ending = LINE_ENDINGS.get(opts[CONF_LINE_ENDING], b"")
        self.io = SerialPort(hass.loop, self.cfg, self._received, self._sent, self._on_lost)

    @property
    def settings(self) -> str:
        return f"{self.cfg.baudrate} {self.cfg.bytesize}{self.cfg.parity}{self.cfg.stopbits}"

    def counters(self) -> dict[str, Any]:
        io = self.io
        return {"rx_frames": io.rx_frames, "tx_frames": io.tx_frames, "rx_bytes": io.rx_bytes,
                "tx_bytes": io.tx_bytes, "errors": sum((self.line_errors or {}).values())}

    async def _async_open(self) -> None:
        await self.io.open()

    async def _async_close(self) -> None:
        await self.io.close()

    async def async_start(self) -> None:
        await super().async_start()
        self._unsubs.append(async_track_time_interval(self.hass, self._poll, timedelta(seconds=30)))
        self._poll()

    @callback
    def _poll(self, _now: datetime | None = None) -> None:
        self.line_errors = self.io.line_errors()
        self.notify("stats")

    async def async_send(self, data: bytes, wait: float = 0, origin: str = "service") -> bytes | None:
        """Send bytes; with wait > 0 return the next received frame (None on timeout)."""
        if not data:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="no_payload")
        if not self.io.is_open:
            raise self._error("not_available")
        try:
            if wait > 0:
                return await self.io.request(data, wait, origin)
            await self.io.write(data, origin)
        except OSError as err:
            raise self._error("send_failed", error=str(err)) from err
        return None
