"""Live check of managed devices (phase 2) on the Pi (run in the SSH add-on).

The two HA-WF485-V3 boards play the devices: f507a4 sits on the RS485-1 line and answers as a
curtain motor and a temperature sensor; 847767 sits on the RS232 line and answers as a projector.
Home Assistant drives the devices through their entities; the boards' answers must move the
entity states (state feedback), and every send must show up in the send log with the device as
its origin.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wsclient import WS, rest  # noqa: E402

w = WS()


def crc16(data: bytes) -> bytes:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return data + crc.to_bytes(2, "little")


def hx(data: bytes) -> str:
    return data.hex(" ").upper()


snap = w.call("woow_serial/snapshot")
ports = {p["name"]: p["id"] for p in snap["ports"]}
for d in snap["devices"]["devices"]:
    if d["name"].startswith("測試"):
        w.call("woow_serial/devices/delete", device_id=d["id"])


def save(device):
    res = w.call("woow_serial/devices/save", device=device)
    assert "device" in res, res
    return res["device"]


bad = w.call("woow_serial/devices/save", device={"name": "測試錯誤", "type": "cover", "port_id": ports["RS485-1"],
                                              "commands": [{"name": "開", "payload": "55 {addr} 03"}]})
print("invalid device refused:", bad)

curtain = save({
    "name": "測試窗簾", "type": "cover", "port_id": ports["RS485-1"], "manufacturer": "測試", "model": "RS485 馬達",
    "params": {"addr": "01 02"},
    "commands": [
        {"id": "open", "name": "開", "payload": "55 {addr} 03 01 {crc16_modbus}"},
        {"id": "close", "name": "關", "payload": "55 {addr} 03 02 {crc16_modbus}"},
        {"id": "stop", "name": "停", "payload": "55 {addr} 03 03 {crc16_modbus}"},
        {"id": "pos", "name": "到位置", "payload": "55 {addr} 03 04 {value:u8} {crc16_modbus}"},
        {"id": "query", "name": "查詢", "payload": "55 {addr} 01 02 01 {crc16_modbus}"},
    ],
    "actions": {"open": "open", "close": "close", "stop": "stop", "set_position": "pos"},
    "rules": [{"pattern": "55 {addr} 01 02 {pos:u8} {crc16_modbus}", "field": "position", "value": "{pos}"}],
})
projector = save({
    "name": "測試投影機", "type": "media_player", "port_id": ports["RS232"],
    "commands": [
        {"id": "on", "name": "開機", "format": "text", "payload": r"PWR ON\r"},
        {"id": "off", "name": "關機", "format": "text", "payload": r"PWR OFF\r"},
        {"id": "vol", "name": "音量", "format": "text", "payload": r"VOL {value:02d}\r"},
        {"id": "hdmi1", "name": "HDMI1", "format": "text", "payload": r"SOURCE 30\r"},
        {"id": "hdmi2", "name": "HDMI2", "format": "text", "payload": r"SOURCE A0\r"},
    ],
    "actions": {"turn_on": "on", "turn_off": "off", "set_volume": "vol"},
    "options": [{"name": "HDMI1", "command": "hdmi1"}, {"name": "HDMI2", "command": "hdmi2"}],
    "rules": [{"pattern": r"^PWR=(?P<p>\d+)", "format": "text", "field": "power", "value": "{p}"},
              {"pattern": r"^VOL=(?P<v>\d+)", "format": "text", "field": "volume", "value": "{v}"}],
    "ranges": {"volume": [0, 40]},
})
sensor = save({
    "name": "測試溫度", "type": "other", "port_id": ports["RS485-1"],
    "sensors": [{"name": "溫度", "pattern": "AA 01 {t:s16be} *", "capture": "t", "scale": 0.1, "unit": "°C",
                 "device_class": "temperature", "precision": 1}],
})
time.sleep(3)
devices = {d["name"]: d for d in w.call("woow_serial/snapshot")["devices"]["devices"]}
for name in ("測試窗簾", "測試投影機", "測試溫度"):
    print(f"{name}: {devices[name]['entities']}")
cover = next(e for e in devices["測試窗簾"]["entities"] if e.startswith("cover."))
player = next(e for e in devices["測試投影機"]["entities"] if e.startswith("media_player."))
temp = next(e for e in devices["測試溫度"]["entities"] if e.startswith("sensor."))
query_button = next(e for e in devices["測試窗簾"]["entities"] if e.startswith("button."))


def call(domain, service, entity_id, **data):
    rest("POST", f"/services/{domain}/{service}", {"entity_id": entity_id, **data})
    time.sleep(2.5)


def board(tag, data: bytes):
    w.call("call_service", domain="text", service="set_value",
           target={"entity_id": f"text.ha_wf485_v3_{tag}_hex_data_tx"}, service_data={"value": hx(data)})
    time.sleep(2.5)


def show(eid, *attrs):
    s = rest("GET", f"/states/{eid}")
    extra = {a: s["attributes"].get(a) for a in attrs}
    print(f"    {eid} = {s['state']} {extra if extra else ''}")
    return s


print("curtain:")
show(cover, "current_position", "supported_features", "assumed_state")
call("cover", "open_cover", cover)
show(cover, "current_position")
board("f507a4", crc16(bytes.fromhex("55010201021E")))  # motor reports 30 %
show(cover, "current_position")
call("cover", "set_cover_position", cover, position=70)
board("f507a4", crc16(bytes.fromhex("550102010246")))  # motor reports 70 %
show(cover, "current_position")
rest("POST", "/services/button/press", {"entity_id": query_button})
time.sleep(2)

print("projector:")
show(player, "volume_level", "source", "source_list", "assumed_state")
call("media_player", "turn_on", player)
board("847767", b"PWR=01\r")
board("847767", b"VOL=20\r")
show(player, "volume_level", "source")
call("media_player", "volume_set", player, volume_level=0.75)
call("media_player", "select_source", player, source="HDMI2")
show(player, "volume_level", "source")
call("media_player", "turn_off", player)
show(player)  # power has feedback: stays on until the projector says so
board("847767", b"PWR=00\r")
show(player)

print("sensor:")
board("f507a4", bytes.fromhex("AA0100FA00"))
show(temp, "unit_of_measurement", "device_class")

snap = w.call("woow_serial/snapshot")
names = {p["id"]: p["name"] for p in snap["ports"]}
devnames = {d["id"]: d["name"] for d in snap["devices"]["devices"]}
print("send log (device sends):")
for r in snap["mirror"]["rows"]:
    if r["origin"].startswith("device:"):
        print(f"  {devnames.get(r['origin'][7:], '?'):10s} {names.get(r['port_id'])}: {r['hex']:30s} "
              f"text={r['text']!r} heard_by={[names.get(k) for k in r['heard_by']]}")
print("device states:", {devnames.get(k, k): v for k, v in snap["devices"]["states"].items()})
