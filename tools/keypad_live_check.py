"""Live check of keypads (phase 3) on the Pi (run in the SSH add-on).

The HA-WF485-V3 f507a4 plays a wall keypad on the RS485-1 line. Checks:
- a press fires woow_serial_button and moves the keypad's event entity;
- an automation built on the device trigger ("button pressed") runs, and still runs after the
  button is renamed and automations are reloaded (alias history);
- bindings drive other devices by themselves (open the test curtain, toggle the test projector).
"""

import json
import os
import sys
import threading
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wsclient import TOKEN, WS, rest  # noqa: E402

w = WS()
events = []


def listen():
    lw = WS()
    for i, event_type in enumerate(("woow_serial_button", "woow_serial_test_ok"), 1):
        lw.send({"id": i, "type": "subscribe_events", "event_type": event_type})
    lw.sock.settimeout(None)
    while True:
        msg = lw.recv()
        if msg.get("type") == "event":
            events.append((msg["event"]["event_type"], msg["event"]["data"]))


threading.Thread(target=listen, daemon=True).start()
time.sleep(1)

snap = w.call("woow_serial/snapshot")
ports = {p["name"]: p["id"] for p in snap["ports"]}
devices = {d["name"]: d for d in snap["devices"]["devices"]}
for d in devices.values():
    if d["name"] == "測試面板":
        w.call("woow_serial/devices/delete", device_id=d["id"])
curtain, projector = devices["測試窗簾"], devices["測試投影機"]
print("bindable on the curtain:", curtain["bindable"])
res = w.call("woow_serial/devices/save", device={
    "name": "測試面板", "type": "keypad", "port_id": ports["RS485-1"],
    "buttons": [
        {"name": "情境1", "pattern": "A5 5A 01 ??"},
        {"name": "開窗簾", "pattern": "A5 5A 02 01", "target": curtain["id"], "action": "open"},
        {"name": "投影機", "pattern": "A5 5A 03 {n:u8}", "target": projector["id"], "action": "toggle"},
    ],
})
assert "device" in res, res
keypad = res["device"]
time.sleep(2)
keypad = next(d for d in w.call("woow_serial/snapshot")["devices"]["devices"] if d["id"] == keypad["id"])
event_entity = next(e for e in keypad["entities"] if e.startswith("event."))
print("keypad entities:", keypad["entities"])
ha_device = next(d for d in w.call("config/device_registry/list")
                 if ["woow_serial", f"device_{keypad['id']}"] in [list(i) for i in d["identifiers"]])
print("device triggers offered:", [t["subtype"] for t in w.call("device_automation/trigger/list", device_id=ha_device["id"])])

automation_id = "woow_serial_keypad_test"
rest("POST", f"/config/automation/config/{automation_id}", {
    "id": automation_id, "alias": "WOOW 串口按鍵測試", "mode": "queued",
    "triggers": [{"trigger": "device", "domain": "woow_serial", "device_id": ha_device["id"],
                  "type": "button_pressed", "subtype": "情境1"}],
    "actions": [{"event": "woow_serial_test_ok", "event_data": {"button": "{{ trigger.event.data.button }}"}}],
})
time.sleep(3)


def press(data_hex):
    w.call("call_service", domain="text", service="set_value",
           target={"entity_id": "text.ha_wf485_v3_f507a4_hex_data_tx"}, service_data={"value": data_hex})
    time.sleep(3)


def summary(title):
    print(title)
    for kind, data in events:
        print(f"    {kind}: {data.get('button')} {data.get('hex', '')} {({k: v for k, v in data.items() if k == 'n'})}")
    events.clear()


press("A5 5A 01 07")
summary("press 情境1:")
state = rest("GET", f"/states/{event_entity}")
print(f"    {event_entity} = {state['state']} event_type={state['attributes'].get('event_type')}")

before = len([r for r in w.call("woow_serial/snapshot")["mirror"]["rows"] if r["origin"].startswith("device:")])
press("A5 5A 02 01")
summary("press 開窗簾 (binding → open the curtain):")
press("A5 5A 03 09")
summary("press 投影機 (binding → toggle the projector):")
rows = w.call("woow_serial/snapshot")["mirror"]["rows"]
names = {d["id"]: d["name"] for d in w.call("woow_serial/snapshot")["devices"]["devices"]}
for r in rows[:2]:
    print(f"    sent by {names.get(r['origin'][7:], r['origin'])}: {r['hex']} {r['text'] or ''}")

renamed = dict(keypad)
renamed.pop("entities", None)
renamed.pop("bindable", None)
renamed["buttons"] = [dict(b, name="場景一") if b["name"] == "情境1" else b for b in keypad["buttons"]]
assert "device" in w.call("woow_serial/devices/save", device=renamed)
rest("POST", "/services/automation/reload", {})
time.sleep(4)
print("device triggers after the rename:", [t["subtype"] for t in w.call("device_automation/trigger/list", device_id=ha_device["id"])])
press("A5 5A 01 08")
summary("press 場景一 (renamed; the automation still names 情境1):")

req = urllib.request.Request(f"http://supervisor/core/api/config/automation/config/{automation_id}", method="DELETE",
                             headers={"Authorization": "Bearer " + TOKEN})
print("test automation removed:", json.loads(urllib.request.urlopen(req, timeout=30).read()))
