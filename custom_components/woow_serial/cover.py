"""Covers: managed devices of type cover (curtains, blinds, screens)."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    # Only the admin entry forwards this platform; its device manager adds and removes the entities.
    entry.runtime_data.devices.register_platform("cover", async_add_entities)
