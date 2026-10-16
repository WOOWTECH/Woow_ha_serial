"""Text entities: type HEX or text and it is sent."""

from __future__ import annotations

from homeassistant.components.text import TextEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .codec import HEX_PATTERN, parse_hex, to_hex, unescape
from .const import DOMAIN
from .entity import WoowSerialEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    hub = entry.runtime_data
    async_add_entities([SendHex(hub), SendText(hub)])


def _invalid(key: str, err: Exception) -> ServiceValidationError:
    return ServiceValidationError(translation_domain=DOMAIN, translation_key=key,
                                  translation_placeholders={"error": str(err)})


class _SendEntity(WoowSerialEntity, TextEntity):
    _attr_native_max = 255
    _attr_icon = "mdi:send"

    def __init__(self, hub, key: str) -> None:
        super().__init__(hub, key, "text")
        self._attr_native_value = ""


class SendHex(_SendEntity):
    """Bytes as HEX, e.g. A5 5A 01 02."""

    _attr_pattern = HEX_PATTERN

    def __init__(self, hub) -> None:
        super().__init__(hub, "send_hex")

    async def async_set_value(self, value: str) -> None:
        try:
            data = parse_hex(value)
        except ValueError as err:
            raise _invalid("bad_hex", err) from err
        await self.hub.async_send(data, origin="entity")
        tidy = to_hex(data)
        self._attr_native_value = tidy if len(tidy) <= self.native_max else value
        self.async_write_ha_state()


class SendText(_SendEntity):
    r"""Text with \r \n \xHH escapes; the port's line ending is appended."""

    def __init__(self, hub) -> None:
        super().__init__(hub, "send_text")

    async def async_set_value(self, value: str) -> None:
        try:
            data = unescape(value)
        except ValueError as err:
            raise _invalid("bad_text", err) from err
        await self.hub.async_send(data + self.hub.line_ending, origin="entity")
        self._attr_native_value = value
        self.async_write_ha_state()
