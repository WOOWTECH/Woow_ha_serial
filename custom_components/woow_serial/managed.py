"""Entities of managed devices: one main entity by device type, a button per command, sensors.

Every action goes through DeviceManager, which renders the mapped command and sends it on the
device's port; state comes back from the manager (optimistic, then corrected by feedback rules).
"""

from __future__ import annotations

import time
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.components.cover import ATTR_POSITION, CoverEntity, CoverEntityFeature
from homeassistant.components.event import EventEntity
from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.components.select import SelectEntity
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import STATE_ON
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .devices import DEVICE_TYPES, SENSOR_MIN_INTERVAL, Button, Command, Device, DeviceManager, SensorDef


def unique_ids(device: Device) -> list[str]:
    ids = [f"{device.id}_cmd_{c.id}" for c in device.commands]
    ids += [f"{device.id}_sensor_{s.id}" for s in device.sensors]
    platform = DEVICE_TYPES[device.type]["platform"]
    if platform:
        ids.append(f"{device.id}_main_{platform}")
    return ids


def build(manager: DeviceManager, device: Device, domain: str) -> list[Entity]:
    """Fresh entity objects of one platform for one device."""
    if domain == "button":
        return [ManagedButton(manager, device, c) for c in device.commands]
    if domain == "sensor":
        return [ManagedSensor(manager, device, s) for s in device.sensors]
    if DEVICE_TYPES[device.type]["platform"] != domain:
        return []
    return [MAIN[domain](manager, device)]


class ManagedEntity(Entity):
    """Bound to one managed device; available while its port is."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, manager: DeviceManager, device: Device, suffix: str) -> None:
        self.manager = manager
        self.device_id = device.id
        self.port_id = device.port_id
        self._attr_unique_id = f"{device.id}_{suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"device_{device.id}")},
            name=device.name,
            manufacturer=device.manufacturer or "WOOWTECH",
            model=device.model or None,
        )
        # Shown under the port it is wired to (HA 2026.8+ links devices by registry id).
        port_device = dr.async_get(manager.hass).async_get_device_by_identifier(
            (DOMAIN, device.port_id), device.port_id)
        if port_device is not None:
            self._attr_device_info["via_device_id"] = port_device.id

    @property
    def device(self) -> Device:
        return self.manager.devices[self.device_id]

    @property
    def data(self) -> dict[str, Any]:
        return self.manager.state.setdefault(self.device_id, {})

    @property
    def available(self) -> bool:
        hub = self.manager.bus.ports.get(self.port_id)
        return hub is not None and hub.available

    def has(self, action: str) -> bool:
        return action in self.device.actions

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.manager.entity_added(self, self.device_id)
        self.async_on_remove(self.manager.add_entity_listener(self.device_id, self._changed))
        self.async_on_remove(self.manager.bus.subscribe_ports(self._port_changed))

    async def async_will_remove_from_hass(self) -> None:
        self.manager.entity_removed(self, self.device_id)
        await super().async_will_remove_from_hass()

    @callback
    def _changed(self) -> None:
        self.async_write_ha_state()

    @callback
    def _port_changed(self, port_id: str) -> None:
        if port_id == self.port_id:
            self.async_write_ha_state()

    def _assumed(self, *names: str) -> bool:
        return not any(self.manager.has_feedback(self.device_id, n) for n in names)


class _MainEntity(ManagedEntity, RestoreEntity):
    """The device itself (switch, light, cover, ...), named after the device."""

    _attr_name = None
    platform_name = ""

    def __init__(self, manager: DeviceManager, device: Device) -> None:
        super().__init__(manager, device, f"main_{self.platform_name}")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        # Restore is by entity id: a device deleted and made again under the same name would inherit the
        # old one's state, so only state written since this device was created counts.
        if not self.data and last is not None and last.last_updated.timestamp() >= self.device.created:
            self.restore(last.state, last.attributes)

    def restore(self, state: str, attributes: dict[str, Any]) -> None:
        """Seed the manager's state from what HA showed before the restart (no command is sent)."""


class ManagedSwitch(_MainEntity, SwitchEntity):
    platform_name = "switch"

    @property
    def is_on(self) -> bool | None:
        return self.data.get("power")

    @property
    def assumed_state(self) -> bool:
        return self._assumed("power")

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.manager.async_action(self.device_id, "turn_on", context=self._context)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.manager.async_action(self.device_id, "turn_off", context=self._context)

    def restore(self, state: str, attributes: dict[str, Any]) -> None:
        if state in ("on", "off"):
            self.data["power"] = state == STATE_ON


class ManagedLight(_MainEntity, LightEntity):
    platform_name = "light"

    @property
    def _mode(self) -> ColorMode:
        return ColorMode.BRIGHTNESS if self.has("set_brightness") else ColorMode.ONOFF

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        return {self._mode}

    @property
    def color_mode(self) -> ColorMode:
        return self._mode

    @property
    def is_on(self) -> bool | None:
        return self.data.get("power")

    @property
    def brightness(self) -> int | None:
        return self.data.get("brightness") if self._mode == ColorMode.BRIGHTNESS else None

    @property
    def assumed_state(self) -> bool:
        return self._assumed("power", "brightness")

    async def async_turn_on(self, **kwargs: Any) -> None:
        if ATTR_BRIGHTNESS in kwargs and self.has("set_brightness"):
            await self.manager.async_action(self.device_id, "set_brightness", kwargs[ATTR_BRIGHTNESS], context=self._context)
        elif self.has("turn_on"):
            await self.manager.async_action(self.device_id, "turn_on", context=self._context)
        else:
            await self.manager.async_action(self.device_id, "set_brightness", self.data.get("brightness") or 255, context=self._context)

    async def async_turn_off(self, **kwargs: Any) -> None:
        if self.has("turn_off") or not self.has("set_brightness"):
            await self.manager.async_action(self.device_id, "turn_off", context=self._context)
        else:
            await self.manager.async_action(self.device_id, "set_brightness", 0, context=self._context)

    def restore(self, state: str, attributes: dict[str, Any]) -> None:
        if state in ("on", "off"):
            self.data["power"] = state == STATE_ON
        if isinstance(attributes.get(ATTR_BRIGHTNESS), (int, float)):
            self.data["brightness"] = attributes[ATTR_BRIGHTNESS]


class ManagedCover(_MainEntity, CoverEntity):
    platform_name = "cover"

    @property
    def supported_features(self) -> CoverEntityFeature:
        features = CoverEntityFeature(0)
        for action, flag in (("open", CoverEntityFeature.OPEN), ("close", CoverEntityFeature.CLOSE),
                             ("stop", CoverEntityFeature.STOP), ("set_position", CoverEntityFeature.SET_POSITION)):
            if self.has(action):
                features |= flag
        return features

    @property
    def current_cover_position(self) -> int | None:
        position = self.data.get("position")
        return int(position) if position is not None and self.has("set_position") else None

    @property
    def is_closed(self) -> bool | None:
        position = self.data.get("position")
        return None if position is None else position <= 0

    @property
    def assumed_state(self) -> bool:
        return self._assumed("position")

    async def async_open_cover(self, **kwargs: Any) -> None:
        await self.manager.async_action(self.device_id, "open", context=self._context)

    async def async_close_cover(self, **kwargs: Any) -> None:
        await self.manager.async_action(self.device_id, "close", context=self._context)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        await self.manager.async_action(self.device_id, "stop", context=self._context)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        await self.manager.async_action(self.device_id, "set_position", kwargs[ATTR_POSITION], context=self._context)

    def restore(self, state: str, attributes: dict[str, Any]) -> None:
        if isinstance(attributes.get("current_position"), (int, float)):
            self.data["position"] = attributes["current_position"]
        elif state in ("open", "closed"):
            self.data["position"] = 100 if state == "open" else 0


_MEDIA_FEATURES = (
    ("turn_on", MediaPlayerEntityFeature.TURN_ON), ("turn_off", MediaPlayerEntityFeature.TURN_OFF),
    ("volume_up", MediaPlayerEntityFeature.VOLUME_STEP), ("volume_down", MediaPlayerEntityFeature.VOLUME_STEP),
    ("set_volume", MediaPlayerEntityFeature.VOLUME_SET), ("mute_on", MediaPlayerEntityFeature.VOLUME_MUTE),
    ("mute_off", MediaPlayerEntityFeature.VOLUME_MUTE), ("play", MediaPlayerEntityFeature.PLAY),
    ("pause", MediaPlayerEntityFeature.PAUSE), ("stop", MediaPlayerEntityFeature.STOP),
    ("next", MediaPlayerEntityFeature.NEXT_TRACK), ("previous", MediaPlayerEntityFeature.PREVIOUS_TRACK),
)


class ManagedMediaPlayer(_MainEntity, MediaPlayerEntity):
    platform_name = "media_player"

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        features = MediaPlayerEntityFeature(0)
        for action, flag in _MEDIA_FEATURES:
            if self.has(action):
                features |= flag
        if self.device.options:
            features |= MediaPlayerEntityFeature.SELECT_SOURCE
        return features

    @property
    def state(self) -> MediaPlayerState | None:
        power = self.data.get("power")
        if power is False:
            return MediaPlayerState.OFF
        playback = {"playing": MediaPlayerState.PLAYING, "paused": MediaPlayerState.PAUSED,
                    "idle": MediaPlayerState.IDLE}.get(self.data.get("playback", ""))
        if power is None and not self.has("turn_on"):
            return playback or MediaPlayerState.ON
        return None if power is None else playback or MediaPlayerState.ON

    @property
    def volume_level(self) -> float | None:
        return self.data.get("volume")

    @property
    def is_volume_muted(self) -> bool | None:
        return self.data.get("mute")

    @property
    def source(self) -> str | None:
        return self.data.get("source")

    @property
    def source_list(self) -> list[str] | None:
        return [o.name for o in self.device.options] or None

    @property
    def assumed_state(self) -> bool:
        return self._assumed("power", "volume", "mute", "source")

    async def async_turn_on(self) -> None:
        await self.manager.async_action(self.device_id, "turn_on", context=self._context)

    async def async_turn_off(self) -> None:
        await self.manager.async_action(self.device_id, "turn_off", context=self._context)

    async def async_volume_up(self) -> None:
        await self.manager.async_action(self.device_id, "volume_up", context=self._context)

    async def async_volume_down(self) -> None:
        await self.manager.async_action(self.device_id, "volume_down", context=self._context)

    async def async_set_volume_level(self, volume: float) -> None:
        await self.manager.async_action(self.device_id, "set_volume", volume, context=self._context)

    async def async_mute_volume(self, mute: bool) -> None:
        await self.manager.async_action(self.device_id, "mute_on" if mute else "mute_off", context=self._context)

    async def async_media_play(self) -> None:
        await self.manager.async_action(self.device_id, "play", context=self._context)

    async def async_media_pause(self) -> None:
        await self.manager.async_action(self.device_id, "pause", context=self._context)

    async def async_media_stop(self) -> None:
        await self.manager.async_action(self.device_id, "stop", context=self._context)

    async def async_media_next_track(self) -> None:
        await self.manager.async_action(self.device_id, "next", context=self._context)

    async def async_media_previous_track(self) -> None:
        await self.manager.async_action(self.device_id, "previous", context=self._context)

    async def async_select_source(self, source: str) -> None:
        await self.manager.async_option(self.device_id, source, "source", context=self._context)

    def restore(self, state: str, attributes: dict[str, Any]) -> None:
        if state in ("on", "off", "playing", "paused", "idle"):
            self.data["power"] = state != "off"
        for key, attr in (("volume", "volume_level"), ("mute", "is_volume_muted"), ("source", "source")):
            if attributes.get(attr) is not None:
                self.data[key] = attributes[attr]


class ManagedSelect(_MainEntity, SelectEntity):
    platform_name = "select"

    @property
    def options(self) -> list[str]:
        return [o.name for o in self.device.options]

    @property
    def current_option(self) -> str | None:
        option = self.data.get("option")
        return option if option in self.options else None

    async def async_select_option(self, option: str) -> None:
        await self.manager.async_option(self.device_id, option, "option", context=self._context)

    def restore(self, state: str, attributes: dict[str, Any]) -> None:
        if state in self.options:
            self.data["option"] = state


class ManagedKeypad(_MainEntity, EventEntity):
    """A keypad: one event type per button; fires on every press (device triggers fire alongside)."""

    platform_name = "event"
    _attr_icon = "mdi:gesture-tap-button"

    @property
    def event_types(self) -> list[str]:
        return [b.name for b in self.device.buttons]

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.manager.add_button_listener(self.device_id, self._pressed))

    @callback
    def _pressed(self, button: Button, data: dict[str, Any]) -> None:
        if button.name in self.event_types:
            self._trigger_event(button.name, {k: v for k, v in data.items() if k not in ("device_id", "keypad")})
            self.async_write_ha_state()


class ManagedButton(ManagedEntity, ButtonEntity):
    """One per command: press to send it (handy on dashboards and in scripts)."""

    def __init__(self, manager: DeviceManager, device: Device, command: Command) -> None:
        super().__init__(manager, device, f"cmd_{command.id}")
        self.command_id = command.id
        self._attr_name = command.name

    async def async_press(self) -> None:
        await self.manager.async_command(self.device_id, self.command_id, context=self._context)


class ManagedSensor(ManagedEntity, SensorEntity):
    """A value read out of the device's frames (status replies, CAN signals)."""

    def __init__(self, manager: DeviceManager, device: Device, sensor: SensorDef) -> None:
        super().__init__(manager, device, f"sensor_{sensor.id}")
        self.key = f"sensor:{sensor.id}"
        self._attr_name = sensor.name
        self._attr_native_unit_of_measurement = sensor.unit or None
        self._attr_state_class = SensorStateClass.MEASUREMENT
        try:
            self._attr_device_class = SensorDeviceClass(sensor.device_class) if sensor.device_class else None
        except ValueError:
            self._attr_device_class = None
        if sensor.precision is not None:
            self._attr_suggested_display_precision = sensor.precision
        self._last_write = 0.0
        self._pending = None

    @property
    def native_value(self) -> Any:
        return self.data.get(self.key)

    @callback
    def _changed(self) -> None:
        # At most one write per SENSOR_MIN_INTERVAL; the latest value is what gets written.
        if self._pending is not None:
            return
        wait = SENSOR_MIN_INTERVAL - (time.monotonic() - self._last_write)
        if wait <= 0:
            self._write()
        else:
            self._pending = async_call_later(self.hass, wait, self._delayed)

    @callback
    def _delayed(self, _now: Any) -> None:
        self._pending = None
        self._write()

    @callback
    def _write(self) -> None:
        self._last_write = time.monotonic()
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        if self._pending is not None:
            self._pending()
            self._pending = None
        await super().async_will_remove_from_hass()


MAIN: dict[str, type[_MainEntity]] = {
    "switch": ManagedSwitch,
    "light": ManagedLight,
    "cover": ManagedCover,
    "media_player": ManagedMediaPlayer,
    "select": ManagedSelect,
    "event": ManagedKeypad,
}
