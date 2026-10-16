"""Move a Pi from woow_bus (0.2, serial + CAN in one integration) to woow_serial + woow_can.

Run in the SSH add-on, in two steps around the reinstall / restart:

    python3 migrate_from_woow_bus.py export   # save entries + devices, then delete the woow_bus entries
    python3 migrate_from_woow_bus.py import   # re-add every port through the real config flows,
                                              # then bring the managed devices over to woow_serial
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wsclient import WS, rest  # noqa: E402

SAVED = "/homeassistant/woow_bus_migration.json"
STRINGS = {"baudrate", "bytesize", "stopbits", "bitrate", "dbitrate"}  # select fields take strings


def export():
    entries = json.load(open("/homeassistant/.storage/core.config_entries"))["data"]["entries"]
    old = [e for e in entries if e["domain"] == "woow_bus"]
    try:
        devices = json.load(open("/homeassistant/.storage/woow_bus.devices"))["data"]["devices"]
    except FileNotFoundError:
        devices = []
    saved = {"entries": [{k: e[k] for k in ("entry_id", "title", "data", "options")} for e in old],
             "devices": devices}
    json.dump(saved, open(SAVED, "w"), ensure_ascii=False, indent=1)
    print(f"saved {len(old)} entries and {len(devices)} devices to {SAVED}")
    for e in old:
        print(f"  delete {e['title']:14s} ({e['data'].get('kind')}):", rest("DELETE", f"/config/config_entries/entry/{e['entry_id']}"))


def _submit(flow, values):
    """Fill a form with the values it asks for (selects as strings)."""
    names = {f["name"] for f in flow["data_schema"]}
    data = {k: (str(v) if k in STRINGS else v) for k, v in values.items() if k in names}
    if "parity" in data:  # selector keys are lowercase since 0.4.1
        data["parity"] = str(data["parity"]).lower()
    return rest("POST", f"/config/config_entries/flow/{flow['flow_id']}", data)


def _import():
    saved = json.load(open(SAVED))
    titles = {}
    for e in saved["entries"]:
        kind, title = e["data"]["kind"], e["title"]
        if kind == "hub":
            continue
        if kind == "can":
            flow = rest("POST", "/config/config_entries/flow", {"handler": "woow_can"})
            flow = rest("POST", f"/config/config_entries/flow/{flow['flow_id']}", {"port": e["data"]["port"]})
            done = _submit(flow, {"name": title, **e["options"]})
        elif kind == "serial":
            flow = rest("POST", "/config/config_entries/flow", {"handler": "woow_serial"})
            flow = rest("POST", f"/config/config_entries/flow/{flow['flow_id']}", {"next_step_id": "local"})
            flow = rest("POST", f"/config/config_entries/flow/{flow['flow_id']}", {"port": e["data"]["port"]})
            done = _submit(flow, {"name": title, **e["options"]})
        else:  # external
            flow = rest("POST", "/config/config_entries/flow", {"handler": "woow_serial"})
            flow = rest("POST", f"/config/config_entries/flow/{flow['flow_id']}", {"next_step_id": "external"})
            flow = rest("POST", f"/config/config_entries/flow/{flow['flow_id']}",
                        {"device_id": e["data"]["device_id"]} if e["data"].get("device_id") else {})
            done = _submit(flow, {"name": title, **e["options"]})
        print(f"  {title:14s} ({kind}): {done['type']}" + (f" {done.get('errors')}" if done["type"] == "form" else ""))
        if done["type"] == "create_entry":
            titles[e["entry_id"]] = done["result"]["entry_id"]
    time.sleep(5)  # the panel entry is created on the first setup of woow_serial
    w = WS()
    for raw in saved["devices"]:
        raw = dict(raw, port_id=titles.get(raw["port_id"], raw["port_id"]))
        res = w.call("woow_serial/devices/save", device=raw)
        print(f"  device {raw['name']}: {'ok' if 'device' in res else res}")
    entries = w.call("config_entries/get", domain="woow_serial") + w.call("config_entries/get", domain="woow_can")
    for e in entries:
        print(f"  {e['domain']:12s} {e['title']:14s} {e['state']}")


if __name__ == "__main__":
    export() if sys.argv[1:] == ["export"] else _import()
