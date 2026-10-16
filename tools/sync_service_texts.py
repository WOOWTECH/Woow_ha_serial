"""Copy the English service and field texts from translations/en.json into services.yaml.

Home Assistant's frontend reads service texts from the translations, but MCP servers such as
ha-mcp (8.7) only show the `name` / `description` written in services.yaml, so both carry them.
Run after changing en.json:  uv run --with pyyaml python tools/sync_service_texts.py
tests/test_woow_serial.py checks that the two agree.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parents[1] / "custom_components" / "woow_serial"


def synced(services: dict, texts: dict) -> dict:
    out: dict = {}
    for name, spec in services.items():
        spec = dict(spec or {})
        text = texts.get(name, {})
        entry: dict = {"name": text.get("name", name), "description": text.get("description", "")}
        fields = {}
        for field, config in (spec.get("fields") or {}).items():
            field_text = (text.get("fields") or {}).get(field, {})
            config = {k: v for k, v in (config or {}).items() if k not in ("name", "description")}
            fields[field] = {"name": field_text.get("name", field), "description": field_text.get("description", ""),
                             **config}
        if fields:
            entry["fields"] = fields
        out[name] = {**entry, **{k: v for k, v in spec.items() if k not in ("name", "description", "fields")}}
    return out


def main() -> None:
    path = HERE / "services.yaml"
    services = yaml.safe_load(path.read_text(encoding="utf-8"))
    texts = json.loads((HERE / "translations" / "en.json").read_text(encoding="utf-8"))["services"]
    result = synced(services, texts)
    path.write_text(yaml.safe_dump(result, allow_unicode=True, sort_keys=False, width=110), encoding="utf-8")
    print(f"services.yaml: {len(result)} services synced from en.json")


if __name__ == "__main__":
    main()
