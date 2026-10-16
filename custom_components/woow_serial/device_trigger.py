"""Device triggers: "<keypad> → <button> pressed" in the automation editor.

Follows HAIR's device_trigger.py: the editor stores a trigger's subtype as the button's *name*,
so a rename would strand every automation built on the old name. A button therefore keeps its
earlier names (Button.alias_history), and a subtype resolves to the current name first, then
to the history. Listening is delegated to Home Assistant's own event trigger on the
woow_serial_button event, filtered on the button id.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, EVENT_BUTTON
from .devices import Device

CONF_SUBTYPE = "subtype"
TRIGGER_TYPE = "button_pressed"
TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend({
    vol.Required(CONF_TYPE): vol.In([TRIGGER_TYPE]),
    vol.Required(CONF_SUBTYPE): str,
})


def _keypad_id(hass: HomeAssistant, device_id: str) -> str | None:
    """Our device id behind a Home Assistant device id (from its identifiers)."""
    entry = dr.async_get(hass).async_get(device_id)
    if entry is None:
        return None
    for domain, identifier in entry.identifiers:
        if domain == DOMAIN and identifier.startswith("device_"):
            return identifier[len("device_"):]
    return None


def _keypad(hass: HomeAssistant, device_id: str) -> Device | None:
    admin = hass.data.get(DOMAIN, {}).get("admin")
    keypad_id = _keypad_id(hass, device_id)
    device = admin.devices.devices.get(keypad_id) if admin is not None and keypad_id else None
    return device if device is not None and device.type == "keypad" else None


def _resolve(keypad: Device, subtype: str) -> str | None:
    """Current names win; only then the names buttons had before."""
    for button in keypad.buttons:
        if button.name == subtype:
            return button.id
    for button in keypad.buttons:
        if subtype in button.alias_history:
            return button.id
    return None


async def async_get_triggers(hass: HomeAssistant, device_id: str) -> list[dict[str, Any]]:
    keypad = _keypad(hass, device_id)
    if keypad is None:
        return []
    return [
        {CONF_PLATFORM: "device", CONF_DEVICE_ID: device_id, CONF_DOMAIN: DOMAIN,
         CONF_TYPE: TRIGGER_TYPE, CONF_SUBTYPE: button.name}
        for button in keypad.buttons
    ]


async def async_validate_trigger_config(hass: HomeAssistant, config: ConfigType) -> ConfigType:
    """Permissive, as HA expects: a renamed or deleted button must not fail validation at startup."""
    return TRIGGER_SCHEMA(config)


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    config = TRIGGER_SCHEMA(config)
    keypad = _keypad(hass, config[CONF_DEVICE_ID])
    button_id = _resolve(keypad, config[CONF_SUBTYPE]) if keypad is not None else None
    if button_id is not None:
        event_data: dict[str, Any] = {"button_id": button_id}
    else:
        # Not resolvable right now (panel entry not loaded yet, or the button is gone): match by
        # keypad and name, which still fires for a button that keeps its name.
        event_data = {"device_id": _keypad_id(hass, config[CONF_DEVICE_ID]) or "-", "button": config[CONF_SUBTYPE]}
    event_config = event_trigger.TRIGGER_SCHEMA({
        event_trigger.CONF_PLATFORM: "event",
        event_trigger.CONF_EVENT_TYPE: EVENT_BUTTON,
        event_trigger.CONF_EVENT_DATA: event_data,
    })
    return await event_trigger.async_attach_trigger(hass, event_config, action, trigger_info, platform_type="device")
