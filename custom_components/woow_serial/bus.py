"""The frame bus: every port publishes what it hears and sends; the admin layer listens.

Ports never know who is listening, so a port works the same with or without the panel.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import logging
import time
from typing import TYPE_CHECKING

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback

from .const import DOMAIN

if TYPE_CHECKING:
    from .hub import Hub

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class BusFrame:
    """One frame seen on one port, in either direction."""

    port_id: str  # config entry id of the port
    direction: str  # "rx" or "tx"
    data: bytes
    origin: str | None = None  # tx: "service", "entity", "panel", "device:<id>" ...
    time: float = field(default_factory=time.time)

    @property
    def key(self) -> str:
        """Identity of the content, the same on every port."""
        return self.data.hex()


class FrameBus:
    """Ports in, listeners out. One per Home Assistant instance."""

    def __init__(self) -> None:
        self.ports: dict[str, Hub] = {}
        self._frame_subs: list[Callable[[BusFrame], None]] = []
        self._port_subs: list[Callable[[str], None]] = []

    @callback
    def subscribe(self, cb: Callable[[BusFrame], None]) -> CALLBACK_TYPE:
        self._frame_subs.append(cb)
        return lambda: self._frame_subs.remove(cb)

    @callback
    def subscribe_ports(self, cb: Callable[[str], None]) -> CALLBACK_TYPE:
        """cb(port_id) when a port comes, goes, or changes availability / counters."""
        self._port_subs.append(cb)
        return lambda: self._port_subs.remove(cb)

    @callback
    def publish(self, frame: BusFrame) -> None:
        for cb in list(self._frame_subs):
            try:
                cb(frame)
            except Exception:  # a listener bug must never take the port down
                _LOGGER.exception("Frame listener failed on %s", frame)

    @callback
    def add_port(self, hub: Hub) -> None:
        self.ports[hub.entry.entry_id] = hub
        self.port_changed(hub.entry.entry_id)

    @callback
    def remove_port(self, port_id: str) -> None:
        if self.ports.pop(port_id, None) is not None:
            self.port_changed(port_id)

    @callback
    def port_changed(self, port_id: str) -> None:
        for cb in list(self._port_subs):
            try:
                cb(port_id)
            except Exception:
                _LOGGER.exception("Port listener failed")


def get_bus(hass: HomeAssistant) -> FrameBus:
    data = hass.data.setdefault(DOMAIN, {})
    if "bus" not in data:
        data["bus"] = FrameBus()
    return data["bus"]
