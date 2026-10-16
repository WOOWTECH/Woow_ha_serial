"""Managed devices (HAIR's Devices): commands, action mapping, state feedback, sensors, polling.

A device lives on one port. Its commands are templates (template.py); its type decides which
Home Assistant entity stands for it and which actions of that entity map to commands. Every
frame its port receives runs through the device's rules (state feedback) and sensors, so a
device that reports its status keeps its entity truthful, unlike infrared where HAIR has to
assume. Devices are kept in .storage/woow_serial.devices and edited from the panel.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, fields
from datetime import timedelta
import logging
import re
import time
from typing import TYPE_CHECKING, Any
import uuid

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store

from .bus import BusFrame, FrameBus
from .codec import parse_hex, to_hex
from .const import DOMAIN, EVENT_BUTTON, LIVE_PUSH
from .template import Pattern, TemplateError, fields_used, render

if TYPE_CHECKING:
    from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DEVICE_TYPES: dict[str, dict[str, Any]] = {
    "switch": {"platform": "switch", "actions": ["turn_on", "turn_off"], "fields": ["power"]},
    "light": {"platform": "light", "actions": ["turn_on", "turn_off", "set_brightness"],
              "fields": ["power", "brightness"]},
    "cover": {"platform": "cover", "actions": ["open", "close", "stop", "set_position"], "fields": ["position"]},
    "media_player": {"platform": "media_player",
                     "actions": ["turn_on", "turn_off", "volume_up", "volume_down", "set_volume", "mute_on",
                                 "mute_off", "play", "pause", "stop", "next", "previous"],
                     "fields": ["power", "volume", "mute", "source", "playback"], "options": True},
    "select": {"platform": "select", "actions": [], "fields": ["option"], "options": True},
    # A wall keypad, or anything that sends frames by itself: each button is a receive pattern that
    # fires a device trigger / event, and may also drive another device directly (a binding).
    "keypad": {"platform": "event", "actions": [], "fields": [], "buttons": True},
    "other": {"platform": None, "actions": [], "fields": []},
}
# Actions that carry a value, and the state field the value belongs to.
VALUE_ACTIONS = {"set_brightness": "brightness", "set_position": "position", "set_volume": "volume"}
# Home Assistant's own scale for those fields; a device's range maps onto it (ranges, below).
HA_SCALE = {"brightness": 255, "position": 100, "volume": 1}
DEFAULT_RANGE = [0, 100]
_CAPTURE_REF = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
SENSOR_MIN_INTERVAL = 1.0  # s between state writes of one sensor
TOGGLE = "toggle"  # binding action: turn_off when the target is on, turn_on otherwise
LOOP_LIMIT, LOOP_WINDOW, LOOP_PAUSE = 10, 5.0, 60.0  # a binding firing this often is paused (runaway guard)
ALIAS_HISTORY = 10


class DeviceError(ValueError):
    """A device definition that cannot be saved; code + info are translated by the panel."""

    def __init__(self, code: str, **info: Any) -> None:
        super().__init__(f"{code}: {info}")
        self.code = code
        self.info = info

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, **self.info}


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def _load(cls, raw: dict[str, Any]):
    names = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in raw.items() if k in names})


@dataclass
class Command:
    id: str
    name: str
    payload: str
    format: str = "hex"  # hex | text | can
    repeat: int = 1
    gap_ms: int = 100  # between repeats
    wait_ms: int = 0  # wait for a reply after the last repeat (queries)


@dataclass
class Rule:
    """When a received frame matches `pattern`, set `field` to `value` (a literal or "{capture}")."""

    id: str
    pattern: str
    format: str = "hex"
    field: str = "power"
    value: str = ""


@dataclass
class SensorDef:
    """A number read out of matching frames: capture * scale + offset."""

    id: str
    name: str
    pattern: str
    format: str = "hex"
    capture: str = "value"
    scale: float = 1.0
    offset: float = 0.0
    unit: str = ""
    device_class: str = ""
    precision: int | None = None


@dataclass
class Option:
    """A media player source or a select option, and the command that picks it."""

    name: str
    command: str


@dataclass
class Button:
    """A keypad button: the frame it sends, and optionally what it drives by itself."""

    id: str
    name: str
    pattern: str
    format: str = "hex"
    debounce_ms: int = 300  # repeats within this window (a held key) count as one press
    target: str = ""  # device id this button drives ("" = triggers only)
    action: str = ""  # turn_on / toggle / open / set_position / ..., "command:<id>" or "option:<name>"
    value: float | None = None  # percent, for set_* actions
    alias_history: list[str] = field(default_factory=list)  # earlier names (device triggers keep working)


@dataclass
class Device:
    id: str
    name: str
    type: str
    port_id: str
    manufacturer: str = ""
    model: str = ""
    params: dict[str, str] = field(default_factory=dict)  # template parameters (HEX), e.g. addr
    commands: list[Command] = field(default_factory=list)
    actions: dict[str, str] = field(default_factory=dict)  # action -> command id
    options: list[Option] = field(default_factory=list)
    rules: list[Rule] = field(default_factory=list)
    sensors: list[SensorDef] = field(default_factory=list)
    buttons: list[Button] = field(default_factory=list)
    ranges: dict[str, list[float]] = field(default_factory=dict)  # field -> [device value at 0, at full]
    poll_command: str = ""
    poll_interval: int = 0  # s; 0 = no polling

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Device:
        device = _load(cls, raw)
        device.commands = [_load(Command, c) for c in raw.get("commands", [])]
        device.options = [_load(Option, o) for o in raw.get("options", [])]
        device.rules = [_load(Rule, r) for r in raw.get("rules", [])]
        device.sensors = [_load(SensorDef, s) for s in raw.get("sensors", [])]
        device.buttons = [_load(Button, b) for b in raw.get("buttons", [])]
        device.params = {str(k): str(v) for k, v in (raw.get("params") or {}).items()}
        device.actions = {str(k): str(v) for k, v in (raw.get("actions") or {}).items() if v}
        device.ranges = {str(k): [float(v[0]), float(v[1])] for k, v in (raw.get("ranges") or {}).items()}
        return device

    def command(self, command_id: str) -> Command | None:
        return next((c for c in self.commands if c.id == command_id), None)

    def button(self, button_id: str) -> Button | None:
        return next((b for b in self.buttons if b.id == button_id), None)

    def range(self, name: str) -> list[float]:
        return self.ranges.get(name) or DEFAULT_RANGE


# ---- value conversions ----------------------------------------------------------------
def to_device(device: Device, name: str, ha_value: float) -> int:
    """A Home Assistant value (brightness 0-255, position 0-100, volume 0-1) in device units."""
    low, high = device.range(name)
    return round(low + (high - low) * max(0.0, min(1.0, ha_value / HA_SCALE[name])))


def from_device(device: Device, name: str, raw: float) -> float:
    low, high = device.range(name)
    if high == low:
        return 0.0
    share = max(0.0, min(1.0, (raw - low) / (high - low)))
    value = share * HA_SCALE[name]
    return value if name == "volume" else round(value)


def truthy(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    if text in ("on", "true", "yes", "open", "1", "01"):
        return True
    if text in ("off", "false", "no", "closed", "0", "00"):
        return False
    try:
        return float(text) != 0
    except ValueError:
        return None


# ---- validation -------------------------------------------------------------------------
def validate(device: Device) -> None:
    """Raise DeviceError for the first problem, naming the item it is in."""
    if not device.name.strip():
        raise DeviceError("no_name")
    spec = DEVICE_TYPES.get(device.type)
    if spec is None:
        raise DeviceError("bad_type", type=device.type)
    if not device.port_id:
        raise DeviceError("no_port")
    for name, value in device.params.items():
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise DeviceError("bad_param_name", param=name)
        try:
            parse_hex(value)
        except ValueError as err:
            raise DeviceError("bad_param", param=name, value=value) from err
    variables = {**device.params, "value": 0}
    names = set()
    for command in device.commands:
        if not command.name.strip():
            raise DeviceError("command_no_name")
        if command.name in names:
            raise DeviceError("command_duplicate", command=command.name)
        names.add(command.name)
        if command.format not in ("hex", "text"):
            raise DeviceError("command_format", command=command.name, format=command.format)
        try:
            render(command.payload, command.format, variables)
        except TemplateError as err:
            raise DeviceError("command_template", command=command.name, template_code=err.code,
                              **{f"t_{k}": v for k, v in err.info.items()}) from err
        if not 1 <= command.repeat <= 20 or not 0 <= command.gap_ms <= 10000 or not 0 <= command.wait_ms <= 60000:
            raise DeviceError("command_limits", command=command.name)
    ids = {c.id for c in device.commands}
    for action, command_id in device.actions.items():
        if action not in spec["actions"]:
            raise DeviceError("bad_action", action=action)
        if command_id not in ids:
            raise DeviceError("action_command", action=action)
    if device.options and not spec.get("options"):
        raise DeviceError("no_options_for_type")
    option_names = set()
    for option in device.options:
        if not option.name.strip() or option.name in option_names:
            raise DeviceError("option_name", option=option.name)
        option_names.add(option.name)
        if option.command not in ids:
            raise DeviceError("option_command", option=option.name)
    for rule in device.rules:
        if rule.field not in spec["fields"]:
            raise DeviceError("rule_field", field=rule.field)
        pattern = _pattern(rule.pattern, rule.format, device.params, "rule")
        for ref in _CAPTURE_REF.findall(rule.value):
            if ref not in _captures(pattern):
                raise DeviceError("rule_capture", capture=ref)
    for sensor in device.sensors:
        if not sensor.name.strip():
            raise DeviceError("sensor_no_name")
        pattern = _pattern(sensor.pattern, sensor.format, device.params, "sensor", sensor=sensor.name)
        if sensor.capture not in _captures(pattern):
            raise DeviceError("sensor_capture", sensor=sensor.name, capture=sensor.capture)
    if device.buttons and not spec.get("buttons"):
        raise DeviceError("no_buttons_for_type")
    button_names = set()
    for button in device.buttons:
        if not button.name.strip() or button.name in button_names:
            raise DeviceError("button_name", button=button.name)
        button_names.add(button.name)
        _pattern(button.pattern, button.format, device.params, "button", button=button.name)
        if not 0 <= button.debounce_ms <= 10000:
            raise DeviceError("button_debounce", button=button.name)
    for name, pair in device.ranges.items():
        if name not in HA_SCALE or len(pair) != 2:
            raise DeviceError("bad_range", field=name)
    if device.poll_command:
        if device.poll_command not in ids:
            raise DeviceError("poll_command")
        if not 1 <= device.poll_interval <= 86400:
            raise DeviceError("poll_interval")


def _pattern(text: str, fmt: str, params: dict[str, str], what: str, **where: Any) -> Pattern:
    try:
        return Pattern(text, fmt, params)
    except TemplateError as err:
        raise DeviceError(f"{what}_pattern", template_code=err.code, **where,
                          **{f"t_{k}": v for k, v in err.info.items()}) from err


def binding_actions(target: Device) -> list[str]:
    """What a button may do to `target`: its mapped actions, toggle, its options and commands."""
    actions = [a for a in DEVICE_TYPES[target.type]["actions"] if a in target.actions]
    if {"turn_on", "turn_off"} <= set(actions):
        actions.insert(0, TOGGLE)
    actions += [f"option:{o.name}" for o in target.options]
    actions += [f"command:{c.id}" for c in target.commands]
    return actions


def _captures(pattern: Pattern) -> set[str]:
    if pattern.regex is not None:
        return set(pattern.regex.groupindex)
    return set(pattern.captures)


# ---- the manager ------------------------------------------------------------------------
class DeviceManager:
    """Owns the devices, their live state and their entities."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, bus: FrameBus) -> None:
        self.hass = hass
        self.entry = entry
        self.bus = bus
        self.devices: dict[str, Device] = {}
        self.state: dict[str, dict[str, Any]] = {}
        self.loaded = False
        self._store: Store[dict[str, Any]] = Store(hass, 1, f"{DOMAIN}.devices")
        self._compiled: dict[str, tuple[list[tuple[Rule, Pattern]], list[tuple[SensorDef, Pattern]],
                                        list[tuple[Button, Pattern]]]] = {}
        self._button_listeners: dict[str, list[Callable[[Button, dict[str, Any]], None]]] = {}
        self._last_press: dict[str, float] = {}  # button id -> monotonic time of the last accepted press
        self._fired: dict[str, list[float]] = {}  # button id -> recent binding runs (runaway guard)
        self._paused: dict[str, float] = {}  # button id -> binding paused until
        self._adders: dict[str, AddEntitiesCallback] = {}
        self._live: dict[str, list[Entity]] = {}  # device id -> entity objects in Home Assistant
        self._entity_listeners: dict[str, list[Callable[[], None]]] = {}
        self._polls: dict[str, CALLBACK_TYPE] = {}
        self._feed: list[Callable[[str, dict[str, Any]], None]] = []
        self._dirty_state: set[str] = set()
        self._push_handle: asyncio.TimerHandle | None = None

    # ---- persistence / lifecycle --------------------------------------------------------
    async def async_load(self) -> None:
        data = await self._store.async_load() or {}
        for raw in data.get("devices", []):
            try:
                device = Device.from_dict(raw)
                self._compile(device)
            except (DeviceError, TemplateError, KeyError, TypeError, ValueError) as err:
                _LOGGER.warning("Skipping stored device %s: %s", raw.get("name"), err)
                continue
            self.devices[device.id] = device
        self.loaded = True

    async def _async_save(self) -> None:
        await self._store.async_save({"devices": [asdict(d) for d in self.devices.values()]})

    @callback
    def start(self) -> None:
        for device in self.devices.values():
            self._start_poll(device)

    @callback
    def stop(self) -> None:
        for unsub in self._polls.values():
            unsub()
        self._polls.clear()
        if self._push_handle is not None:
            self._push_handle.cancel()
            self._push_handle = None

    def _compile(self, device: Device) -> None:
        rules = [(r, Pattern(r.pattern, r.format, device.params)) for r in device.rules]
        sensors = [(s, Pattern(s.pattern, s.format, device.params)) for s in device.sensors]
        buttons = [(b, Pattern(b.pattern, b.format, device.params)) for b in device.buttons]
        self._compiled[device.id] = (rules, sensors, buttons)

    def has_feedback(self, device_id: str, name: str) -> bool:
        device = self.devices.get(device_id)
        return device is not None and any(r.field == name for r in device.rules)

    # ---- entities -----------------------------------------------------------------------
    def desired_unique_ids(self) -> set[str]:
        from .managed import unique_ids  # noqa: PLC0415  (managed imports this module)

        return {uid for device in self.devices.values() for uid in unique_ids(device)}

    @callback
    def prune_registry(self) -> int:
        """Remove registry rows of entities whose command / sensor / device is gone.

        Skipped when the store looks empty while rows exist: a store that failed to load would
        otherwise take every entity's name, area and dashboard references with it.
        """
        registry = er.async_get(self.hass)
        rows = er.async_entries_for_config_entry(registry, self.entry.entry_id)
        if not self.loaded or (not self.devices and rows):
            return 0
        keep = self.desired_unique_ids()
        removed = 0
        for row in rows:
            if row.unique_id not in keep:
                registry.async_remove(row.entity_id)
                removed += 1
        return removed

    @callback
    def register_platform(self, domain: str, add_entities: AddEntitiesCallback) -> None:
        from .managed import build  # noqa: PLC0415

        self._adders[domain] = add_entities
        entities = [e for device in self.devices.values() for e in build(self, device, domain)]
        if entities:
            add_entities(entities)

    @callback
    def entity_added(self, entity: Entity, device_id: str) -> None:
        self._live.setdefault(device_id, []).append(entity)

    @callback
    def entity_removed(self, entity: Entity, device_id: str) -> None:
        live = self._live.get(device_id, [])
        if entity in live:
            live.remove(entity)

    @callback
    def add_button_listener(self, device_id: str, cb: Callable[[Button, dict[str, Any]], None]) -> CALLBACK_TYPE:
        listeners = self._button_listeners.setdefault(device_id, [])
        listeners.append(cb)
        return lambda: listeners.remove(cb)

    @callback
    def add_entity_listener(self, device_id: str, cb: Callable[[], None]) -> CALLBACK_TYPE:
        listeners = self._entity_listeners.setdefault(device_id, [])
        listeners.append(cb)
        return lambda: listeners.remove(cb)

    async def _async_rebuild(self, device: Device | None, device_id: str) -> None:
        """Replace a device's entities after an edit (registry rows survive, so entity ids stay)."""
        from .managed import build  # noqa: PLC0415

        for entity in list(self._live.get(device_id, [])):
            await entity.async_remove()
        self._live.pop(device_id, None)
        self.prune_registry()
        if device is None:
            return
        for domain, add_entities in self._adders.items():
            entities = build(self, device, domain)
            if entities:
                add_entities(entities)

    # ---- editing (panel) ----------------------------------------------------------------
    def device_dict(self, device: Device) -> dict[str, Any]:
        registry = er.async_get(self.hass)
        entities = [row.entity_id for row in er.async_entries_for_config_entry(registry, self.entry.entry_id)
                    if row.unique_id.startswith(f"{device.id}_")]
        return {**asdict(device), "entities": sorted(entities), "bindable": binding_actions(device)}

    async def async_save_device(self, raw: dict[str, Any]) -> Device:
        raw = dict(raw)
        raw["id"] = raw.get("id") or new_id()
        for key in ("commands", "rules", "sensors", "buttons"):
            for item in raw.get(key, []) or []:
                item["id"] = item.get("id") or new_id()
        try:
            device = Device.from_dict(raw)
        except (KeyError, TypeError, ValueError) as err:
            raise DeviceError("malformed", detail=str(err)) from err
        hub = self.bus.ports.get(device.port_id)
        if hub is None and self.hass.config_entries.async_get_entry(device.port_id) is None:
            raise DeviceError("no_port")
        validate(device)
        self._check_bindings(device)
        old = self.devices.get(device.id)
        for button in device.buttons:
            before = old.button(button.id) if old else None
            if before is not None and before.name != button.name:  # a rename keeps the old name findable
                history = [before.name, *before.alias_history]
                button.alias_history = [n for n in dict.fromkeys(history) if n != button.name][:ALIAS_HISTORY]
        self._compile(device)
        self.devices[device.id] = device
        await self._async_save()
        self._start_poll(device)
        await self._async_rebuild(device, device.id)
        self._push("devices", {"devices": [self.device_dict(device)], "removed": []})
        return device

    def _check_bindings(self, device: Device) -> None:
        for button in device.buttons:
            if not button.target:
                continue
            target = self.devices.get(button.target)
            if target is None or target.id == device.id:
                raise DeviceError("binding_target", button=button.name)
            if button.action not in binding_actions(target):
                raise DeviceError("binding_action", button=button.name, action=button.action)
            if button.action in VALUE_ACTIONS and (button.value is None or not 0 <= button.value <= 100):
                raise DeviceError("binding_value", button=button.name)

    async def async_delete_device(self, device_id: str) -> None:
        if self.devices.pop(device_id, None) is None:
            return
        self._compiled.pop(device_id, None)
        self.state.pop(device_id, None)
        self._stop_poll(device_id)
        await self._async_save()
        await self._async_rebuild(None, device_id)
        registry = dr.async_get(self.hass)
        entry = registry.async_get_device_by_identifier((DOMAIN, f"device_{device_id}"), self.entry.entry_id)
        if entry is not None:
            registry.async_remove_device(entry.id)
        self._push("devices", {"devices": [], "removed": [device_id]})

    # ---- sending ------------------------------------------------------------------------
    def _port(self, device: Device):
        hub = self.bus.ports.get(device.port_id)
        if hub is None or not hub.available:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="port_missing",
                                     translation_placeholders={"name": device.name})
        return hub

    async def async_run(self, device: Device, command: Command, variables: dict[str, Any] | None = None,
                        origin: str | None = None) -> tuple[Any, Any]:
        """Send one command (all its repeats); return (what was sent, the reply or None)."""
        hub = self._port(device)
        try:
            payload = render(command.payload, command.format, {**device.params, **(variables or {})})
        except TemplateError as err:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="bad_template",
                                     translation_placeholders={"name": command.name, "error": str(err)}) from err
        origin = origin or f"device:{device.id}"
        reply = None
        for attempt in range(max(1, command.repeat)):
            if attempt:
                await asyncio.sleep(command.gap_ms / 1000)
            wait = command.wait_ms / 1000 if attempt == command.repeat - 1 else 0
            reply = await hub.async_send(payload, wait, origin=origin)
        return payload, reply

    async def async_command(self, device_id: str, command_id: str, value: float | None = None) -> tuple[Any, Any]:
        device = self.devices[device_id]
        command = device.command(command_id)
        if command is None:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="not_mapped",
                                     translation_placeholders={"name": device.name, "action": command_id})
        return await self.async_run(device, command, {} if value is None else {"value": value})

    async def async_action(self, device_id: str, action: str, ha_value: float | None = None) -> None:
        """Run the command mapped to an entity action, then show what it implies."""
        device = self.devices[device_id]
        command = device.command(device.actions.get(action, ""))
        if command is None:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="not_mapped",
                                     translation_placeholders={"name": device.name, "action": action})
        variables: dict[str, Any] = {}
        name = VALUE_ACTIONS.get(action)
        if name is not None and ha_value is not None:
            variables["value"] = to_device(device, name, ha_value)
        await self.async_run(device, command, variables)
        self.update_state(device_id, self._implied(device, action, ha_value))

    async def async_option(self, device_id: str, option: str, name: str) -> None:
        """Pick a source / option by running its command."""
        device = self.devices[device_id]
        chosen = next((o for o in device.options if o.name == option), None)
        command = device.command(chosen.command) if chosen else None
        if command is None:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="not_mapped",
                                     translation_placeholders={"name": device.name, "action": option})
        await self.async_run(device, command)
        self.update_state(device_id, {name: option} if not self.has_feedback(device_id, name) else {})

    def _implied(self, device: Device, action: str, ha_value: float | None) -> dict[str, Any]:
        """Optimistic state after a send; a field with feedback rules waits for the device."""
        implied: dict[str, Any] = {
            "turn_on": {"power": True}, "turn_off": {"power": False},
            "open": {"position": 100}, "close": {"position": 0},
            "mute_on": {"mute": True}, "mute_off": {"mute": False},
            "play": {"playback": "playing"}, "pause": {"playback": "paused"}, "stop": {"playback": "idle"},
        }.get(action, {})
        name = VALUE_ACTIONS.get(action)
        if name is not None and ha_value is not None:
            implied = {name: ha_value}
            if name == "brightness":
                implied["power"] = ha_value > 0
        return {k: v for k, v in implied.items() if not self.has_feedback(device.id, k)}

    # ---- receiving ----------------------------------------------------------------------
    @callback
    def on_frame(self, frame: BusFrame) -> None:
        for device in self.devices.values():
            if device.port_id != frame.port_id:
                continue
            rules, sensors, buttons = self._compiled.get(device.id, ([], [], []))
            for button, pattern in buttons:
                found = pattern.match(frame.data)
                if found is not None:
                    self._press(device, button, frame, found)
            changes: dict[str, Any] = {}
            for rule, pattern in rules:
                found = pattern.match(frame.data)
                if found is not None:
                    value = self._rule_value(device, rule, found)
                    if value is not None:
                        changes[rule.field] = value
            for sensor, pattern in sensors:
                found = pattern.match(frame.data)
                if found is None or not isinstance(found.get(sensor.capture), (int, float)):
                    continue
                value = found[sensor.capture] * sensor.scale + sensor.offset
                if sensor.precision is not None:
                    value = round(value, sensor.precision)
                changes[f"sensor:{sensor.id}"] = value
            if changes:
                self.update_state(device.id, changes)

    @callback
    def _press(self, device: Device, button: Button, frame: BusFrame, found: dict[str, Any]) -> None:
        """A keypad button was pressed: event, device trigger, event entity, binding."""
        now = time.monotonic()
        last = self._last_press.get(button.id)
        if last is not None and now - last < button.debounce_ms / 1000:
            return  # the same press repeated (key held, or the keypad sends each press twice)
        self._last_press[button.id] = now
        data = {"device_id": device.id, "keypad": device.name, "button_id": button.id, "button": button.name,
                "port_id": frame.port_id, "hex": to_hex(frame.data), **found}
        self.hass.bus.async_fire(EVENT_BUTTON, data)
        for cb in list(self._button_listeners.get(device.id, [])):
            cb(button, data)
        self.update_state(device.id, {"last_button": button.name})
        if button.target and button.action:
            self._run_binding(device, button)

    def _run_binding(self, device: Device, button: Button) -> None:
        now = time.monotonic()
        if self._paused.get(button.id, 0) > now:
            return
        recent = [t for t in self._fired.get(button.id, []) if now - t < LOOP_WINDOW] + [now]
        self._fired[button.id] = recent
        if len(recent) > LOOP_LIMIT:
            self._paused[button.id] = now + LOOP_PAUSE
            _LOGGER.warning("%s / %s drove %s %d times in %ss; binding paused for %ss", device.name, button.name,
                            button.target, len(recent), LOOP_WINDOW, LOOP_PAUSE)
            return
        self.hass.async_create_task(self._async_binding(device, button), f"woow_serial binding {button.name}")

    async def _async_binding(self, device: Device, button: Button) -> None:
        target = self.devices.get(button.target)
        if target is None:
            return
        action = button.action
        try:
            if action == TOGGLE:
                on = self.state.get(target.id, {}).get("power")
                await self.async_action(target.id, "turn_off" if on else "turn_on")
            elif action.startswith("command:"):
                await self.async_command(target.id, action.split(":", 1)[1])
            elif action.startswith("option:"):
                await self.async_option(target.id, action.split(":", 1)[1],
                                        "source" if target.type == "media_player" else "option")
            elif action in VALUE_ACTIONS:
                name = VALUE_ACTIONS[action]
                await self.async_action(target.id, action, (button.value or 0) / 100 * HA_SCALE[name])
            else:
                await self.async_action(target.id, action)
        except HomeAssistantError as err:
            _LOGGER.warning("%s / %s could not drive %s: %s", device.name, button.name, target.name, err)

    def _rule_value(self, device: Device, rule: Rule, found: dict[str, Any]) -> Any:
        text = rule.value.strip()
        whole = _CAPTURE_REF.fullmatch(text)
        raw: Any = found.get(whole.group(1)) if whole else _CAPTURE_REF.sub(
            lambda m: str(found.get(m.group(1), "")), text)
        if rule.field in ("power", "mute"):
            return truthy(raw)
        if rule.field in HA_SCALE:
            try:
                return from_device(device, rule.field, float(raw))
            except (TypeError, ValueError):
                return None
        return None if raw is None else str(raw)

    @callback
    def update_state(self, device_id: str, changes: dict[str, Any]) -> None:
        if not changes or device_id not in self.devices:
            return
        state = self.state.setdefault(device_id, {})
        if all(state.get(k) == v for k, v in changes.items()):
            return
        state.update(changes)
        for cb in list(self._entity_listeners.get(device_id, [])):
            cb()
        self._dirty_state.add(device_id)
        if self._feed and self._push_handle is None:
            self._push_handle = self.hass.loop.call_later(LIVE_PUSH, self._push_state)

    @callback
    def _push_state(self) -> None:
        self._push_handle = None
        states = {i: self.state.get(i, {}) for i in self._dirty_state if i in self.devices}
        self._dirty_state.clear()
        self._push("device_state", {"states": states})

    # ---- polling ------------------------------------------------------------------------
    def _start_poll(self, device: Device) -> None:
        self._stop_poll(device.id)
        command = device.command(device.poll_command)
        if command is None or device.poll_interval <= 0:
            return

        async def tick(_now: Any) -> None:
            try:
                await self.async_run(device, command, origin=f"device:{device.id}")
            except HomeAssistantError as err:
                _LOGGER.debug("%s: poll failed: %s", device.name, err)

        self._polls[device.id] = async_track_time_interval(
            self.hass, tick, timedelta(seconds=device.poll_interval), name=f"woow_serial poll {device.name}")

    def _stop_poll(self, device_id: str) -> None:
        if (unsub := self._polls.pop(device_id, None)) is not None:
            unsub()

    # ---- panel feed ---------------------------------------------------------------------
    @callback
    def subscribe(self, cb: Callable[[str, dict[str, Any]], None]) -> CALLBACK_TYPE:
        self._feed.append(cb)
        return lambda: self._feed.remove(cb)

    def _push(self, kind: str, payload: dict[str, Any]) -> None:
        for cb in list(self._feed):
            cb(kind, payload)

    def snapshot(self) -> dict[str, Any]:
        return {
            "devices": [self.device_dict(d) for d in self.devices.values()],
            "states": self.state,
            "types": DEVICE_TYPES,
            "value_actions": VALUE_ACTIONS,
        }

    # ---- editor helpers -----------------------------------------------------------------
    @staticmethod
    def preview(payload: str, fmt: str, params: dict[str, str], value: float | None) -> dict[str, Any]:
        """What a command template sends, or why it cannot."""
        variables: dict[str, Any] = {**params}
        if value is not None:
            variables["value"] = value
        try:
            used = sorted(fields_used(payload, fmt))
            result = render(payload, fmt, variables)
        except TemplateError as err:
            return {"error": {"code": err.code, **{f"t_{k}": v for k, v in err.info.items()}}}
        return {"sent": to_hex(result), "fields": used}

    @staticmethod
    def test_pattern(pattern: str, fmt: str, params: dict[str, str], frames: list[bytes]) -> dict[str, Any]:
        """Which of these frames a pattern matches, and what it reads out of them."""
        try:
            compiled = Pattern(pattern, fmt, params)
        except TemplateError as err:
            return {"error": {"code": err.code, **{f"t_{k}": v for k, v in err.info.items()}}}
        matches = []
        for data in frames:
            found = compiled.match(data)
            if found is not None:
                matches.append({"frame": to_hex(data), "captures": found})
        return {"matches": matches, "captures": sorted(_captures(compiled))}
