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
    form["parity"] = "n"  # selector keys are lowercase; the stored value is uppercase
    stored = cf.coerce(schema(form))
    assert stored["baudrate"] == 9600 and stored["parity"] == "N"
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


def test_activity_messages_are_translated():
    """Every logged message has an English line and a panel translation in both languages."""
    import re
    from pathlib import Path

    from custom_components.woow_serial.activity import MESSAGES, summarize

    assert summarize("device_deleted", {"device": "Curtain"}) == 'deleted device "Curtain"'
    assert summarize("sent", {"hex": "01"}) == "sent 01 on ?"  # a missing arg never raises
    i18n = (Path(__file__).parents[1] / "frontend" / "src" / "i18n.ts").read_text(encoding="utf-8")
    english, chinese = i18n.split("const zh", 1)
    for msg, line in MESSAGES.items():
        fields = set(re.findall(r"\{(\w+)\}", line))
        for table in (english, chinese):
            match = re.search(rf"^  log_{msg}: \"(.*)\",$", table, re.M)
            assert match, f"log_{msg} missing from the panel translations"
            assert set(re.findall(r"\{(\w+)\}", match.group(1))) == fields, msg


def test_llm_tools_cover_every_service():
    """Each service is a tool with a description and parameters the MCP server can turn into JSON schema."""
    import probatio

    from homeassistant.helpers import llm

    from custom_components.woow_serial import llm_api

    services, texts = llm_api._read()
    tools = {tool.name: tool for tool in llm_api.build_tools(services, texts)}
    assert set(tools) == set(services)
    for name, tool in tools.items():
        assert tool.description and "return_response" not in tool.description, name
        schema = probatio.to_openapi(tool.parameters, custom_serializer=llm.selector_serializer, openapi_version="3.1.0")
        assert set(schema.get("properties", {})) == set((services[name] or {}).get("fields") or {}), name
    assert tools["get_device"].annotations.read_only and not tools["delete_device"].annotations.read_only
    assert "device" in probatio.to_openapi(tools["save_device"].parameters, custom_serializer=llm.selector_serializer,
                                           openapi_version="3.1.0")["required"]


def test_service_texts_in_sync():
    """services.yaml repeats the English texts (MCP servers read them there): run tools/sync_service_texts.py."""
    import json
    from pathlib import Path

    import yaml

    root = Path(__file__).parents[1] / "custom_components" / "woow_serial"
    services = yaml.safe_load((root / "services.yaml").read_text(encoding="utf-8"))
    texts = json.loads((root / "translations" / "en.json").read_text(encoding="utf-8"))["services"]
    assert set(services) == set(texts)
    for name, spec in services.items():
        assert (spec["name"], spec["description"]) == (texts[name]["name"], texts[name]["description"]), name
        for field, config in (spec.get("fields") or {}).items():
            text = texts[name]["fields"][field]
            assert (config["name"], config["description"]) == (text["name"], text["description"]), f"{name}.{field}"


def test_text_patterns_take_parameters():
    """{param} in a text pattern is the parameter's text (escaped); regex quantifiers stay quantifiers."""
    pattern = tp.Pattern(r"Out0*{output} In(?P<input>\d{1,2}) All", "text", {"output": "1.5"})
    assert pattern.match(b"Out1.5 In12 All") == {"input": 12}
    assert pattern.match(b"Out1x5 In12 All") is None  # the dot is literal
    assert tp.Pattern(r"MV(?P<v>\d{2})", "text", {}).match(b"MV45\r") == {"v": 45}


def test_out_of_range_feedback():
    """A position or brightness outside the device range is not one; a volume past it is the limit."""
    device = dv.Device.from_dict({"id": "d", "name": "d", "type": "cover", "port_id": "p",
                                  "ranges": {"position": [100, 0], "volume": [0, 80]}})
    assert dv.from_device(device, "position", 30) == 70
    assert dv.from_device(device, "position", 255) is None
    assert dv.from_device(device, "volume", 90) == 1.0
    assert dv.from_device(device, "brightness", -1) is None


def test_follow_ups_and_reply_to():
    base = {"id": "d", "name": "d", "type": "switch", "port_id": "p", "commands": [
        {"id": "on", "name": "On", "payload": "01"}, {"id": "q", "name": "Query", "payload": "02"}]}

    def code(**change):
        device = dv.Device.from_dict({**base, **change})
        try:
            dv.validate(device)
        except dv.DeviceError as err:
            return err.code
        return None

    assert code(commands=[{"id": "on", "name": "On", "payload": "01", "then": "q"},
                          {"id": "q", "name": "Query", "payload": "02"}]) is None
    assert code(commands=[{"id": "on", "name": "On", "payload": "01", "then": "on"}]) == "command_then"
    assert code(commands=[{"id": "on", "name": "On", "payload": "01", "then": "zz"}]) == "command_then"
    assert code(rules=[{"id": "r", "pattern": "01 {b:u8}", "value": "{b}", "reply_to": "q"}]) is None
    assert code(rules=[{"id": "r", "pattern": "01 {b:u8}", "value": "{b}", "reply_to": "zz"}]) == "rule_reply_to"
    assert code(sensors=[{"id": "s", "name": "S", "pattern": "01 {v:u8}", "capture": "v", "reply_to": "zz"}]) == \
        "sensor_reply_to"


def test_template_texts_localize():
    from custom_components.woow_serial.templates import localize

    data = {"name": {"en": "Open", "zh-Hant": "開"}, "payload": "55", "params": {"en": "kept as is"},
            "list": [{"en": "A", "zh-Hant": "甲"}]}
    assert localize(data, "zh-Hant") == {"name": "開", "payload": "55", "params": "kept as is", "list": ["甲"]}
    assert localize(data, "de") == {"name": "Open", "payload": "55", "params": "kept as is", "list": ["A"]}


def test_send_accepts_an_expected_reply():
    data = SEND_SCHEMA({"port": "RS485-1", "hex": "04 04 00 01 00 02 20 5E", "expect": "04 04 04 *"})
    assert data["expect"] == "04 04 04 *" and data["wait_ms"] == 0
    assert tp.Pattern("04 04 04 {t:s16} *", "hex", {}).match(bytes.fromhex("040404FFC9")) == {"t": -55}


def test_replies_belong_to_the_command_that_went_out():
    """reply_to: an answer counts for the command whose bytes went out last on that port (on_sent), so
    a channel whose read waited in line behind another's never takes that one's answer."""
    import types

    def relay(device_id, coil):
        return dv.Device.from_dict({
            "id": device_id, "name": device_id, "type": "switch", "port_id": "p1", "params": {"coil": coil},
            "commands": [{"id": "read", "name": "Read", "payload": "03 01 {coil} 00 01 {crc16_modbus}"}],
            "rules": [{"id": "r", "pattern": "03 01 01 {b:u8} {crc16_modbus}", "field": "power", "value": "{b}",
                       "reply_to": "read"}]})

    mgr = dv.DeviceManager(_Hass(), None, types.SimpleNamespace(ports={}))
    for device in (relay("ch1", "00 00"), relay("ch2", "00 01")):
        mgr.devices[device.id] = device
        mgr._compile(device)
    on, off = bytes.fromhex("03010101"), bytes.fromhex("03010100")  # "coil is on / off", no register named
    on, off = on + ck.compute("crc16_modbus", on), off + ck.compute("crc16_modbus", off)
    mgr.on_sent(BusFrame("p1", "tx", b"\x03\x01\x00\x01", origin="device:ch2:read"))
    mgr.on_frame(BusFrame("p1", "rx", on))
    assert mgr.state.get("ch2", {}).get("power") is True and "power" not in mgr.state.get("ch1", {})
    mgr.on_frame(BusFrame("p1", "rx", off))  # a second frame answers nothing
    assert mgr.state["ch2"]["power"] is True
    mgr.on_sent(BusFrame("p1", "tx", b"\x01", origin="panel"))  # someone else sent in between
    mgr.on_frame(BusFrame("p1", "rx", off))
    assert mgr.state["ch2"]["power"] is True and "power" not in mgr.state.get("ch1", {})
    mgr.on_sent(BusFrame("p1", "tx", b"\x03\x01\x00\x00", origin="device:ch1:read"))
    mgr.on_frame(BusFrame("p1", "rx", off))
    assert mgr.state["ch1"]["power"] is False and mgr.state["ch2"]["power"] is True


def test_joined_frames_are_taken_apart():
    """A WF485 joins frames less than ~0.1 s apart; frames made only of known pieces are split again."""
    import types

    hass = _Hass()
    mgr = dv.DeviceManager(hass, None, types.SimpleNamespace(ports={}))
    keypad = dv.Device.from_dict({"id": "k", "name": "k", "type": "keypad", "port_id": "p1", "params": {"addr": "10"},
                                  "buttons": [{"id": "b1", "name": "1", "pattern": "A5 5A {addr} 01 {sum8}"},
                                              {"id": "b3", "name": "3", "pattern": "A5 5A {addr} 03 {sum8}"}]})
    motor = dv.Device.from_dict({**CURTAIN, "id": "m", "port_id": "p1", "ranges": {}})
    for device in (keypad, motor):
        mgr.devices[device.id] = device
        mgr._compile(device)

    def press(key):
        body = bytes([0xA5, 0x5A, 0x10, key])
        return body + bytes([sum(body) & 0xFF])

    def presses():
        out = [d["button"] for t, d in hass.bus.events if t == "woow_serial_button"]
        hass.bus.events.clear()
        return out

    mgr.on_frame(BusFrame("p1", "rx", press(3) * 3))  # one key sent three times, back to back
    assert presses() == ["3"]  # three pieces, one press (debounce)
    mgr.on_frame(BusFrame("p1", "rx", press(1) + press(3)))
    assert presses() == ["1"]  # "3" is still within its debounce
    mgr._last_press.clear()
    position = bytes.fromhex("55010203041E")
    position += ck.compute("crc16_modbus", position)
    mgr.on_frame(BusFrame("p1", "rx", position + press(1)))  # a motor's answer and a key press joined
    assert presses() == ["1"] and mgr.state["m"]["position"] == 30
    mgr._last_press.clear()
    sent = bytes.fromhex("55010203011234")
    mgr.on_sent(BusFrame("p1", "tx", sent, origin="panel"))
    mgr.on_frame(BusFrame("p1", "rx", sent + press(3)))  # the motor's echo of our command, then a key
    assert presses() == ["3"]
    mgr._last_press.clear()
    mgr.on_frame(BusFrame("p1", "rx", b"\x99\x98" + press(1)))  # unknown bytes in front: no guessing
    assert presses() == []
    assert mgr.split("p1", press(1)) == [press(1)]
