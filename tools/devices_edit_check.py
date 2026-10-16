"""Editing a device keeps its entity ids, adds / removes command buttons, and keeps it working."""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wsclient import WS, rest  # noqa: E402

w = WS()


def device(name):
    return next(d for d in w.call("woow_serial/snapshot")["devices"]["devices"] if d["name"] == name)


def save(dev):
    dev = {k: v for k, v in dev.items() if k != "entities"}
    res = w.call("woow_serial/devices/save", device=dev)
    assert "device" in res, res
    time.sleep(2)


before = device("測試窗簾")
print("before:", before["entities"])
added = dict(before, commands=before["commands"] + [{"name": "微調", "payload": "55 {addr} 03 05 {crc16_modbus}"}])
save(added)
middle = device("測試窗簾")
print("added:", sorted(set(middle["entities"]) - set(before["entities"])),
      "lost:", sorted(set(before["entities"]) - set(middle["entities"])))
save(dict(middle, commands=[c for c in middle["commands"] if c["name"] != "微調"]))
after = device("測試窗簾")
print("removed again:", sorted(set(middle["entities"]) - set(after["entities"])),
      "same as before:", sorted(after["entities"]) == sorted(before["entities"]))
cover = next(e for e in after["entities"] if e.startswith("cover."))
state = rest("GET", f"/states/{cover}")
print(f"{cover}: {state['state']} position={state['attributes'].get('current_position')}")
rest("POST", "/services/cover/stop_cover", {"entity_id": cover})
time.sleep(1.5)
last = next(r for r in w.call("woow_serial/snapshot")["mirror"]["rows"] if r["origin"].startswith("device:"))
print("stop sent after edits:", last["hex"], "heard_by:", list(last["heard_by"]))
reg = w.call("config/device_registry/list")
dev_reg = next(d for d in reg if ["woow_serial", f"device_{after['id']}"] in [list(i) for i in d["identifiers"]])
parent = next((d for d in reg if d["id"] == dev_reg["via_device_id"]), None)
print("HA device:", dev_reg["name"], "| via:", parent and parent["name"])
