"""Unit tests of WOOW Serial's logic (no Home Assistant instance needed)."""

from __future__ import annotations

import asyncio
import os

import pytest

from custom_components.woow_serial import SEND_SCHEMA
from custom_components.woow_serial import catalog as cat
from custom_components.woow_serial import checksum as ck
from custom_components.woow_serial import config_flow as cf
from custom_components.woow_serial import devices as dv
from custom_components.woow_serial import mirror as mir
from custom_components.woow_serial import template as tp
from custom_components.woow_serial.bus import BusFrame
from custom_components.woow_serial.codec import parse_hex, printable, unescape
from custom_components.woow_serial.const import EXTERNAL_DEFAULTS
from custom_components.woow_serial.serial_port import SerialConfig, SerialPort


class _NoStore:
    def __init__(self, *args, **kwargs):
        pass

    def async_delay_save(self, *args):
        pass


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


@pytest.fixture(autouse=True)
def _no_storage(monkeypatch):
    for module in (cat, mir, dv):
        monkeypatch.setattr(module, "Store", _NoStore)


CURTAIN = {
    "id": "d1", "name": "客廳窗簾", "type": "cover", "port_id": "p1", "params": {"addr": "01 02"},
    "commands": [{"id": "c1", "name": "開", "payload": "55 {addr} 03 01 {crc16_modbus}"},
                 {"id": "c2", "name": "位置", "payload": "55 {addr} 03 04 {value:u8} {crc16_modbus}"}],
    "actions": {"open": "c1", "set_position": "c2"},
    "rules": [{"id": "r1", "pattern": "55 {addr} 03 ?? {pos:u8} {crc16_modbus}", "field": "position", "value": "{pos}"}],
    "ranges": {"position": [100, 0]},  # this motor counts 100 = closed
}


def test_codec():
    assert parse_hex("A5 5A 0x01,02:03-04") == bytes.fromhex("A55A01020304")
    assert unescape(r"PWR ON\r\x02\\") == b"PWR ON\r\x02\\"
    assert printable(b"OK\r\n\x02\\") == r"OK\r\n\x02\\"
    assert abs(SerialConfig("/dev/x", 9600).gap - 0.025) < 1e-9


def test_forms_and_service_schema():
    import probatio
    from homeassistant.helpers import config_validation as cv

    vals = {**cf.serial_defaults("/dev/ttySC0"), "name": cf.default_name("/dev/ttySC0")}
    assert vals["echo_filter"] and vals["name"] == "RS485-1"
    schema = cf.serial_schema(vals, True)
    probatio.to_field_list(schema, custom_serializer=cv.custom_serializer)
    form = {k: (str(v) if k in ("baudrate", "bytesize", "stopbits") else v) for k, v in vals.items()}
    assert cf.coerce(schema(form))["baudrate"] == 9600
    for with_name in (True, False):
        vals = {**EXTERNAL_DEFAULTS, "name": "WF485", "tx_entity": "text.x_hex_data_tx", "rx_entity": "sensor.x_uart_net_hex"}
        fields = probatio.to_field_list(cf.external_schema(vals, with_name), custom_serializer=cv.custom_serializer)
        assert len(fields) == 9 + with_name
    assert SEND_SCHEMA({"config_entry_id": "x", "hex": "A5 5A"})["wait_ms"] == 0
    with pytest.raises(probatio.Invalid):
        SEND_SCHEMA({"config_entry_id": "x", "hex": "A5", "text": "hi"})


def test_checksums():
    assert ck.detect(bytes.fromhex("010300000002C40B"))[0] == "crc16_modbus"
    assert "sum8" in ck.detect(bytes.fromhex("A55A0102") + ck.sum8(bytes.fromhex("A55A0102")))
    assert "sum8@1" in ck.detect(bytes.fromhex("5501020306"))
    assert ck.compute("crc16_modbus", bytes.fromhex("010300000002")) == bytes.fromhex("C40B")
    assert ck.detect(bytes.fromhex("574F4F57")) == ["xor8"]  # an accident: why groups vote
    assert ck.detect(bytes.fromhex("A55A84776702")) == []


def test_catalog_groups_and_votes():
    c = cat.Catalog(object())
    for i, raw in enumerate(["A55A84776701", "A55A84776701", "A55A84776702", "010300000002C40B"]):
        c.on_frame(BusFrame("p1", "rx", bytes.fromhex(raw), time=1000.0 + i))
    c.on_frame(BusFrame("p1", "rx", b"PWR=01\r", time=1005.0))
    snap = c.snapshot()
    groups = {g["key"]: g for g in snap["groups"]}
    assert set(groups) == {"A5 5A", "01 03", "text"}
    assert groups["A5 5A"]["rows"] == 2 and groups["A5 5A"]["count"] == 3
    assert groups["01 03"]["checksum"] == "crc16_modbus"
    assert {r["hex"]: r for r in snap["rows"]}["50 57 52 3D 30 31 0D"]["text"] == r"PWR=01\r"
    c.set_prefix("p1", 3)
    c.on_frame(BusFrame("p1", "rx", bytes.fromhex("A55A84776701"), time=1007.0))
    assert {g.key for g in c.groups.values()} == {"A5 5A 84"}


def test_send_log_reply_and_echo():
    m = mir.Mirror(object())
    assert m.on_frame(BusFrame("p1", "tx", b"WOOW", origin="panel", time=1000.0), 0.5) is False
    assert m.on_frame(BusFrame("p1", "rx", bytes.fromhex("A55A"), time=1000.2), 0.5) is False
    assert m.on_frame(BusFrame("p2", "rx", b"WOOW", time=1000.3), 0.5) is True  # our own send, heard elsewhere
    (row,) = m.rows.values()
    assert (row.replies, row.reply, row.reply_ms, row.heard_by, row.origin) == (1, "A5 5A", 200, {"p2": 1}, "panel")


def test_command_templates():
    head = bytes.fromhex("5501020332")
    assert tp.render_hex("55 {addr} 03 {value:u8} {crc16_modbus}", {"addr": "01 02", "value": 50}) == head + ck.crc16_modbus(head)
    assert tp.render_hex("A5 5A {value:u16le} {sum8@2}", {"value": 0x1234}) == bytes.fromhex("A55A341246")
    assert tp.render_hex("0xA5,5A {value:bcd}", {"value": 42}) == bytes.fromhex("A55A42")
    assert tp.render_text(r"VOL {value:03d}\r", {"value": 7.0}) == b"VOL 007\r"
    assert tp.fields_used("55 {addr} {value:u8} {crc16_modbus}", "hex") == {"addr", "value"}


@pytest.mark.parametrize(("template", "value", "code"), [
    ("55 {nope}", 1, "no_value"), ("55 ??", 1, "wildcard_in_command"), ("5", 1, "odd_hex"),
    ("55 {value:u99}", 1, "bad_type"), ("ZZ", 1, "bad_token"), ("{value:u8}", 300, "range"),
])
def test_command_template_errors(template, value, code):
    with pytest.raises(tp.TemplateError) as err:
        tp.render_hex(template, {"value": value})
    assert err.value.code == code


def test_receive_patterns():
    p = tp.Pattern("55 {addr} 03 ?? {pos:u8} {crc16_modbus}", "hex", {"addr": "01 02"})
    reply = bytes.fromhex("550102030132")
    assert p.match(reply + ck.crc16_modbus(reply)) == {"pos": 0x32}
    assert p.match(reply + b"\x00\x00") is None
    other = bytes.fromhex("5501FF030132")
    assert p.match(other + ck.crc16_modbus(other)) is None
    assert tp.Pattern("A5 5A *", "hex", {}).match(bytes.fromhex("A55A0102")) == {}
    assert tp.Pattern(r"^PWR=(?P<power>\d+)", "text", {}).match(b"PWR=01\r") == {"power": 1}
    for bad, fmt, code in (("55 {pos}", "hex", "capture_needs_type"), ("* 55", "hex", "rest_not_last"), ("(", "text", "bad_regex")):
        with pytest.raises(tp.TemplateError) as err:
            tp.Pattern(bad, fmt, {})
        assert err.value.code == code


def test_device_validation_ranges_feedback():
    dev = dv.Device.from_dict(CURTAIN)
    dv.validate(dev)
    assert dv.to_device(dev, "position", 30) == 70 and dv.from_device(dev, "position", 70) == 30
    for change, code in (({"actions": {"turn_on": "c1"}}, "bad_action"), ({"actions": {"open": "zz"}}, "action_command"),
                         ({"rules": [{"id": "r", "pattern": "55 {pos:u8}", "field": "position", "value": "{x}"}]}, "rule_capture"),
                         ({"commands": [{"id": "c1", "name": "開", "payload": "55 {nope}"}], "actions": {}}, "command_template"),
                         ({"name": " "}, "no_name")):
        with pytest.raises(dv.DeviceError) as err:
            dv.validate(dv.Device.from_dict({**CURTAIN, **change}))
        assert err.value.code == code
    mgr = dv.DeviceManager(_Hass(), None, None)
    mgr.devices[dev.id] = dev
    mgr._compile(dev)
    assert mgr._implied(dev, "open", None) == {}  # position has feedback: wait for the motor
    status = bytes.fromhex("550102030146")
    mgr.on_frame(BusFrame("p1", "rx", status + ck.crc16_modbus(status)))
    assert mgr.state["d1"] == {"position": 30}
    assert dv.DeviceManager.preview("55 {addr} {value:u8} {crc16_modbus}", "hex", {"addr": "01"}, 5)["sent"].startswith("55 01 05")
    assert dv.DeviceManager.preview("55 {addr}", "hex", {}, None)["error"]["code"] == "no_value"


def test_keypads():
    hass = _Hass()
    mgr = dv.DeviceManager(hass, None, None)
    curtain = dv.Device.from_dict(CURTAIN)
    mgr.devices[curtain.id] = curtain
    mgr._compile(curtain)
    keypad = dv.Device.from_dict({
        "id": "k1", "name": "客廳面板", "type": "keypad", "port_id": "p1",
        "buttons": [{"id": "b1", "name": "情境1", "pattern": "A5 5A 01 ??"},
                    {"id": "b2", "name": "情境2", "pattern": "A5 5A 02 {n:u8}", "target": "d1", "action": "open"}],
    })
    dv.validate(keypad)
    mgr._check_bindings(keypad)
    assert dv.binding_actions(curtain) == ["open", "set_position", "command:c1", "command:c2"]
    mgr.devices[keypad.id] = keypad
    mgr._compile(keypad)
    mgr.on_frame(BusFrame("p1", "rx", bytes.fromhex("A55A0107")))
    mgr.on_frame(BusFrame("p1", "rx", bytes.fromhex("A55A0107")))  # held key: the same press
    mgr.on_frame(BusFrame("p1", "rx", bytes.fromhex("A55A0205")))
    presses = [d for t, d in hass.bus.events if t == "woow_serial_button"]
    assert [(p["button"], p["hex"]) for p in presses] == [("情境1", "A5 5A 01 07"), ("情境2", "A5 5A 02 05")]
    assert presses[1]["n"] == 5 and presses[1]["button_id"] == "b2"
    assert hass.tasks == ["woow_serial binding 情境2"]
    for button, code in (({"target": "nope", "action": "open"}, "binding_target"),
                         ({"target": "d1", "action": "turn_on"}, "binding_action"),
                         ({"target": "d1", "action": "set_position"}, "binding_value")):
        with pytest.raises(dv.DeviceError) as err:
            mgr._check_bindings(dv.Device.from_dict({"id": "k3", "name": "k", "type": "keypad", "port_id": "p1",
                                                     "buttons": [{"id": "x", "name": "a", "pattern": "A5", **button}]}))
        assert err.value.code == code


def test_serial_port_on_a_pty():
    async def run():
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
        assert frames == [b"\x01\x02\x03\x04"]

        async def peer():
            await asyncio.sleep(0.02)
            os.write(master, os.read(master, 100))  # RS485-style echo of what we sent
            await asyncio.sleep(0.005)
            os.write(master, b"\xAA\xBB")

        task = asyncio.create_task(peer())
        assert await port.request(b"\x10\x20", 1.0, "test") == b"\xAA\xBB"
        await task
        assert txs == [(b"\x10\x20", "test")]
        assert await port.request(b"\x30", 0.1) is None
        await port.close()
        os.close(master)
        os.close(slave)

    asyncio.run(run())
