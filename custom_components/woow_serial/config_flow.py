"""Config flow: an on-board port, a port bound from another integration, or the admin panel."""

from __future__ import annotations

import glob
import os
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.selector import (
    BooleanSelector,
    DeviceSelector,
    DeviceSelectorConfig,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .const import (
    BAUDRATES,
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_DEVICE_ID,
    CONF_ECHO_FILTER,
    CONF_FRAME_GAP,
    CONF_IDLE_VALUES,
    CONF_KIND,
    CONF_LINE_ENDING,
    CONF_LOOP_FLUSH,
    CONF_PARITY,
    CONF_PORT,
    CONF_RX_ENTITY,
    CONF_RX_FORMAT,
    CONF_SETTINGS_ENTITY,
    CONF_STATUS_ENTITY,
    CONF_STOPBITS,
    CONF_TX_ECHO_ENTITY,
    CONF_TX_ENTITY,
    CONF_TX_FORMAT,
    DOMAIN,
    EXTERNAL_DEFAULTS,
    KIND_EXTERNAL,
    KIND_HUB,
    KIND_SERIAL,
    LINE_ENDINGS,
    RX_FORMATS,
    SERIAL_DEFAULTS,
    TX_FORMATS,
    WF485_ENTITIES,
)
from .serial_port import probe

_INTS = (CONF_BAUDRATE, CONF_BYTESIZE, CONF_STOPBITS, CONF_FRAME_GAP)
_BINDING = (CONF_TX_ENTITY, CONF_TX_FORMAT, CONF_RX_ENTITY, CONF_RX_FORMAT, CONF_IDLE_VALUES,
            CONF_LINE_ENDING, CONF_TX_ECHO_ENTITY, CONF_SETTINGS_ENTITY, CONF_STATUS_ENTITY)


def _driver(device: str) -> str:
    """Hardware driver of a sysfs device, skipping the serial core's own port/ctrl layers."""
    path = os.path.realpath(device)
    while path.startswith("/sys/devices/"):
        link = os.path.join(path, "driver")
        if os.path.exists(link):
            name = os.path.basename(os.path.realpath(link))
            if name not in ("port", "ctrl"):
                return name
        path = os.path.dirname(path)
    return ""


def scan_ports() -> dict[str, str]:
    """On-board UARTs (SC16IS7xx RS485, PL011 RS232) and their drivers. Blocking."""
    found: dict[str, str] = {}
    for path in sorted(glob.glob("/dev/ttySC*")) + sorted(glob.glob("/dev/ttyAMA*")):
        name = os.path.basename(path)
        if name == "ttyAMA10":  # Raspberry Pi 5 debug UART
            continue
        found[path] = _driver(f"/sys/class/tty/{name}/device")
    return found


def default_name(port: str) -> str:
    """Names that match the Waveshare isolated RS232/RS485/CAN board."""
    base = os.path.basename(port)
    if base.startswith("ttySC") and base[5:].isdigit():
        return f"RS485-{int(base[5:]) + 1}"
    if base == "ttyAMA0":
        return "RS232"
    return base


def serial_defaults(port: str) -> dict[str, Any]:
    rs485 = os.path.basename(port).startswith("ttySC")  # half duplex: hears its own echo
    return {**SERIAL_DEFAULTS, CONF_ECHO_FILTER: rs485, CONF_LOOP_FLUSH: rs485}


def find_binding(hass: HomeAssistant, device_id: str) -> dict[str, str]:
    """Entities of an HA-WF485-V3 (or anything named like it) on this device."""
    found: dict[str, str] = {}
    for item in er.async_entries_for_device(er.async_get(hass), device_id):
        for key, (domain, ending) in WF485_ENTITIES.items():
            if key not in found and item.domain == domain and item.entity_id.endswith(ending):
                found[key] = item.entity_id
    return found


def _select(options: list[str], key: str | None = None, dropdown: bool = True) -> SelectSelector:
    config = SelectSelectorConfig(
        options=options, mode=SelectSelectorMode.DROPDOWN if dropdown else SelectSelectorMode.LIST)
    if key:  # probatio (HA 2026.10) rejects translation_key=None
        config["translation_key"] = key
    return SelectSelector(config)


def _number(low: int, high: int, step: int, unit: str) -> NumberSelector:
    return NumberSelector(NumberSelectorConfig(min=low, max=high, step=step,
                                               unit_of_measurement=unit, mode=NumberSelectorMode.BOX))


def _entity(domain: str | list[str]) -> EntitySelector:
    return EntitySelector(EntitySelectorConfig(domain=domain))


def serial_schema(values: dict[str, Any], with_name: bool) -> vol.Schema:
    fields: dict[Any, Any] = {}
    if with_name:
        fields[vol.Required(CONF_NAME, default=values[CONF_NAME])] = TextSelector()
    fields.update({
        vol.Required(CONF_BAUDRATE, default=str(values[CONF_BAUDRATE])): _select([str(b) for b in BAUDRATES]),
        vol.Required(CONF_BYTESIZE, default=str(values[CONF_BYTESIZE])): _select(["8", "7"], dropdown=False),
        vol.Required(CONF_PARITY, default=values[CONF_PARITY]): _select(["N", "E", "O"], "parity", False),
        vol.Required(CONF_STOPBITS, default=str(values[CONF_STOPBITS])): _select(["1", "2"], dropdown=False),
        vol.Required(CONF_FRAME_GAP, default=values[CONF_FRAME_GAP]): _number(0, 5000, 1, "ms"),
        vol.Required(CONF_ECHO_FILTER, default=values[CONF_ECHO_FILTER]): BooleanSelector(),
        vol.Required(CONF_LOOP_FLUSH, default=values[CONF_LOOP_FLUSH]): BooleanSelector(),
        vol.Required(CONF_LINE_ENDING, default=values[CONF_LINE_ENDING]): _select(list(LINE_ENDINGS), "line_ending"),
    })
    return vol.Schema(fields)


def external_schema(values: dict[str, Any], with_name: bool) -> vol.Schema:
    """Which entity sends, which one receives, and how their values are written."""
    fields: dict[Any, Any] = {}
    if with_name:
        fields[vol.Required(CONF_NAME, default=values[CONF_NAME])] = TextSelector()

    def suggested(key: str) -> dict[str, Any]:
        return {"suggested_value": values.get(key)} if values.get(key) else {}

    fields.update({
        vol.Required(CONF_TX_ENTITY, description=suggested(CONF_TX_ENTITY)): _entity(["text", "input_text"]),
        vol.Required(CONF_TX_FORMAT, default=values[CONF_TX_FORMAT]): _select(TX_FORMATS, "tx_format"),
        vol.Required(CONF_RX_ENTITY, description=suggested(CONF_RX_ENTITY)): _entity(["sensor", "text", "input_text"]),
        vol.Required(CONF_RX_FORMAT, default=values[CONF_RX_FORMAT]): _select(RX_FORMATS, "rx_format"),
        vol.Required(CONF_IDLE_VALUES, default=values[CONF_IDLE_VALUES]): TextSelector(),
        vol.Required(CONF_LINE_ENDING, default=values[CONF_LINE_ENDING]): _select(list(LINE_ENDINGS), "line_ending"),
        vol.Optional(CONF_TX_ECHO_ENTITY, description=suggested(CONF_TX_ECHO_ENTITY)): _entity("sensor"),
        vol.Optional(CONF_SETTINGS_ENTITY, description=suggested(CONF_SETTINGS_ENTITY)): _entity("sensor"),
        vol.Optional(CONF_STATUS_ENTITY, description=suggested(CONF_STATUS_ENTITY)): _entity("binary_sensor"),
    })
    return vol.Schema(fields)


def coerce(data: dict[str, Any]) -> dict[str, Any]:
    out = dict(data)
    for key in _INTS:
        if key in out:
            out[key] = int(float(out[key]))
    return out


def binding_errors(hass: HomeAssistant, opts: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    for key in (CONF_TX_ENTITY, CONF_RX_ENTITY):
        if not opts.get(key) or hass.states.get(opts[key]) is None:
            errors[key] = "entity_missing"
    if not errors and opts[CONF_TX_ENTITY] == opts[CONF_RX_ENTITY]:
        errors[CONF_RX_ENTITY] = "same_entity"
    return errors


def _binding(opts: dict[str, Any]) -> dict[str, Any]:
    return {k: opts[k] for k in _BINDING if opts.get(k) not in (None, "")}


class WoowSerialConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add an on-board port, a bound external port, or the admin panel."""

    VERSION = 1

    def __init__(self) -> None:
        self._port = ""
        self._driver = ""
        self._device_id: str | None = None
        self._values: dict[str, Any] = {}

    def _has_hub(self) -> bool:
        return any(e.data.get(CONF_KIND) == KIND_HUB for e in self._async_current_entries(include_ignore=False))

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        options = ["local", "external"] + ([] if self._has_hub() else ["hub"])
        return self.async_show_menu(step_id="user", menu_options=options)

    # ---- the admin panel ------------------------------------------------------------
    async def async_step_hub(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        await self.async_set_unique_id(KIND_HUB)
        self._abort_if_unique_id_configured()
        chinese = (self.hass.config.language or "").lower().startswith("zh")
        return self.async_create_entry(title="管理面板" if chinese else "Admin panel", data={CONF_KIND: KIND_HUB})

    async def async_step_system(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Created once on first run (see __init__._async_offer_panel)."""
        return await self.async_step_hub()

    # ---- on-board ports -------------------------------------------------------------
    async def async_step_local(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        ports = await self.hass.async_add_executor_job(scan_ports)
        taken = self._async_current_ids()
        free = {p: driver for p, driver in ports.items() if p not in taken}
        if not free:
            return self.async_abort(reason="no_ports")
        if user_input is not None and user_input[CONF_PORT] in free:
            self._port = user_input[CONF_PORT]
            self._driver = free[self._port]
            return await self.async_step_serial()
        options = [
            SelectOptionDict(value=p, label=f"{os.path.basename(p)} · {default_name(p)} · {driver}")
            for p, driver in free.items()
        ]
        return self.async_show_form(step_id="local", data_schema=vol.Schema({
            vol.Required(CONF_PORT): SelectSelector(SelectSelectorConfig(options=options, mode=SelectSelectorMode.LIST)),
        }))

    async def async_step_serial(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            opts = coerce(user_input)
            name = opts.pop(CONF_NAME).strip() or default_name(self._port)
            try:
                await self.hass.async_add_executor_job(probe, self._port)
            except OSError:
                errors["base"] = "cannot_open"
            else:
                await self.async_set_unique_id(self._port)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=name, options=opts, data={
                    CONF_KIND: KIND_SERIAL, CONF_PORT: self._port, "driver": self._driver})
        values = {**serial_defaults(self._port), CONF_NAME: default_name(self._port), **(user_input or {})}
        return self.async_show_form(step_id="serial", data_schema=serial_schema(values, True), errors=errors,
                                    description_placeholders={"port": self._port, "driver": self._driver})

    # ---- ports bound from other integrations ----------------------------------------
    async def async_step_external(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Pick the device (an HA-WF485-V3 fills itself in), or leave it empty to bind by hand."""
        if user_input is not None:
            self._device_id = user_input.get(CONF_DEVICE_ID) or None
            self._values = {**EXTERNAL_DEFAULTS, CONF_NAME: ""}
            if self._device_id:
                device = dr.async_get(self.hass).async_get(self._device_id)
                if device is not None:
                    self._values[CONF_NAME] = device.name_by_user or device.name or ""
                self._values.update(find_binding(self.hass, self._device_id))
            return await self.async_step_external_bind()
        return self.async_show_form(step_id="external", data_schema=vol.Schema({
            vol.Optional(CONF_DEVICE_ID): DeviceSelector(DeviceSelectorConfig()),
        }))

    async def async_step_external_bind(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            opts = dict(user_input)
            name = opts.pop(CONF_NAME).strip()
            errors = binding_errors(self.hass, opts)
            if not errors:
                await self.async_set_unique_id(self._device_id or opts[CONF_TX_ENTITY])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=name or opts[CONF_TX_ENTITY], options=_binding(opts), data={
                    CONF_KIND: KIND_EXTERNAL, CONF_PORT: opts[CONF_TX_ENTITY], CONF_DEVICE_ID: self._device_id})
            self._values.update(user_input)
        return self.async_show_form(step_id="external_bind", data_schema=external_schema(self._values, True),
                                    errors=errors)

    @classmethod
    @callback
    def async_supports_options(cls, config_entry: ConfigEntry) -> bool:
        return config_entry.data.get(CONF_KIND) != KIND_HUB

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return WoowSerialOptionsFlow()


class WoowSerialOptionsFlow(OptionsFlow):
    """Change line parameters or the binding; the entry reloads with them."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self.config_entry
        external = entry.data[CONF_KIND] == KIND_EXTERNAL
        errors: dict[str, str] = {}
        if user_input is not None:
            opts = coerce(user_input)
            if external:
                errors = binding_errors(self.hass, opts)
                opts = _binding(opts)
            if not errors:
                return self.async_create_entry(data=opts)
        if external:
            values = {**EXTERNAL_DEFAULTS, **entry.options, **(user_input or {})}
            schema = external_schema(values, False)
        else:
            values = {**serial_defaults(entry.data[CONF_PORT]), **entry.options, **(user_input or {})}
            schema = serial_schema(values, False)
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors,
                                    description_placeholders={"port": entry.data[CONF_PORT]})
