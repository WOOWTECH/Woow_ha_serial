"""Exercise the agent services the way an MCP client does: REST service calls with return_response.

Run in the SSH add-on. Leaves nothing behind (the test device is deleted at the end).
"""

import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wsclient import TOKEN  # noqa: E402

results = []


def call(service, data=None, domain="woow_serial", response=True):
    url = f"http://supervisor/core/api/services/{domain}/{service}" + ("?return_response" if response else "")
    req = urllib.request.Request(url, method="POST", data=json.dumps(data or {}).encode(),
                                 headers={"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            body = json.loads(r.read() or b"{}")
            return r.status, body.get("service_response") if response else body
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode()[:300]


def check(name, ok, detail=""):
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")


status, d = call("describe")
check("describe", status == 200 and {"workflow", "device_types", "command_template", "ports"} <= set(d),
      f"{len(d.get('ports', []))} ports, {len(d.get('templates', []))} templates, types={list(d.get('device_types', {}))}")
status, d = call("list_ports")
names = [p["name"] for p in d["ports"]]
check("list_ports", status == 200 and "RS485-1" in names, names)
status, d = call("get_monitor", {"port": "RS485-1", "limit": 3})
check("get_monitor by port name", status == 200 and "groups" in d, f"{len(d['groups'])} groups")
status, d = call("get_send_log", {"limit": 3})
check("get_send_log", status == 200 and "sent" in d, f"{len(d['sent'])} rows")
status, d = call("list_devices", {"type": "cover"})
check("list_devices type=cover", status == 200 and all(x["type"] == "cover" for x in d["devices"]),
      [x["name"] for x in d["devices"]])
status, d = call("preview_command", {"payload": "55 {addr} 03 04 {value:u8} {crc16_modbus}", "params": {"addr": "01 02"}, "value": 50})
check("preview_command", status == 200 and d.get("sent", "").startswith("55 01 02 03 04 32"), d)
status, d = call("preview_command", {"payload": "55 {addr}", "params": {}})
check("preview_command error is data", status == 200 and d.get("error", {}).get("code") == "no_value", d)
status, d = call("test_pattern", {"pattern": "A5 5A ?? *", "port": "RS485-1"})
check("test_pattern", status == 200 and "matches" in d, f"{len(d.get('matches', []))} matches")
status, d = call("list_templates")
check("list_templates", status == 200 and "templates" in d, f"{len(d['templates'])} templates")
status, d = call("save_device", {"device": {"name": "AI 測試開關", "type": "switch", "port": "RS485-2",
                                            "commands": [{"name": "開", "payload": "A0 01 {nope}"}]}, "note": "故意寫錯"})
check("save_device invalid -> structured error", status == 200 and d.get("ok") is False and d["error"]["code"] == "command_template", d)
status, d = call("save_device", {"device": {
    "name": "AI 測試開關", "type": "switch", "port": "RS485-2",
    "commands": [{"name": "開", "payload": "A0 01 01 {sum8}"}, {"name": "關", "payload": "A0 01 00 {sum8}"}],
    "actions": {"turn_on": "開", "turn_off": "關"}}, "note": "AI 服務測試：建立開關"})
device = (d or {}).get("device", {})
check("save_device with names for ids", status == 200 and d.get("ok") and device.get("actions", {}).get("turn_on")
      and device["actions"]["turn_on"] != "開", {k: device.get(k) for k in ("id", "actions", "entities")})
status, d = call("run_command", {"device": "AI 測試開關", "command": "開", "note": "AI 服務測試：送出開"})
check("run_command by names", status == 200 and d.get("sent") == "A0 01 01 A2", d)
switch = next((e for e in device.get("entities", []) if e.startswith("switch.")), None)
status, _ = call("turn_on", {"entity_id": switch}, domain="switch", response=False)
check("entity action through HA", status == 200 and switch is not None, switch)
status, d = call("send", {"port": "RS485-2", "hex": "A0 01 02", "note": "AI 服務測試：直接送"})
check("send by port name", status == 200, d)
status, d = call("listen", {"port": "RS485-2", "timeout": 2})
check("listen times out cleanly", status == 200 and d.get("timeout") is True, d)
status, d = call("get_device", {"device": "AI 測試開關"})
check("get_device by name", status == 200 and d["device"]["name"] == "AI 測試開關", d["device"]["state"] if status == 200 else d)
status, d = call("get_activity", {"limit": 6})
entries = d.get("activity", []) if status == 200 else []
for e in entries:
    print(f"      activity: [{e['channel']}] {e['user']} {'ok' if e['ok'] else 'FAIL'} {e['summary']}  note={e['note']!r}")
check("activity has service + entity entries", {"service", "entity"} <= {e["channel"] for e in entries}, "")
status, d = call("delete_device", {"device": "AI 測試開關", "note": "AI 服務測試：清理"})
check("delete_device by name", status == 200 and d.get("ok"), d)
status, d = call("get_device", {"device": "nope"})
check("unknown device -> readable error", status == 400 and "nope" in str(d), str(d)[:160])
status, d = call("get_monitor", {"port": "RS999"})
check("unknown port -> readable error", status == 400 and "RS999" in str(d), str(d)[:160])
print(f"\n{sum(ok for _, ok in results)}/{len(results)} passed")
