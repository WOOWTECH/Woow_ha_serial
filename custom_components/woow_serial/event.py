"""Event entities: a port's "received" event; keypads of the panel (see managed.ManagedKeypad)."""

from __future__ import annotations

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from .codec import describe
from .const import KIND_HUB
from .entity import WoowSerialEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    hub = entry.runtime_data
    if hub.kind == KIND_HUB:  # keypads of managed devices
        hub.devices.register_platform("event", async_add_entities)
        return
    async_add_entities([Received(hub, "rx")])


class Received(WoowSerialEntity, EventEntity):
    """hex / text / length of the frame."""

    _attr_event_types = ["frame"]
    _attr_icon = "mdi:message-arrow-left-outline"
    _updates_on = ("rx",)

    def __init__(self, hub, key: str) -> None:
        super().__init__(hub, key, "event")

    @callback
    def _refresh(self, what: str = "") -> None:
        if what != "rx" or not self.hub.last_rx:
            return
        payload, when = self.hub.last_rx
        self._trigger_event("frame", describe(payload))
