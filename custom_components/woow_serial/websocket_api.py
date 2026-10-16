"""Websocket commands behind the panel (admin only)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from . import checksum
from .admin import AdminHub
from .catalog import is_text
from .codec import parse_hex, printable, to_hex
from .const import DOMAIN
from .devices import DeviceError, DeviceManager
from .template import FORMATS

_COMMANDS: list[Any] = []


def _command(func: Any) -> Any:
    _COMMANDS.append(func)
    return func


@callback
def async_register(hass: HomeAssistant) -> None:
    for handler in _COMMANDS:
        websocket_api.async_register_command(hass, handler)


async def _log(admin: AdminHub, connection: websocket_api.ActiveConnection, action: str, msg: str,
               args: dict[str, Any], **extra: Any) -> None:
    """Panel changes go to the activity log next to the agents' ones."""
    user = connection.user.name if connection.user is not None else None
    await admin.activity.async_record("panel", action, msg, args, user=user, **extra)


def _port_name(admin: AdminHub, port_id: str) -> str:
    hub = admin.bus.ports.get(port_id)
    return hub.name if hub else "?"


def _admin(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> AdminHub | None:
    admin = hass.data.get(DOMAIN, {}).get("admin")
    if admin is None:
        connection.send_error(msg["id"], "not_loaded", "The WOOW Serial panel entry is not loaded")
    return admin


@_command
@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "woow_serial/snapshot"})
@callback
def ws_snapshot(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    if (admin := _admin(hass, connection, msg)) is not None:
        connection.send_result(msg["id"], admin.snapshot())


@_command
@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "woow_serial/subscribe"})
@callback
def ws_subscribe(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Live feed: {"kind": "frames" | "ports" | "catalog" | "mirror", ...}."""
    if (admin := _admin(hass, connection, msg)) is None:
        return

    @callback
    def forward(kind: str, payload: dict[str, Any]) -> None:
        connection.send_message(websocket_api.event_message(msg["id"], {"kind": kind, **payload}))

    connection.subscriptions[msg["id"]] = admin.subscribe(forward)
    connection.send_result(msg["id"])


@_command
@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "woow_serial/send",
    vol.Required("port_id"): str,
    vol.Optional("hex"): str,
    vol.Optional("text"): str,
    vol.Optional("wait_ms", default=0): vol.All(int, vol.Range(min=0, max=60000)),
})
@websocket_api.async_response
async def ws_send(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    if (admin := _admin(hass, connection, msg)) is None:
        return
    try:
        result = await admin.async_send(msg["port_id"], hex_data=msg.get("hex"), text=msg.get("text"),
                                        wait_ms=msg["wait_ms"])
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_format", str(err))
    except HomeAssistantError as err:
        connection.send_error(msg["id"], "send_failed", str(err))
    else:
        await _log(admin, connection, "send", "sent", {"hex": result["sent"], "port": _port_name(admin, msg["port_id"])},
                   port_id=msg["port_id"])
        connection.send_result(msg["id"], result)


@_command
@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "woow_serial/catalog/update_group",
    vol.Required("group_id"): str,
    vol.Optional("alias"): str,
    vol.Optional("hidden"): bool,
    vol.Optional("order"): vol.Coerce(float),
})
@callback
def ws_update_group(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    if (admin := _admin(hass, connection, msg)) is None:
        return
    if msg["group_id"] not in admin.catalog.groups:
        connection.send_error(msg["id"], "not_found", "No such group")
        return
    admin.catalog.update_group(msg["group_id"], alias=msg.get("alias"), hidden=msg.get("hidden"),
                               order=msg.get("order"))
    connection.send_result(msg["id"])


@_command
@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "woow_serial/catalog/update_row",
    vol.Required("row_id"): str,
    vol.Required("alias"): str,
})
@callback
def ws_update_row(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    if (admin := _admin(hass, connection, msg)) is None:
        return
    if msg["row_id"] not in admin.catalog.rows:
        connection.send_error(msg["id"], "not_found", "No such row")
        return
    admin.catalog.update_row(msg["row_id"], msg["alias"].strip())
    connection.send_result(msg["id"])


@_command
@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "woow_serial/catalog/delete",
    vol.Optional("group_id"): str,
    vol.Optional("row_id"): str,
})
@callback
def ws_delete(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    if (admin := _admin(hass, connection, msg)) is None:
        return
    if "row_id" in msg:
        admin.catalog.delete_row(msg["row_id"])
    if "group_id" in msg:
        admin.catalog.delete_group(msg["group_id"])
    connection.send_result(msg["id"])


@_command
@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "woow_serial/catalog/clear",
    vol.Optional("port_id"): str,
})
@callback
def ws_clear(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    if (admin := _admin(hass, connection, msg)) is not None:
        admin.catalog.clear(msg.get("port_id"))
        connection.send_result(msg["id"])


@_command
@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "woow_serial/catalog/prefix",
    vol.Required("port_id"): str,
    vol.Required("length"): vol.All(int, vol.Range(min=0, max=8)),
})
@callback
def ws_prefix(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    if (admin := _admin(hass, connection, msg)) is not None:
        admin.catalog.set_prefix(msg["port_id"], msg["length"])
        connection.send_result(msg["id"])


@_command
@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "woow_serial/mirror/delete",
    vol.Optional("row_id"): str,
})
@callback
def ws_mirror_delete(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    if (admin := _admin(hass, connection, msg)) is not None:
        admin.mirror.delete(msg.get("row_id"))
        connection.send_result(msg["id"])


@_command
@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "woow_serial/devices/save",
    vol.Required("device"): dict,
})
@websocket_api.async_response
async def ws_device_save(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Create or replace a device (commands, mapping, rules and sensors in one go)."""
    if (admin := _admin(hass, connection, msg)) is None:
        return
    existed = msg["device"].get("id") in admin.devices.devices
    try:
        device = await admin.devices.async_save_device(msg["device"])
    except DeviceError as err:
        connection.send_result(msg["id"], {"error": err.as_dict()})
        return
    await _log(admin, connection, "save_device", "device_updated" if existed else "device_created",
               {"device": device.name, "type": device.type, "port": _port_name(admin, device.port_id)},
               device_id=device.id, port_id=device.port_id)
    connection.send_result(msg["id"], {"device": admin.devices.device_dict(device)})


@_command
@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "woow_serial/templates/create",
    vol.Required("template"): str,
    vol.Required("port_id"): str,
    vol.Optional("name", default=""): str,
    vol.Optional("params", default={}): {str: str},
})
@websocket_api.async_response
async def ws_template_create(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """A device from a template, created in the panel."""
    if (admin := _admin(hass, connection, msg)) is None:
        return
    template = admin.templates.get(msg["template"])
    if template is None:
        connection.send_error(msg["id"], "not_found", "No such template")
        return
    raw = template.instantiate(msg["port_id"], msg["name"], msg["params"], hass.config.language or "en")
    try:
        device = await admin.devices.async_save_device(raw)
    except DeviceError as err:
        connection.send_result(msg["id"], {"error": err.as_dict()})
        return
    await _log(admin, connection, "create_from_template", "device_from_template",
               {"device": device.name, "type": device.type, "port": _port_name(admin, device.port_id),
                "template": template.id}, device_id=device.id, port_id=device.port_id)
    connection.send_result(msg["id"], {"device": admin.devices.device_dict(device)})


@_command
@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "woow_serial/devices/delete",
    vol.Required("device_id"): str,
})
@websocket_api.async_response
async def ws_device_delete(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    if (admin := _admin(hass, connection, msg)) is not None:
        device = admin.devices.devices.get(msg["device_id"])
        await admin.devices.async_delete_device(msg["device_id"])
        if device is not None:
            await _log(admin, connection, "delete_device", "device_deleted", {"device": device.name},
                       device_id=device.id, port_id=device.port_id)
        connection.send_result(msg["id"])


@_command
@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "woow_serial/devices/run",
    vol.Required("device_id"): str,
    vol.Required("command_id"): str,
    vol.Optional("value"): vol.Coerce(float),
})
@websocket_api.async_response
async def ws_device_run(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Test one command of a saved device from the editor."""
    if (admin := _admin(hass, connection, msg)) is None:
        return
    if msg["device_id"] not in admin.devices.devices:
        connection.send_error(msg["id"], "not_found", "No such device")
        return
    try:
        sent, reply = await admin.devices.async_command(msg["device_id"], msg["command_id"], msg.get("value"))
    except HomeAssistantError as err:
        connection.send_error(msg["id"], "send_failed", str(err))
        return
    device = admin.devices.devices[msg["device_id"]]
    command = device.command(msg["command_id"])
    await _log(admin, connection, "run_command", "command_tested",
               {"device": device.name, "command": command.name if command else "?", "hex": to_hex(sent)},
               device_id=device.id, port_id=device.port_id)
    connection.send_result(msg["id"], {"sent": to_hex(sent), "reply": None if reply is None else to_hex(reply)})


@_command
@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "woow_serial/template/preview",
    vol.Required("payload"): str,
    vol.Required("format"): vol.In(FORMATS),
    vol.Optional("params", default={}): {str: str},
    vol.Optional("value"): vol.Coerce(float),
})
@callback
def ws_template_preview(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """What a command template sends with these parameters (or why it cannot)."""
    connection.send_result(msg["id"], DeviceManager.preview(msg["payload"], msg["format"], msg["params"],
                                                            msg.get("value")))


@_command
@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "woow_serial/pattern/test",
    vol.Required("pattern"): str,
    vol.Required("format"): vol.In(FORMATS),
    vol.Required("port_id"): str,
    vol.Optional("params", default={}): {str: str},
})
@callback
def ws_pattern_test(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Try a receive pattern on the frames the monitor holds for that port."""
    if (admin := _admin(hass, connection, msg)) is None:
        return
    connection.send_result(msg["id"], DeviceManager.test_pattern(
        msg["pattern"], msg["format"], msg["params"], admin.recent_frames(msg["port_id"])))


@_command
@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "woow_serial/listen",
    vol.Required("port_id"): str,
    vol.Optional("timeout", default=15): vol.All(vol.Coerce(float), vol.Range(min=1, max=120)),
})
@websocket_api.async_response
async def ws_listen(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Wait for the next frame on a port (press the physical button now)."""
    if (admin := _admin(hass, connection, msg)) is None:
        return
    data = await admin.async_listen(msg["port_id"], msg["timeout"])
    if data is None:
        connection.send_result(msg["id"], {"timeout": True})
    else:
        connection.send_result(msg["id"], {"hex": to_hex(data), "text": printable(data) if is_text(data) else None})


@_command
@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "woow_serial/checksum",
    vol.Required("hex"): str,
    vol.Optional("algorithm"): vol.In(list(checksum.ALGORITHMS)),
    vol.Optional("start", default=0): vol.All(int, vol.Range(min=0, max=16)),
})
@callback
def ws_checksum(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Name the checksum a frame ends in, or append one to a frame being typed."""
    try:
        data = parse_hex(msg["hex"])
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_format", str(err))
        return
    result: dict[str, Any] = {"detected": checksum.detect(data), "algorithms": list(checksum.ALGORITHMS)}
    if "algorithm" in msg:
        value = checksum.compute(msg["algorithm"], data, msg["start"])
        result.update(value=to_hex(value), frame=to_hex(data + value))
    connection.send_result(msg["id"], result)
