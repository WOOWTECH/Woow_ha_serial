"""Pre-install check of custom_components/woow_serial inside the HA Core container (Python and HA as deployed)."""
import asyncio, glob, importlib, json, os, py_compile, sys

sys.path.insert(0, "/tmp/wstest")
BASE = "/tmp/wstest/custom_components/woow_serial"
import homeassistant  # noqa: F401  (installs probatio as `voluptuous` first, like HA itself does)

for f in sorted(glob.glob(BASE + "/*.py")):
    py_compile.compile(f, doraise=True)
for f in sorted(glob.glob(BASE + "/translations/*.json")) + [BASE + "/manifest.json"]:
    json.load(open(f, encoding="utf-8"))
import yaml
yaml.safe_load(open(BASE + "/services.yaml", encoding="utf-8"))
assert os.path.exists(BASE + "/frontend/woow-serial-panel.js"), "panel bundle missing"
print("compile / json / yaml / bundle: ok")

for m in ("const", "codec", "checksum", "bus", "serial_port", "hub", "external", "entity", "text", "sensor",
          "event", "catalog", "mirror", "template", "devices", "managed", "button", "switch", "light", "cover",
          "media_player", "select", "device_trigger", "panel", "admin", "websocket_api", "config_flow", "__init__"):
    importlib.import_module("custom_components.woow_serial" + ("" if m == "__init__" else "." + m))
print("imports against this HA version: ok")

from custom_components.woow_serial.codec import parse_hex, printable, unescape
assert parse_hex("A5 5A 0x01,02:03-04") == bytes.fromhex("A55A01020304")
assert unescape(r"PWR ON\r\x02\\") == b"PWR ON\r\x02\\"
assert printable(b"OK\r\n\x02\\") == r"OK\r\n\x02\\"
from custom_components.woow_serial.serial_port import SerialConfig, SerialPort
assert abs(SerialConfig("/dev/x", 9600).gap - 0.025) < 1e-9
print("codec / gap: ok")

import probatio
from homeassistant.helpers import config_validation as cv
from custom_components.woow_serial import SEND_SCHEMA
from custom_components.woow_serial import config_flow as cf
from custom_components.woow_serial.const import EXTERNAL_DEFAULTS
ports = cf.scan_ports()
print("  scan_ports:", ports)
for port in ports:
    vals = {**cf.serial_defaults(port), "name": cf.default_name(port)}
    schema = cf.serial_schema(vals, True)
    fields = probatio.to_field_list(schema, custom_serializer=cv.custom_serializer)
    form = {k: (str(v) if k in ("baudrate", "bytesize", "stopbits") else v) for k, v in vals.items()}
    print(f"  {port}: {len(fields)} form fields -> {cf.coerce(schema(form))}")
for with_name in (True, False):
    vals = {**EXTERNAL_DEFAULTS, "name": "WF485", "tx_entity": "text.x_hex_data_tx", "rx_entity": "sensor.x_uart_net_hex"}
    fields = probatio.to_field_list(cf.external_schema(vals, with_name), custom_serializer=cv.custom_serializer)
    assert len(fields) == 9 + with_name, [f["name"] for f in fields]
print("  send:", SEND_SCHEMA({"config_entry_id": "x", "hex": "A5 5A"}))
try:
    SEND_SCHEMA({"config_entry_id": "x", "hex": "A5", "text": "hi"})
    raise AssertionError("hex + text should be rejected")
except probatio.Invalid:
    pass
print("config flow forms / service schema: ok")

from custom_components.woow_serial import checksum as ck
assert ck.detect(bytes.fromhex("010300000002C40B"))[0] == "crc16_modbus"
assert "sum8" in ck.detect(bytes.fromhex("A55A0102") + ck.sum8(bytes.fromhex("A55A0102")))
assert "sum8@1" in ck.detect(bytes.fromhex("5501020306"))
assert ck.compute("crc16_modbus", bytes.fromhex("010300000002")) == bytes.fromhex("C40B")
assert ck.detect(bytes.fromhex("574F4F57")) == ["xor8"]  # an accident: why groups vote (catalog)
assert ck.detect(bytes.fromhex("A55A84776702")) == []
print("checksums: ok")

import custom_components.woow_serial.catalog as cat
import custom_components.woow_serial.devices as dv
import custom_components.woow_serial.mirror as mir
from custom_components.woow_serial.bus import BusFrame


class _NoStore:
    def __init__(self, *args, **kwargs):
        pass

    def async_delay_save(self, *args):
        pass


cat.Store = mir.Store = dv.Store = _NoStore
c = cat.Catalog(object())
t0 = 1000.0
for i, raw in enumerate(["A55A84776701", "A55A84776701", "A55A84776702", "010300000002C40B"]):
    c.on_frame(BusFrame("p1", "rx", bytes.fromhex(raw), time=t0 + i))
c.on_frame(BusFrame("p1", "rx", b"PWR=01\r", time=t0 + 5))
snap = c.snapshot()
groups = {g["key"]: g for g in snap["groups"]}
assert set(groups) == {"A5 5A", "01 03", "text"}, list(groups)
assert groups["A5 5A"]["rows"] == 2 and groups["A5 5A"]["count"] == 3
assert groups["01 03"]["checksum"] == "crc16_modbus", groups["01 03"]
assert {r["hex"]: r for r in snap["rows"]}["50 57 52 3D 30 31 0D"]["text"] == r"PWR=01\r"
c.set_prefix("p1", 3)
c.on_frame(BusFrame("p1", "rx", bytes.fromhex("A55A84776701"), time=t0 + 7))
assert {g.key for g in c.groups.values() if g.port_id == "p1"} == {"A5 5A 84"}
print("monitor catalog: ok")

m = mir.Mirror(object())
assert m.on_frame(BusFrame("p1", "tx", b"WOOW", origin="panel", time=t0), 0.5) is False
assert m.on_frame(BusFrame("p1", "rx", bytes.fromhex("A55A"), time=t0 + 0.2), 0.5) is False
assert m.on_frame(BusFrame("p2", "rx", b"WOOW", time=t0 + 0.3), 0.5) is True
assert m.on_frame(BusFrame("p1", "rx", bytes.fromhex("A55A"), time=t0 + 0.4), 0.5) is False
(row,) = m.rows.values()
assert (row.replies, row.reply, row.reply_ms, row.heard_by, row.origin) == (1, "A5 5A", 200, {"p2": 1}, "panel"), row
print("send log (reply, heard elsewhere): ok")

from custom_components.woow_serial import template as tp

head = bytes.fromhex("5501020332")
assert tp.render_hex("55 {addr} 03 {value:u8} {crc16_modbus}", {"addr": "01 02", "value": 50}) == head + ck.crc16_modbus(head)
assert tp.render_hex("A5 5A {value:u16le} {sum8@2}", {"value": 0x1234}) == bytes.fromhex("A55A3412") + bytes([0x46])
assert tp.render_hex("0xA5,5A {value:bcd}", {"value": 42}) == bytes.fromhex("A55A42")
assert tp.render_text(r"VOL {value:03d}\r", {"value": 7.0}) == b"VOL 007\r"
assert tp.fields_used("55 {addr} {value:u8} {crc16_modbus}", "hex") == {"addr", "value"}
for bad, code in (("55 {nope}", "no_value"), ("55 ??", "wildcard_in_command"), ("5", "odd_hex"),
                  ("55 {value:u99}", "bad_type"), ("ZZ", "bad_token"), ("{value:u8}", None)):
    try:
        tp.render_hex(bad, {"value": 300 if code is None else 1})
        raise AssertionError(bad)
    except tp.TemplateError as err:
        assert err.code == (code or "range"), (bad, err.code)
p = tp.Pattern("55 {addr} 03 ?? {pos:u8} {crc16_modbus}", "hex", {"addr": "01 02"})
reply = bytes.fromhex("550102030132")
assert p.match(reply + ck.crc16_modbus(reply)) == {"pos": 0x32}
assert p.match(reply + b"\x00\x00") is None  # bad CRC
other = bytes.fromhex("5501FF030132")
assert p.match(other + ck.crc16_modbus(other)) is None  # another device's address
assert tp.Pattern("A5 5A *", "hex", {}).match(bytes.fromhex("A55A0102")) == {}
assert tp.Pattern(r"^PWR=(?P<power>\d+)", "text", {}).match(b"PWR=01\r") == {"power": 1}
for bad, code in (("55 {pos}", "capture_needs_type"), ("* 55", "rest_not_last"), ("(", "bad_regex")):
    try:
        tp.Pattern(bad, "text" if bad == "(" else "hex", {})
        raise AssertionError(bad)
    except tp.TemplateError as err:
        assert err.code == code, (bad, err.code)
print("templates and receive patterns: ok")

curtain = {
    "id": "d1", "name": "客廳窗簾", "type": "cover", "port_id": "p1", "params": {"addr": "01 02"},
    "commands": [{"id": "c1", "name": "開", "payload": "55 {addr} 03 01 {crc16_modbus}"},
                 {"id": "c2", "name": "位置", "payload": "55 {addr} 03 04 {value:u8} {crc16_modbus}"}],
    "actions": {"open": "c1", "set_position": "c2"},
    "rules": [{"id": "r1", "pattern": "55 {addr} 03 ?? {pos:u8} {crc16_modbus}", "field": "position", "value": "{pos}"}],
    "ranges": {"position": [100, 0]},  # this motor counts 100 = closed
}
dev = dv.Device.from_dict(curtain)
dv.validate(dev)
assert dv.to_device(dev, "position", 30) == 70 and dv.from_device(dev, "position", 70) == 30
for change, code in (({"actions": {"turn_on": "c1"}}, "bad_action"), ({"actions": {"open": "zz"}}, "action_command"),
                     ({"rules": [{"id": "r", "pattern": "55 {pos:u8}", "field": "position", "value": "{x}"}]}, "rule_capture"),
                     ({"commands": [{"id": "c1", "name": "開", "payload": "55 {nope}"}], "actions": {}}, "command_template"),
                     ({"commands": [{"id": "c1", "name": "開", "format": "can", "payload": "55"}], "actions": {}}, "command_format"),
                     ({"name": " "}, "no_name")):
    try:
        dv.validate(dv.Device.from_dict({**curtain, **change}))
        raise AssertionError(change)
    except dv.DeviceError as err:
        assert err.code == code, (change, err.code)
mgr = dv.DeviceManager(object(), None, None)
mgr.devices[dev.id] = dev
mgr._compile(dev)
assert mgr._implied(dev, "open", None) == {}  # position has feedback: wait for the motor
status = bytes.fromhex("550102030146")  # motor reports raw 0x46 = 70 (= 30 % open)
mgr.on_frame(BusFrame("p1", "rx", status + ck.crc16_modbus(status)))
assert mgr.state["d1"] == {"position": 30}, mgr.state
mgr.on_frame(BusFrame("p2", "rx", status + ck.crc16_modbus(status)))  # other port: ignored
assert dv.DeviceManager.preview("55 {addr} {value:u8} {crc16_modbus}", "hex", {"addr": "01"}, 5)["sent"].startswith("55 01 05")
assert dv.DeviceManager.preview("55 {addr}", "hex", {}, None)["error"]["code"] == "no_value"
assert dv.DeviceManager.test_pattern("55 01 ?? *", "hex", {}, [bytes.fromhex("550102"), bytes.fromhex("AA")])["matches"][0]["frame"] == "55 01 02"
print("devices: validation, ranges, state feedback: ok")


class _Bus:
    def __init__(self):
        self.events = []

    def async_fire(self, event_type, data):
        self.events.append((event_type, data))


class _Hass:
    def __init__(self):
        self.bus = _Bus()
        self.tasks = []

    def async_create_task(self, coro, name=None):
        self.tasks.append(name)
        coro.close()


hass = _Hass()
mgr = dv.DeviceManager(hass, None, None)
mgr.devices[dev.id] = dev
mgr._compile(dev)
keypad = dv.Device.from_dict({
    "id": "k1", "name": "客廳面板", "type": "keypad", "port_id": "p1",
    "buttons": [{"id": "b1", "name": "情境1", "pattern": "A5 5A 01 ??"},
                {"id": "b2", "name": "情境2", "pattern": "A5 5A 02 {n:u8}", "target": "d1", "action": "open"}],
})
dv.validate(keypad)
mgr._check_bindings(keypad)
assert dv.binding_actions(dev) == ["open", "set_position", "command:c1", "command:c2"], dv.binding_actions(dev)
for change, code in (({"buttons": [{"id": "x", "name": "a", "pattern": "A5 {n}"}]}, "button_pattern"),
                     ({"buttons": [{"id": "x", "name": "a", "pattern": "A5"}, {"id": "y", "name": "a", "pattern": "A6"}]}, "button_name"),
                     ({"type": "switch", "buttons": [{"id": "x", "name": "a", "pattern": "A5"}]}, "no_buttons_for_type")):
    try:
        dv.validate(dv.Device.from_dict({**{"id": "k2", "name": "k", "type": "keypad", "port_id": "p1"}, **change}))
        raise AssertionError(change)
    except dv.DeviceError as err:
        assert err.code == code, (change, err.code)
for button, code in (({"target": "nope", "action": "open"}, "binding_target"), ({"target": "d1", "action": "turn_on"}, "binding_action"),
                     ({"target": "d1", "action": "set_position"}, "binding_value")):
    try:
        mgr._check_bindings(dv.Device.from_dict({"id": "k3", "name": "k", "type": "keypad", "port_id": "p1",
                                                 "buttons": [{"id": "x", "name": "a", "pattern": "A5", **button}]}))
        raise AssertionError(button)
    except dv.DeviceError as err:
        assert err.code == code, (button, err.code)
mgr.devices[keypad.id] = keypad
mgr._compile(keypad)
mgr.on_frame(BusFrame("p1", "rx", bytes.fromhex("A55A0107")))
mgr.on_frame(BusFrame("p1", "rx", bytes.fromhex("A55A0107")))  # held key: same press
mgr.on_frame(BusFrame("p1", "rx", bytes.fromhex("A55A0205")))
presses = [d for t, d in hass.bus.events if t == "woow_serial_button"]
assert [(p["button"], p["hex"]) for p in presses] == [("情境1", "A5 5A 01 07"), ("情境2", "A5 5A 02 05")], presses
assert presses[1]["n"] == 5 and presses[1]["device_id"] == "k1" and presses[1]["button_id"] == "b2"
assert hass.tasks == ["woow_serial binding 情境2"], hass.tasks
assert mgr.state["k1"]["last_button"] == "情境2"
print("keypads: match, debounce, event data, binding, validation: ok")


async def serial_test():
    master, slave = os.openpty()
    path = os.ttyname(slave)
    os.set_blocking(master, False)
    frames, txs, lost = [], [], []
    port = SerialPort(asyncio.get_running_loop(), SerialConfig(path, 9600, echo_filter=True, loop_flush=True),
                      frames.append, lambda d, origin=None: txs.append((d, origin)), lost.append)
    await port.open()
    os.write(master, b"\x01\x02\x03")
    await asyncio.sleep(0.012)
    os.write(master, b"\x04")
    await asyncio.sleep(0.08)
    assert frames == [b"\x01\x02\x03\x04"], frames

    async def peer():
        await asyncio.sleep(0.02)
        os.write(master, os.read(master, 100))  # RS485-style echo of what we sent
        await asyncio.sleep(0.005)
        os.write(master, b"\xAA\xBB")  # the device's reply

    task = asyncio.create_task(peer())
    reply = await port.request(b"\x10\x20", 1.0, "test")
    await task
    assert reply == b"\xAA\xBB", reply
    assert txs == [(b"\x10\x20", "test")], txs
    assert await port.request(b"\x30", 0.1) is None
    assert frames[-1] == b"\xAA\xBB" and not lost, (frames, lost)
    await port.close()
    os.close(master)
    os.close(slave)
    print("serial (pty): split-on-gap, echo filter, request/reply, timeout: ok")


asyncio.run(serial_test())
