"""Sensors: last received / sent data and counters of a port; sensors of managed devices."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfInformation
from homeassistant.core import HomeAssistant, callback

from .codec import clip, describe, printable, to_hex
from .const import KIND_HUB
from .entity import WoowSerialEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    hub = entry.runtime_data
    if hub.kind == KIND_HUB:  # sensors of managed devices
        hub.devices.register_platform("sensor", async_add_entities)
        return
    entities = [
        ReceivedHex(hub), ReceivedText(hub), SentHex(hub),
        SerialCounter(hub, "rx_bytes"), SerialCounter(hub, "tx_bytes"),
    ]
    if hub.has_line_errors:  # on-board UARTs only; a bound port has no line counters
        entities.append(LineErrors(hub))
    async_add_entities(entities)


class _Sensor(WoowSerialEntity, SensorEntity):
    def __init__(self, hub, key: str) -> None:
        super().__init__(hub, key, "sensor")


class ReceivedHex(_Sensor):
    """Last received frame as HEX; full data in the attributes."""

    _attr_icon = "mdi:download"
    _updates_on = ("rx",)

    def __init__(self, hub) -> None:
        super().__init__(hub, "rx_hex")

    @callback
    def _refresh(self, what: str = "") -> None:
        if self.hub.last_rx:
            data, when = self.hub.last_rx
            self._attr_native_value = clip(to_hex(data))
            self._attr_extra_state_attributes = {**describe(data), "time": when.isoformat()}


class ReceivedText(_Sensor):
    """Last received frame as readable text (non-printable bytes as escapes)."""

    _attr_icon = "mdi:text-box-outline"
    _updates_on = ("rx",)

    def __init__(self, hub) -> None:
        super().__init__(hub, "rx_text")

    @callback
    def _refresh(self, what: str = "") -> None:
        if self.hub.last_rx:
            self._attr_native_value = clip(printable(self.hub.last_rx[0]))


class SentHex(_Sensor):
    """Last frame this port sent (from any entity, service or automation)."""

    _attr_icon = "mdi:upload"
    _updates_on = ("tx",)

    def __init__(self, hub) -> None:
        super().__init__(hub, "tx_hex")

    @callback
    def _refresh(self, what: str = "") -> None:
        if self.hub.last_tx:
            data, when = self.hub.last_tx
            self._attr_native_value = clip(to_hex(data))
            self._attr_extra_state_attributes = {**describe(data), "time": when.isoformat()}


class SerialCounter(_Sensor):
    """Bytes received / sent since HA started (after echo filtering)."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_native_unit_of_measurement = UnitOfInformation.BYTES
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _updates_on = ("stats",)

    @callback
    def _refresh(self, what: str = "") -> None:
        io = self.hub.io
        if self._attr_translation_key == "rx_bytes":
            self._attr_native_value = io.rx_bytes
            self._attr_extra_state_attributes = {"frames": io.rx_frames}
        else:
            self._attr_native_value = io.tx_bytes
            self._attr_extra_state_attributes = {"frames": io.tx_frames}


class LineErrors(_Sensor):
    """Kernel framing / overrun / parity / break counters for the UART."""

    _attr_icon = "mdi:alert-circle-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _updates_on = ("stats",)

    def __init__(self, hub) -> None:
        super().__init__(hub, "line_errors")

    @callback
    def _refresh(self, what: str = "") -> None:
        errors = self.hub.line_errors
        self._attr_native_value = sum(errors.values()) if errors else None
        self._attr_extra_state_attributes = {**(errors or {}), "settings": self.hub.settings}
