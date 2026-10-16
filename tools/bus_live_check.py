"""Live check of WOOW Serial on the Pi (run in the SSH add-on).

1. The panel entry exists and the sidebar panel is registered.
2. The two HA-WF485-V3 boards are bound as external ports through the real config flow.
3. Sends from the panel API on each side of the two wired loops (RS485-1 <-> f507a4,
   RS232 <-> 847767): the send log must show each one heard by the port on the other end,
   and none of them may land in the monitor (they are Home Assistant's own output).
4. Frames the WF485 boards send on their own (their text entity, outside WOOW Bus) must land
   in the monitor of the on-board port, grouped, with the Modbus CRC named.
"""

import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wsclient import WS, rest  # noqa: E402

w = WS()
entries = w.call("config_entries/get", domain="woow_serial")
print("config entries:")
for e in entries:
    print(f"  {e['title']:16s} {e['state']:12s} source={e['source']}")
panel = w.call("get_panels").get("woow-serial")
print("panel:", "registered" if panel else "MISSING", panel and panel.get("title"), panel and panel.get("url_path"))

BOARDS = {"f507a4": "WF485 f507a4", "847767": "WF485 847767"}
for tag, name in BOARDS.items():
    if any(e["title"] == name for e in entries):
        print(f"  {name}: already bound")
        continue
    device_id = w.call("config/entity_registry/get", entity_id=f"text.ha_wf485_v3_{tag}_hex_data_tx")["device_id"]
    flow = rest("POST", "/config/config_entries/flow", {"handler": "woow_serial"})
    assert flow["type"] == "menu", flow
    flow = rest("POST", f"/config/config_entries/flow/{flow['flow_id']}", {"next_step_id": "external"})
    assert flow.get("step_id") == "external", flow
    flow = rest("POST", f"/config/config_entries/flow/{flow['flow_id']}", {"device_id": device_id})
    assert flow.get("step_id") == "external_bind", flow
    form = {f["name"]: f for f in flow["data_schema"]}
    data = {k: f["default"] for k, f in form.items() if f.get("default") is not None}
    data.update({k: (f.get("description") or {}).get("suggested_value") for k, f in form.items()
                 if (f.get("description") or {}).get("suggested_value")})
    data["name"] = name
    print(f"  {name}: binding filled in from the device: "
          f"{ {k: v for k, v in data.items() if k.endswith('entity')} }")
    done = rest("POST", f"/config/config_entries/flow/{flow['flow_id']}", data)
    print(f"  {name}: {done['type']} -> {done.get('title')}")
time.sleep(3)

events = []


def feed():
    lw = WS()
    lw.send({"id": 1, "type": "woow_serial/subscribe"})
    lw.sock.settimeout(None)
    while True:
        msg = lw.recv()
        if msg.get("type") == "event":
            events.append(msg["event"])


threading.Thread(target=feed, daemon=True).start()
time.sleep(1)

snap = w.call("woow_serial/snapshot")
ports = {p["name"]: p for p in snap["ports"]}
names = {p["id"]: p["name"] for p in snap["ports"]}
print("ports:")
for p in snap["ports"]:
    print(f"  {p['name']:14s} {p['kind']:9s} {'online ' if p['available'] else 'OFFLINE'} {p['settings']:12s} {p['model']}")

print("panel sends (both ends of both loops):")
for port, data in (("RS485-1", "57 4F 4F 57 50 31"), ("WF485 f507a4", "A5 5A 50 32"),
                   ("RS232", "57 4F 4F 57 50 33"), ("WF485 847767", "A5 5A 50 34")):
    print(f"  {port:14s} {data:20s} -> {w.call('woow_serial/send', port_id=ports[port]['id'], hex=data)}")
    time.sleep(2.5)

print("frames the boards send by themselves (outside WOOW Bus):")
for tag, data in (("f507a4", "01 03 00 00 00 02 C4 0B"), ("f507a4", "01 06 00 01 00 03 98 0B"),
                  ("f507a4", "01 03 00 00 00 02 C4 0B"), ("847767", "50 57 52 20 4F 4E 0D")):
    w.call("call_service", domain="text", service="set_value",
           target={"entity_id": f"text.ha_wf485_v3_{tag}_hex_data_tx"}, service_data={"value": data})
    print(f"  {BOARDS[tag]} sent {data}")
    time.sleep(2.5)

snap = w.call("woow_serial/snapshot")
print("send log:")
for r in snap["mirror"]["rows"][:6]:
    print(f"  {names.get(r['port_id'], '?'):14s} {r['hex']:20s} x{r['count']} origin={r['origin']:6s} "
          f"replies={r['replies']} heard_by={[names.get(k) for k in r['heard_by']]}")
print("monitor:")
for g in sorted(snap["catalog"]["groups"], key=lambda g: g["order"]):
    rows = [r for r in snap["catalog"]["rows"] if r["group_id"] == g["id"]]
    print(f"  {names.get(g['port_id'], '?'):14s} [{g['key']}] count={g['count']} rows={g['rows']} checksum={g['checksum']}")
    for r in rows:
        print(f"      {r['hex']:26s} x{r['count']} text={r['text']!r} checks={r['checks']}")
kinds = {}
for e in events:
    kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
print("panel feed events:", kinds)
for e in events:
    if e["kind"] == "frames":
        for f in e["frames"]:
            print(f"  {names.get(f['port'], '?'):14s} {f['dir']} {f['hex']:24s} echo={f['echo']} origin={f['origin']}")
