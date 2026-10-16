"""Device templates: ready-made definitions of real RS485 / RS232 equipment.

A template is a JSON file holding everything a managed device needs (commands, entity actions,
state feedback, sensors, buttons) plus the line settings the equipment expects and the
parameters an installation fills in (usually the device address). Built-in templates ship in
templates/; local ones can be dropped into <config>/woow_serial/templates/. Agents and people
create a device from one with a single call (create_from_template).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
import json
import logging
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant

from .devices import DEVICE_TYPES, Device, DeviceError, validate

_LOGGER = logging.getLogger(__name__)
BUILTIN_DIR = Path(__file__).parent / "templates"
LOCAL_SUBDIR = "woow_serial/templates"
LANGUAGES = ("en", "zh-Hant")


def _lang(language: str) -> str:
    return "zh-Hant" if language.lower().startswith("zh") else "en"


def localize(value: Any, language: str) -> Any:
    """Resolve {"en": ..., "zh-Hant": ...} texts anywhere in a template's device (names of commands,
    sensors, buttons and options, rule values that name an option) to one language."""
    if isinstance(value, dict):
        if value and set(value) <= set(LANGUAGES) and all(isinstance(v, str) for v in value.values()):
            return value.get(_lang(language)) or value.get("en") or next(iter(value.values()))
        return {k: localize(v, language) for k, v in value.items()}
    if isinstance(value, list):
        return [localize(v, language) for v in value]
    return value


@dataclass
class Template:
    id: str
    name: dict[str, str]
    brand: str
    model: str
    type: str
    description: dict[str, str]
    port: dict[str, Any]  # recommended line settings: bus (rs485 / rs232), baudrate, bytesize, parity, stopbits
    params: list[dict[str, Any]]  # {key, default, description: {en, zh-Hant}}
    device: dict[str, Any]  # Device fields: commands, actions, options, rules, sensors, buttons, ranges, poll
    references: list[str] = field(default_factory=list)  # protocol documents the template follows
    notes: dict[str, str] = field(default_factory=dict)
    source: str = "builtin"

    def text(self, attr: str, language: str) -> str:
        values: dict[str, str] = getattr(self, attr)
        return values.get(_lang(language)) or values.get("en") or next(iter(values.values()), "")

    def summary(self, language: str) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.text("name", language),
            "brand": self.brand,
            "model": self.model,
            "type": self.type,
            "description": self.text("description", language),
            "port": self.port,
            "params": [{"key": p["key"], "default": p.get("default", ""),
                        "description": localize(p.get("description") or "", language)} for p in self.params],
            "commands": [localize(c["name"], language) for c in self.device.get("commands", [])],
            "options": [localize(o["name"], language) for o in self.device.get("options", [])],
            "buttons": [localize(b["name"], language) for b in self.device.get("buttons", [])],
            "notes": self.text("notes", language) if self.notes else "",
            "references": self.references,
            "source": self.source,
        }

    def instantiate(self, port_id: str, name: str, params: dict[str, Any] | None, language: str) -> dict[str, Any]:
        """A device definition ready for DeviceManager.async_save_device (ids are filled in there)."""
        raw = localize(copy.deepcopy(self.device), language)
        values = {p["key"]: str(p.get("default", "")) for p in self.params}
        values.update({str(k): str(v) for k, v in (params or {}).items()})
        raw.update({"name": name or self.text("name", language), "type": self.type, "port_id": port_id,
                    "manufacturer": self.brand, "model": self.model, "params": values})
        return raw


def _read(directory: Path, source: str) -> tuple[list[Template], list[str]]:
    """Blocking: parse and validate every template file in a folder."""
    found: list[Template] = []
    problems: list[str] = []
    if not directory.is_dir():
        return found, problems
    for path in sorted(directory.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            template = Template(**{k: v for k, v in raw.items() if k in Template.__dataclass_fields__}, source=source)
            if template.type not in DEVICE_TYPES:
                raise DeviceError("bad_type", type=template.type)
            for language in LANGUAGES:
                probe = Device.from_dict({**template.instantiate("probe", "probe", None, language), "id": "probe"})
                validate(probe)
        except (OSError, ValueError, TypeError, KeyError) as err:  # DeviceError / TemplateError are ValueErrors
            problems.append(f"{path.name}: {err}")
            continue
        found.append(template)
    return found, problems


class TemplateLibrary:
    """Built-in and local templates, by id (a local template overrides a built-in one of the same id)."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.templates: dict[str, Template] = {}
        self.problems: list[str] = []

    async def async_load(self) -> None:
        local = Path(self.hass.config.path(LOCAL_SUBDIR))

        def load() -> tuple[list[Template], list[str]]:
            builtin, problems = _read(BUILTIN_DIR, "builtin")
            mine, more = _read(local, "local")
            return builtin + mine, problems + more

        templates, self.problems = await self.hass.async_add_executor_job(load)
        self.templates = {t.id: t for t in templates}
        for problem in self.problems:
            _LOGGER.warning("Skipping device template %s", problem)

    def get(self, template_id: str) -> Template | None:
        return self.templates.get(template_id)

    def summaries(self, language: str, device_type: str | None = None) -> list[dict[str, Any]]:
        return [t.summary(language) for t in sorted(self.templates.values(), key=lambda t: (t.type, t.brand, t.id))
                if device_type is None or t.type == device_type]
