"""Home Assistant services for AI agents (and scripts): everything the panel does, as actions.

Agents reach these over MCP (e.g. ha-mcp's service calls). Design rules:
- ports and devices are named by id *or* by name, so an agent can use what it reads back;
- reads return data (SupportsResponse.ONLY); changes return data when asked (OPTIONAL);
- an invalid device comes back as a structured error the agent can fix and resend;
- input is checked in the handler, not by Home Assistant's schema check: over REST (how ha-mcp
  calls services) a schema failure is a bare "400: Bad Request", a ServiceValidationError
  carries its message;
- configuration changes need an admin user (like the panel); operating devices does not;
- every change is written to the activity log with the caller's user and its `note`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

import probatio
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_admin_service

from . import checksum
from .catalog import is_text
from .codec import printable, to_hex
from .const import DOMAIN
from .devices import DEVICE_TYPES, HA_SCALE, VALUE_ACTIONS, Device, DeviceError, DeviceManager, new_id
from .template import BCD, FORMATS, NUMBERS

if TYPE_CHECKING:
    from .admin import AdminHub
    from .hub import Hub

_NOTE = vol.Optional("note", default="")  # every change can say why; shown in the activity log
ADMIN_SERVICES = {"save_device", "create_from_template", "delete_device", "learn_command", "learn_button"}
_LIMIT = vol.All(vol.Coerce(int), vol.Range(min=1, max=1000))
_TIMEOUT = vol.All(vol.Coerce(float), vol.Range(min=1, max=120))


def _invalid(key: str, **placeholders: str) -> ServiceValidationError:
    return ServiceValidationError(translation_domain=DOMAIN, translation_key=key,
                                  translation_placeholders=placeholders or None)


def _explain(err: Exception) -> str:
    """'value must be one of [...] at 'type'' for each problem, as Home Assistant's websocket API words it."""
    parts = []
    for error in getattr(err, "errors", None) or [err]:
        path = ".".join(str(p) for p in getattr(error, "path", None) or [])
        message = getattr(error, "msg", None) or str(error)
        parts.append(f"{message} at '{path}'" if path else message)
    return "; ".join(parts)


def validated(hass: HomeAssistant, schema: Callable[[dict[str, Any]], dict[str, Any]],
              handler: Callable[[ServiceCall], Awaitable[ServiceResponse]]) -> Callable[[ServiceCall], Awaitable[ServiceResponse]]:
    """Check a call's data in the handler, so every caller (REST included) is told what is wrong."""

    async def run(call: ServiceCall) -> ServiceResponse:
        try:
            data = schema(dict(call.data))
        except (vol.Invalid, probatio.Invalid) as err:
            raise _invalid("bad_input", error=_explain(err)) from err
        return await handler(ServiceCall(hass, call.domain, call.service, data, call.context, call.return_response))

    return run


def _admin(hass: HomeAssistant) -> AdminHub:
    admin = hass.data.get(DOMAIN, {}).get("admin")
    if admin is None:
        raise _invalid("panel_not_loaded")
    return admin


def resolve_port(admin: AdminHub, ref: str) -> Hub:
    """A port by config entry id, name (RS485-1) or device path (/dev/ttySC0)."""
    want = ref.strip().casefold()
    for hub in admin.bus.ports.values():
        if want in (hub.entry.entry_id.casefold(), hub.name.casefold(), hub.port.casefold()):
            return hub
    raise _invalid("unknown_port", port=ref, ports=", ".join(sorted(h.name for h in admin.bus.ports.values())))


def resolve_device(admin: AdminHub, ref: str) -> Device:
    want = ref.strip().casefold()
    for device in admin.devices.devices.values():
        if want in (device.id.casefold(), device.name.casefold()):
            return device
    raise _invalid("unknown_device", device=ref,
                   devices=", ".join(sorted(d.name for d in admin.devices.devices.values())))


def _command_id(device: Device, ref: str) -> str:
    want = ref.strip().casefold()
    for command in device.commands:
        if want in (command.id.casefold(), command.name.casefold()):
            return command.id
    raise _invalid("unknown_command", device=device.name, command=ref,
                   commands=", ".join(c.name for c in device.commands))


def normalize(admin: AdminHub, raw: dict[str, Any]) -> dict[str, Any]:
    """Let agents write names where ids belong: commands in actions / options / poll, button targets."""
    raw = dict(raw)
    if raw.get("port") and not raw.get("port_id"):
        raw["port_id"] = resolve_port(admin, str(raw.pop("port"))).entry.entry_id
    commands = [dict(c) for c in raw.get("commands") or []]
    for command in commands:
        command["id"] = command.get("id") or new_id()
    raw["commands"] = commands
    by_name = {c.get("name"): c["id"] for c in commands}
    for command in commands:
        if command.get("then"):
            command["then"] = by_name.get(command["then"], command["then"])
    raw["actions"] = {action: by_name.get(ref, ref) for action, ref in (raw.get("actions") or {}).items()}
    raw["options"] = [dict(o, command=by_name.get(o.get("command"), o.get("command"))) for o in raw.get("options") or []]
    if raw.get("poll_command"):
        raw["poll_command"] = by_name.get(raw["poll_command"], raw["poll_command"])
    for key in ("rules", "sensors"):
        raw[key] = [dict(item, reply_to=by_name.get(item["reply_to"], item["reply_to"])) if item.get("reply_to")
                    else dict(item) for item in raw.get(key) or []]
    buttons = []
    for button in raw.get("buttons") or []:
        button = dict(button)
        if button.get("target"):
            target = resolve_device(admin, str(button["target"]))
            button["target"] = target.id
            action = str(button.get("action") or "")
            if action.startswith("command:"):
                ref = action.split(":", 1)[1]
                match = next((c.id for c in target.commands if ref in (c.id, c.name)), ref)
                button["action"] = f"command:{match}"
        buttons.append(button)
    raw["buttons"] = buttons
    return raw


def _error(err: DeviceError) -> dict[str, Any]:
    """A DeviceError as data an agent can act on."""
    return {"ok": False, "error": {**err.as_dict(), "message": str(err)}}


def _device_view(admin: AdminHub, device: Device) -> dict[str, Any]:
    port = admin.bus.ports.get(device.port_id)
    return {**admin.devices.device_dict(device), "port": port.name if port else None,
            "state": admin.devices.state.get(device.id, {})}


def describe(admin: AdminHub, language: str) -> dict[str, Any]:
    """Everything an agent needs to know to drive this integration."""
    return {
        "integration": "woow_serial",
        "purpose": "Control RS485 / RS232 equipment from Home Assistant: watch frames on a port, learn them, "
                   "turn them into devices with entities, and react to keypads.",
        "workflow": [
            "list_ports to see the ports (on-board UARTs and bound external devices such as an HA-WF485-V3).",
            "list_templates and create_from_template when the equipment is a known model.",
            "Otherwise: get_monitor (frames heard per port) or listen / learn_command while a person presses the "
            "original remote or keypad, then save_device with commands, actions, rules and buttons.",
            "preview_command and test_pattern check templates and patterns before saving.",
            "run_command or the entity services (cover.open_cover, light.turn_on, ...) operate devices; "
            "get_send_log shows whether the equipment answered.",
            "Give every change a short `note`: people read it in the panel's activity log.",
        ],
        "device_types": DEVICE_TYPES,
        "value_actions": {k: {"field": v, "home_assistant_scale": HA_SCALE[v]} for k, v in VALUE_ACTIONS.items()},
        "device_fields": {
            "name": "unique within the integration", "type": "one of device_types", "port_id": "port id (list_ports)",
            "params": "{name: value} substituted for {name} in commands and patterns: HEX in HEX ones "
                      "({'addr': '01 02'}), text in text ones ({'output': '2'})",
            "commands": "[{id?, name, payload, format: hex|text, repeat=1, gap_ms=100, wait_ms=0, then?, "
                        "then_ms=500}]; wait_ms: set it on every command the device answers (Modbus, most "
                        "RS485 motors, RS232 AV gear): the port is held until the answer, so the next request "
                        "cannot collide with it on a half-duplex line; then = a command sent then_ms after this "
                        "one, usually a query, for devices that only acknowledge a set command",
            "actions": "{action: command id} for the type's actions",
            "options": "[{name, command}] sources of a media_player / choices of a select",
            "rules": "[{pattern, format, field, value, reply_to?}] state feedback; value is a literal or "
                     "'{capture}'; reply_to = a command: only its reply counts (Modbus answers do not name the "
                     "register they answer)",
            "sensors": "[{name, pattern, format, capture, scale=1, offset=0, unit, device_class, precision, "
                       "reply_to?}]",
            "buttons": "keypad only: [{name, pattern, format, debounce_ms=300, target?, action?, value?}]",
            "ranges": "{brightness|position|volume: [device value at 0 %, at 100 %]}",
            "poll_command": "command id sent every poll_interval seconds",
        },
        "command_template": {
            "hex": "Bytes as HEX; {param} inserts a device parameter; {value:TYPE} inserts the action value; "
                   "{CHECKSUM} or {CHECKSUM@START} appends a checksum over the bytes before it.",
            "text": "Text with \\r \\n \\t \\xHH escapes; {value:03d} uses Python format specs.",
            "value_types": sorted(NUMBERS) + sorted(BCD),
            "checksums": list(checksum.ALGORITHMS),
        },
        "receive_pattern": {
            "hex": "?? any byte; {name:TYPE} captures a number; {param} must match; {CHECKSUM} must be valid; "
                   "* at the end accepts the rest.",
            "text": "A Python regular expression; named groups (?P<name>...) are captures.",
        },
        "binding_actions": "toggle, the target's mapped actions, option:<name>, command:<command id>",
        "events": {
            "woow_serial_frame": "every received frame: entry_id, name, port, hex, text, length",
            "woow_serial_button": "keypad press: device_id, keypad, button_id, button, port_id, hex, captures",
        },
        "ports": [hub.info() for hub in admin.bus.ports.values()],
        "templates": [{"id": t["id"], "name": t["name"], "type": t["type"]} for t in admin.templates.summaries(language)],
        "devices": [{"id": d.id, "name": d.name, "type": d.type} for d in admin.devices.devices.values()],
    }


def async_register(hass: HomeAssistant) -> None:
    """Register the agent services (they look the admin entry up per call)."""

    def language() -> str:
        return hass.config.language or "en"

    def register(name: str, handler: Callable[[ServiceCall], Awaitable[ServiceResponse]], schema: dict,
                 response: SupportsResponse) -> None:
        run = validated(hass, vol.Schema(schema), handler)
        if name in ADMIN_SERVICES:
            async_register_admin_service(hass, DOMAIN, name, run, schema=None, supports_response=response)
        else:
            hass.services.async_register(DOMAIN, name, run, schema=None, supports_response=response)

    async def record(call: ServiceCall, action: str, msg: str, args: dict[str, Any], *, routine: bool = False,
                     **extra: Any) -> None:
        """Log a change. Routine operations (sends) only when a person / agent token or a note is behind them,
        so an automation that polls every minute does not bury the log."""
        if routine and not (call.context.user_id or call.data.get("note")):
            return
        await _admin(hass).activity.async_record("service", action, msg, args, context=call.context,
                                                  note=call.data.get("note", ""), **extra)

    # ---- reads ------------------------------------------------------------------------------
    async def s_describe(call: ServiceCall) -> ServiceResponse:
        return describe(_admin(hass), language())

    async def s_list_ports(call: ServiceCall) -> ServiceResponse:
        return {"ports": [hub.info() for hub in _admin(hass).bus.ports.values()]}

    async def s_get_monitor(call: ServiceCall) -> ServiceResponse:
        admin = _admin(hass)
        port_id = resolve_port(admin, call.data["port"]).entry.entry_id if call.data.get("port") else None
        snap = admin.catalog.snapshot()
        groups = [g for g in snap["groups"] if (port_id is None or g["port_id"] == port_id)
                  and (call.data["include_hidden"] or not g["hidden"])]
        groups.sort(key=lambda g: -g["last_seen"])
        groups = groups[: call.data["limit"]]
        names = {p.entry.entry_id: p.name for p in admin.bus.ports.values()}
        rows: dict[str, list[dict[str, Any]]] = {}
        for row in sorted(snap["rows"], key=lambda r: -r["last_seen"]):
            rows.setdefault(row["group_id"], []).append(
                {k: row[k] for k in ("id", "hex", "text", "checks", "alias", "count", "last_seen")})
        return {"groups": [{**{k: g[k] for k in ("id", "key", "alias", "hidden", "count", "rows", "checksum", "last_seen")},
                            "port": names.get(g["port_id"]), "port_id": g["port_id"], "frames": rows.get(g["id"], [])[:50]}
                           for g in groups]}

    async def s_get_send_log(call: ServiceCall) -> ServiceResponse:
        admin = _admin(hass)
        port_id = resolve_port(admin, call.data["port"]).entry.entry_id if call.data.get("port") else None
        rows = [r for r in admin.mirror.snapshot()["rows"] if port_id is None or r["port_id"] == port_id]
        return {"sent": rows[: call.data["limit"]]}

    async def s_listen(call: ServiceCall) -> ServiceResponse:
        admin = _admin(hass)
        hub = resolve_port(admin, call.data["port"])
        data = await admin.async_listen(hub.entry.entry_id, call.data["timeout"])
        if data is None:
            return {"timeout": True, "port": hub.name}
        return {"timeout": False, "port": hub.name, "hex": to_hex(data),
                "text": printable(data) if is_text(data) else None, "checks": checksum.detect(data)}

    async def s_list_devices(call: ServiceCall) -> ServiceResponse:
        admin = _admin(hass)
        port_id = resolve_port(admin, call.data["port"]).entry.entry_id if call.data.get("port") else None
        devices = [d for d in admin.devices.devices.values()
                   if (port_id is None or d.port_id == port_id) and (not call.data.get("type") or d.type == call.data["type"])]
        return {"devices": [_device_view(admin, d) for d in devices]}

    async def s_get_device(call: ServiceCall) -> ServiceResponse:
        admin = _admin(hass)
        return {"device": _device_view(admin, resolve_device(admin, call.data["device"]))}

    async def s_preview(call: ServiceCall) -> ServiceResponse:
        return DeviceManager.preview(call.data["payload"], call.data["format"], call.data["params"], call.data.get("value"))

    async def s_test_pattern(call: ServiceCall) -> ServiceResponse:
        admin = _admin(hass)
        hub = resolve_port(admin, call.data["port"])
        return DeviceManager.test_pattern(call.data["pattern"], call.data["format"], call.data["params"],
                                          admin.recent_frames(hub.entry.entry_id))

    async def s_list_templates(call: ServiceCall) -> ServiceResponse:
        admin = _admin(hass)
        return {"templates": admin.templates.summaries(language(), call.data.get("type"))}

    async def s_get_activity(call: ServiceCall) -> ServiceResponse:
        admin = _admin(hass)
        device_id = resolve_device(admin, call.data["device"]).id if call.data.get("device") else None
        return {"activity": admin.activity.recent(call.data["limit"], device_id)}

    # ---- changes ----------------------------------------------------------------------------
    async def save(call: ServiceCall, raw: dict[str, Any], action: str, msg: str | None = None,
                   **args: Any) -> ServiceResponse:
        """Save a device and log it: msg / args name what happened (default: created / updated)."""
        admin = _admin(hass)
        existing = admin.devices.devices.get(raw.get("id", ""))
        try:
            device = await admin.devices.async_save_device(raw)
        except DeviceError as err:
            await record(call, action, "device_save_failed", {"device": raw.get("name", "?"), "error": err.code},
                         ok=False, error=err.as_dict())
            if call.return_response:
                return _error(err)
            raise _invalid("invalid_device", code=err.code, detail=str(err)) from err
        port = admin.bus.ports.get(device.port_id)
        msg = msg or ("device_updated" if existing else "device_created")
        await record(call, action, msg, {"device": device.name, "type": device.type, "port": port.name if port else "?",
                                         **args}, device_id=device.id, port_id=device.port_id)
        return {"ok": True, "device": _device_view(admin, device)} if call.return_response else None

    async def s_save_device(call: ServiceCall) -> ServiceResponse:
        admin = _admin(hass)
        raw = normalize(admin, dict(call.data["device"]))
        if not raw.get("id") and raw.get("name"):  # saving under an existing name updates that device
            same = next((d for d in admin.devices.devices.values() if d.name == raw["name"]), None)
            if same is not None and call.data["replace"]:
                raw["id"] = same.id
        return await save(call, raw, "save_device")

    async def s_create_from_template(call: ServiceCall) -> ServiceResponse:
        admin = _admin(hass)
        template = admin.templates.get(call.data["template"])
        if template is None:
            raise _invalid("unknown_template", template=call.data["template"],
                           templates=", ".join(sorted(admin.templates.templates)))
        hub = resolve_port(admin, call.data["port"])
        raw = template.instantiate(hub.entry.entry_id, call.data.get("name", ""), call.data["params"], language())
        response = await save(call, raw, "create_from_template", "device_from_template", template=template.id)
        if response and response.get("ok"):
            response["template"] = template.id
            wanted = {k: template.port[k] for k in ("baudrate", "bytesize", "parity", "stopbits") if k in template.port}
            response["port_settings"] = {"port": hub.settings, "template_expects": wanted}
        return response

    async def s_delete_device(call: ServiceCall) -> ServiceResponse:
        admin = _admin(hass)
        device = resolve_device(admin, call.data["device"])
        await admin.devices.async_delete_device(device.id)
        await record(call, "delete_device", "device_deleted", {"device": device.name}, device_id=device.id,
                     port_id=device.port_id)
        return {"ok": True} if call.return_response else None

    async def s_run_command(call: ServiceCall) -> ServiceResponse:
        admin = _admin(hass)
        device = resolve_device(admin, call.data["device"])
        command_id = _command_id(device, call.data["command"])
        command = device.command(command_id)
        try:
            sent, reply = await admin.devices.async_command(device.id, command_id, call.data.get("value"))
        except HomeAssistantError as err:
            await record(call, "run_command", "command_failed", {"device": device.name, "command": command.name,
                                                                 "error": str(err)},
                         ok=False, routine=True, device_id=device.id, port_id=device.port_id)
            raise
        await record(call, "run_command", "command_sent", {"device": device.name, "command": command.name,
                                                           "hex": to_hex(sent)},
                     routine=True, device_id=device.id, port_id=device.port_id)
        if not call.return_response:
            return None
        return {"sent": to_hex(sent), "reply": None if reply is None else to_hex(reply),
                "timeout": command.wait_ms > 0 and reply is None}

    async def learn(call: ServiceCall, kind: str) -> ServiceResponse:
        """Listen on the device's port, then add what was heard as a command / keypad button."""
        admin = _admin(hass)
        device = resolve_device(admin, call.data["device"])
        if kind == "button" and device.type != "keypad":
            raise _invalid("not_a_keypad", device=device.name)
        data = await admin.async_listen(device.port_id, call.data["timeout"])
        if data is None:
            return {"ok": False, "timeout": True} if call.return_response else None
        text = printable(data) if is_text(data) else None
        raw = admin.devices.device_dict(device)
        if kind == "command":
            raw["commands"].append({"name": call.data["name"], "payload": text if text else to_hex(data),
                                    "format": "text" if text else "hex"})
        else:
            pattern = f"^{_regex_escape(text)}$" if text else to_hex(data)
            raw["buttons"].append({"name": call.data["name"], "pattern": pattern, "format": "text" if text else "hex"})
        response = await save(call, raw, f"learn_{kind}", f"{kind}_learned", name=call.data["name"], hex=to_hex(data))
        if response is not None:
            response["heard"] = {"hex": to_hex(data), "text": text}
        return response

    async def s_learn_command(call: ServiceCall) -> ServiceResponse:
        return await learn(call, "command")

    async def s_learn_button(call: ServiceCall) -> ServiceResponse:
        return await learn(call, "button")

    register("describe", s_describe, {}, SupportsResponse.ONLY)
    register("list_ports", s_list_ports, {}, SupportsResponse.ONLY)
    register("get_monitor", s_get_monitor, {vol.Optional("port"): cv.string, vol.Optional("limit", default=20): _LIMIT,
                                            vol.Optional("include_hidden", default=False): cv.boolean}, SupportsResponse.ONLY)
    register("get_send_log", s_get_send_log, {vol.Optional("port"): cv.string, vol.Optional("limit", default=20): _LIMIT},
             SupportsResponse.ONLY)
    register("listen", s_listen, {vol.Required("port"): cv.string, vol.Optional("timeout", default=15): _TIMEOUT},
             SupportsResponse.ONLY)
    register("list_devices", s_list_devices, {vol.Optional("port"): cv.string, vol.Optional("type"): vol.In(list(DEVICE_TYPES))},
             SupportsResponse.ONLY)
    register("get_device", s_get_device, {vol.Required("device"): cv.string}, SupportsResponse.ONLY)
    register("preview_command", s_preview, {vol.Required("payload"): cv.string, vol.Optional("format", default="hex"): vol.In(FORMATS),
                                            vol.Optional("params", default={}): {cv.string: cv.string},
                                            vol.Optional("value"): vol.Coerce(float)}, SupportsResponse.ONLY)
    register("test_pattern", s_test_pattern, {vol.Required("pattern"): cv.string, vol.Required("port"): cv.string,
                                              vol.Optional("format", default="hex"): vol.In(FORMATS),
                                              vol.Optional("params", default={}): {cv.string: cv.string}}, SupportsResponse.ONLY)
    register("list_templates", s_list_templates, {vol.Optional("type"): vol.In(list(DEVICE_TYPES))}, SupportsResponse.ONLY)
    register("get_activity", s_get_activity, {vol.Optional("limit", default=50): _LIMIT, vol.Optional("device"): cv.string},
             SupportsResponse.ONLY)
    register("save_device", s_save_device, {vol.Required("device"): dict, vol.Optional("replace", default=True): cv.boolean,
                                            _NOTE: cv.string}, SupportsResponse.OPTIONAL)
    register("create_from_template", s_create_from_template, {
        vol.Required("template"): cv.string, vol.Required("port"): cv.string, vol.Optional("name", default=""): cv.string,
        vol.Optional("params", default={}): {cv.string: cv.string}, _NOTE: cv.string}, SupportsResponse.OPTIONAL)
    register("delete_device", s_delete_device, {vol.Required("device"): cv.string, _NOTE: cv.string}, SupportsResponse.OPTIONAL)
    register("run_command", s_run_command, {vol.Required("device"): cv.string, vol.Required("command"): cv.string,
                                            vol.Optional("value"): vol.Coerce(float), _NOTE: cv.string}, SupportsResponse.OPTIONAL)
    for name, handler in (("learn_command", s_learn_command), ("learn_button", s_learn_button)):
        register(name, handler, {vol.Required("device"): cv.string, vol.Required("name"): cv.string,
                                 vol.Optional("timeout", default=15): _TIMEOUT, _NOTE: cv.string}, SupportsResponse.OPTIONAL)


def _regex_escape(text: str) -> str:
    """printable() writes \\r, \\n, \\xHH and \\\\ as a regex reads them; escape every other metacharacter."""
    return "".join("\\" + ch if ch in ".*+?^$()[]{}|" else ch for ch in text)


__all__ = ["async_register", "describe", "resolve_device", "resolve_port"]
