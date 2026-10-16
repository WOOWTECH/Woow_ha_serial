"""WOOW Serial: RS485 / RS232 ports (on-board or bound from other integrations) and their admin panel."""

from __future__ import annotations

import logging
import time

import voluptuous as vol

from homeassistant.config_entries import SOURCE_SYSTEM, ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import ConfigEntryNotReady, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from . import checksum, llm_api, services as agent_services, websocket_api
from .admin import AdminHub
from .bus import get_bus
from .codec import describe, parse_hex, unescape
from .const import ATTR_ENTRY, CONF_KIND, DOMAIN, KIND_EXTERNAL, KIND_HUB, SERVICE_SEND
from .external import ExternalHub
from .hub import Hub, SerialHub
from .template import Pattern, TemplateError

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.EVENT, Platform.SENSOR, Platform.TEXT]  # each port
HUB_PLATFORMS = [  # entities of the devices managed from the panel
    Platform.BUTTON, Platform.COVER, Platform.EVENT, Platform.LIGHT, Platform.MEDIA_PLAYER,
    Platform.SELECT, Platform.SENSOR, Platform.SWITCH,
]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_WAIT = vol.All(vol.Coerce(int), vol.Range(min=0, max=60000))
EXPECT_WAIT = 2.0  # s, when `expect` is given without wait_ms
SEND_SCHEMA = vol.Schema({
    vol.Exclusive(ATTR_ENTRY, "target"): cv.string,
    vol.Exclusive("port", "target"): cv.string,  # a port name (RS485-1) or path, handy for agents
    vol.Exclusive("hex", "payload"): cv.string,
    vol.Exclusive("text", "payload"): cv.string,
    vol.Optional("wait_ms", default=0): _WAIT,
    vol.Optional("expect"): cv.string,  # wait for the first frame matching this receive pattern
    vol.Optional("note", default=""): cv.string,
})


def _invalid(key: str, **placeholders: str) -> ServiceValidationError:
    return ServiceValidationError(translation_domain=DOMAIN, translation_key=key,
                                  translation_placeholders=placeholders or None)


def _port(hass: HomeAssistant, entry_id: str) -> Hub:
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED:
        raise _invalid("not_loaded", entry=entry_id)
    if entry.data[CONF_KIND] == KIND_HUB:
        raise _invalid("not_a_port", name=entry.title)
    return entry.runtime_data


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the send service and the panel's websocket commands, and offer the panel once."""
    get_bus(hass)
    websocket_api.async_register(hass)

    async def send(call: ServiceCall) -> ServiceResponse:
        if ATTR_ENTRY in call.data:
            hub = _port(hass, call.data[ATTR_ENTRY])
        elif "port" in call.data:
            hub = agent_services.resolve_port(agent_services._admin(hass), call.data["port"])
        else:
            raise _invalid("no_port")
        try:
            if "hex" in call.data:
                data = parse_hex(call.data["hex"])
            elif "text" in call.data:
                data = unescape(call.data["text"]) + hub.line_ending
            else:
                raise _invalid("no_payload")
        except ValueError as err:
            raise _invalid("bad_hex" if "hex" in call.data else "bad_text", error=str(err)) from err
        wait = call.data["wait_ms"] / 1000
        expect = None
        if call.data.get("expect"):
            try:
                expect = Pattern(call.data["expect"], "text" if "text" in call.data else "hex", {})
            except TemplateError as err:
                raise _invalid("bad_expect", error=str(err)) from err
            wait = wait or EXPECT_WAIT
        admin = hass.data[DOMAIN].get("admin")
        started = time.monotonic()
        if expect is not None and admin is not None:  # skip whatever else the line carries meanwhile
            pending = admin.expect_frame(hub.entry.entry_id, lambda frame: expect.match(frame) is not None)
            try:
                await hub.async_send(data, 0, origin="service")
            except BaseException:
                admin.forget_frame(hub.entry.entry_id, pending)
                raise
            reply = await admin.async_wait_frame(hub.entry.entry_id, pending, wait)
        else:
            reply = await hub.async_send(data, wait, origin="service")
        elapsed = round((time.monotonic() - started) * 1000)
        if admin is not None and (call.context.user_id or call.data["note"]):  # people / agents, not automations
            await admin.activity.async_record(
                "service", "send", "sent", {"hex": describe(data)["hex"], "port": hub.name}, context=call.context,
                note=call.data["note"], port_id=hub.entry.entry_id)
        if not call.return_response:
            return None
        response: dict = {"port": hub.name, "sent": describe(data)}
        if wait > 0:
            response["reply"] = {**describe(reply), "checks": checksum.detect(reply)} if reply is not None else None
            if reply is not None and expect is not None:
                response["reply"]["captures"] = expect.match(reply)
            response["timeout"] = reply is None
            response["elapsed_ms"] = elapsed
        return response

    hass.services.async_register(DOMAIN, SERVICE_SEND, agent_services.validated(hass, SEND_SCHEMA, send),
                                 schema=None, supports_response=SupportsResponse.OPTIONAL)
    agent_services.async_register(hass)
    llm_api.async_register(hass)  # the same services as tools for Home Assistant's MCP server
    hass.async_create_task(_async_offer_panel(hass))
    return True


async def _async_offer_panel(hass: HomeAssistant) -> None:
    """Add the panel entry the first time the integration runs; a user who removes it keeps it removed."""
    if any(e.data.get(CONF_KIND) == KIND_HUB for e in hass.config_entries.async_entries(DOMAIN)):
        return
    store: Store[dict] = Store(hass, 1, f"{DOMAIN}.meta")
    meta = await store.async_load() or {}
    if meta.get("panel_offered"):
        return
    await store.async_save({**meta, "panel_offered": True})
    await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_SYSTEM})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    kind = entry.data[CONF_KIND]
    if kind == KIND_HUB:
        admin = AdminHub(hass, entry)
        await admin.async_start()
        entry.runtime_data = admin
        hass.data[DOMAIN]["admin"] = admin
        await hass.config_entries.async_forward_entry_setups(entry, HUB_PLATFORMS)
        return True
    hub: Hub = ExternalHub(hass, entry) if kind == KIND_EXTERNAL else SerialHub(hass, entry)
    try:
        await hub.async_start()
    except (OSError, ValueError) as err:
        await hub.async_stop()
        raise ConfigEntryNotReady(f"{entry.title} ({hub.port}): {err}") from err
    entry.runtime_data = hub
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if entry.data[CONF_KIND] == KIND_HUB:
        if not await hass.config_entries.async_unload_platforms(entry, HUB_PLATFORMS):
            return False
        await entry.runtime_data.async_stop()
        hass.data[DOMAIN].pop("admin", None)
        return True
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_stop()
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """A removed port takes its monitor rows with it."""
    admin: AdminHub | None = hass.data.get(DOMAIN, {}).get("admin")
    if admin is not None and entry.data[CONF_KIND] != KIND_HUB:
        admin.catalog.clear(entry.entry_id)


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
