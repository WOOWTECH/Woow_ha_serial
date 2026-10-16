"""Base entity: one device per port, pushed updates from the hub."""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .hub import Hub


class WoowSerialEntity(Entity):
    """Entity bound to a port (SerialHub or ExternalHub)."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _updates_on: tuple[str, ...] = ()

    def __init__(self, hub: Hub, key: str, platform: str) -> None:
        self.hub = hub
        self._attr_translation_key = key
        self._attr_unique_id = f"{hub.entry.entry_id}_{key}"
        self.entity_id = f"{platform}.{hub.slug}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, hub.entry.entry_id)},
            name=hub.name,
            manufacturer="WOOWTECH",
            model=hub.model,
        )
        if hub.via_device_id is not None:  # a bound port hangs under the device that carries it
            self._attr_device_info["via_device_id"] = hub.via_device_id

    @property
    def available(self) -> bool:
        return self.hub.available

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._refresh()
        self.async_on_remove(self.hub.add_listener(self._hub_update))

    @callback
    def _hub_update(self, what: str) -> None:
        if what == "availability":
            self.async_write_ha_state()
        elif what in self._updates_on:
            self._refresh(what)
            self.async_write_ha_state()

    @callback
    def _refresh(self, what: str = "") -> None:
        """Copy hub data into _attr_* (subclasses)."""
