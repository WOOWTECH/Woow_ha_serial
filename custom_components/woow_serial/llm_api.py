"""Tools for Home Assistant's own MCP server and conversation agents: the "WOOW Serial" LLM API.

ha-mcp calls the services directly. Home Assistant's MCP server (mcp_server) only offers tools
from LLM APIs, so the same services are offered here as tools, built from services.yaml and the
English service texts. It is an API of its own, not part of Assist: a voice assistant gets no bus
access unless someone picks this API for it. The MCP server serves it to admins, either among
"all LLM APIs" (tools named woow_serial__<service>) or alone at /api/mcp/woow_serial.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import probatio

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, llm, selector
from homeassistant.util.yaml import load_yaml_dict

from .const import DOMAIN

API_NAME = "WOOW Serial"
READ_ONLY = {"describe", "list_ports", "get_monitor", "get_send_log", "listen", "list_devices", "get_device",
             "preview_command", "test_pattern", "list_templates", "get_activity"}
REPLACES = {"save_device", "delete_device"}  # overwrite or remove what is there
IDEMPOTENT = READ_ONLY | REPLACES
# Hints in the service texts that are for direct service calls; a tool always asks for the response.
_SERVICE_HINTS = (" Call it with return_response: true.", " Add return_response: true to get the result.")
PROMPT = (
    "WOOW Serial controls RS485 / RS232 equipment through Home Assistant. Call describe first: it explains "
    "the workflow, the device definition and the template syntax, and lists ports, templates and devices. "
    "Prefer create_from_template when the equipment is a known model. Ports, devices and commands can be "
    "named by their names. Give every change a short note in the language the user speaks with you: people "
    "review the changes in the activity log of the WOOW Serial panel. A device's entities (cover, light, "
    "switch, media_player, select) are operated like any other Home Assistant entity; run_command sends a "
    "device's own commands."
)


class ServiceTool(llm.Tool):
    """One WOOW Serial service as a tool; errors come back as data the model can act on."""

    integration = DOMAIN

    def __init__(self, service: str, title: str | None, description: str, parameters: probatio.Schema) -> None:
        self.name = service
        self.title = title
        self.description = description
        self.parameters = parameters
        read_only = service in READ_ONLY
        self.annotations = llm.ToolAnnotations(read_only=read_only, destructive=service in REPLACES,
                                               idempotent=service in IDEMPOTENT, open_world=not read_only)

    async def async_call(self, hass: HomeAssistant, tool_input: llm.ToolInput,
                         llm_context: llm.LLMContext) -> llm.ToolResult:
        try:
            result = await hass.services.async_call(DOMAIN, self.name, tool_input.tool_args, blocking=True,
                                                    context=llm_context.context, return_response=True)
        except HomeAssistantError as err:  # a ServiceValidationError says what to fix
            return llm.ToolResult(data={"error": str(err)}, error=True)
        return llm.ToolResult(data=dict(result or {}))


def _read() -> tuple[dict[str, Any], dict[str, Any]]:
    """Blocking: services.yaml and the English service texts."""
    here = Path(__file__).parent
    services = load_yaml_dict(str(here / "services.yaml"))
    texts = json.loads((here / "translations" / "en.json").read_text(encoding="utf-8"))["services"]
    return services, texts


def build_tools(services: dict[str, Any], texts: dict[str, Any]) -> list[llm.Tool]:
    tools: list[llm.Tool] = []
    for name, spec in services.items():
        text = texts.get(name, {})
        schema: dict[Any, Any] = {}
        for field, config in ((spec or {}).get("fields") or {}).items():
            config = config or {}
            field_text = (text.get("fields") or {}).get(field, {})
            description = field_text.get("description") or field_text.get("name") or field
            if config.get("example") is not None:
                description += f" Example: {config['example']}"
            marker = probatio.Required if config.get("required") else probatio.Optional
            key = marker(field, description=description)
            schema[key] = selector.selector(config["selector"]) if config.get("selector") else cv.string
        description = text.get("description", "")
        for hint in _SERVICE_HINTS:
            description = description.replace(hint, "")
        tools.append(ServiceTool(name, text.get("name"), description, probatio.Schema(schema)))
    return tools


class WoowSerialAPI(llm.API):
    """The WOOW Serial services as LLM tools."""

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(hass=hass, id=DOMAIN, name=API_NAME)
        self._tools: list[llm.Tool] | None = None

    async def async_get_api_instance(self, llm_context: llm.LLMContext) -> llm.APIInstance:
        if self._tools is None:
            self._tools = build_tools(*await self.hass.async_add_executor_job(_read))
        return llm.APIInstance(api=self, api_prompt=PROMPT, llm_context=llm_context, tools=self._tools,
                               custom_serializer=llm.selector_serializer)


def async_register(hass: HomeAssistant) -> None:
    llm.async_register_api(hass, WoowSerialAPI(hass))
