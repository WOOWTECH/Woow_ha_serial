"""Built-in device templates: every one loads in both languages, sends the frames the makers' documents
show (CRCs checked when the templates were written) and reads their answers back."""

from __future__ import annotations

from typing import Any

import pytest

from custom_components.woow_serial import devices as dv
from custom_components.woow_serial import templates as tl
from custom_components.woow_serial.codec import parse_hex, to_hex
from custom_components.woow_serial.template import Pattern, render

BUILTIN, PROBLEMS = tl._read(tl.BUILTIN_DIR, "builtin")
TEMPLATES = {t.id: t for t in BUILTIN}


def make(template_id: str, language: str = "en", **params: str) -> dv.Device:
    raw = TEMPLATES[template_id].instantiate("port", "", params, language)
    device = dv.Device.from_dict({**raw, "id": "dev"})
    dv.validate(device)
    return device


def sent(device: dv.Device, command_id: str, value: float | None = None) -> str | bytes:
    """HEX for HEX commands, bytes for text ones. `value` is in device units."""
    command = device.command(command_id)
    data = render(command.payload, command.format, {**device.params, **({} if value is None else {"value": value})})
    return to_hex(data) if command.format == "hex" else data


def heard(device: dv.Device, frame: bytes | str, reply_to: str | None = None) -> dict[str, Any]:
    """What the device's rules and sensors take from one frame (as DeviceManager.on_frame does)."""
    data = parse_hex(frame) if isinstance(frame, str) else frame
    out: dict[str, Any] = {}
    for rule in device.rules:
        if rule.reply_to and rule.reply_to != reply_to:
            continue
        found = Pattern(rule.pattern, rule.format, device.params).match(data)
        if found is not None and (value := dv.DeviceManager._rule_value(None, device, rule, found)) is not None:
            out[rule.field] = value
    for sensor in device.sensors:
        if sensor.reply_to and sensor.reply_to != reply_to:
            continue
        found = Pattern(sensor.pattern, sensor.format, device.params).match(data)
        if found is not None:
            out[sensor.id] = round(found[sensor.capture] * sensor.scale + sensor.offset, sensor.precision or 3)
    return out


def test_every_builtin_template_loads():
    assert PROBLEMS == []
    assert set(TEMPLATES) == {
        "dooya_rs485_curtain", "aok_rs485_curtain", "waveshare_modbus_relay", "xymd02_modbus_th",
        "epson_escvp21_projector", "benq_rs232_projector", "denon_marantz_avr", "extron_sis_matrix_output",
        "blackbird_hdmi_matrix_output",
    }
    for template in BUILTIN:
        for attr in ("name", "description", "notes"):
            assert set(getattr(template, attr)) == {"en", "zh-Hant"}, (template.id, attr)
        assert template.references and template.port["bus"] in ("rs485", "rs232"), template.id
        for language in tl.LANGUAGES:
            summary = template.summary(language)
            assert summary["commands"] and all(isinstance(c, str) for c in summary["commands"]), template.id


def test_names_follow_the_language():
    assert [c.name for c in make("dooya_rs485_curtain", "zh-Hant").commands][:3] == ["開", "關", "停"]
    assert [c.name for c in make("dooya_rs485_curtain", "en").commands][:3] == ["Open", "Close", "Stop"]
    epson = make("epson_escvp21_projector", "zh-Hant")
    assert [o.name for o in epson.options] == ["HDMI 1", "HDMI 2", "電腦 1", "視訊"]
    assert heard(epson, b"SOURCE=10\r:") == {"source": "電腦 1"}  # rule values follow the option names


def test_dooya():
    d = make("dooya_rs485_curtain", addr="12 34")  # the protocol document's own examples
    assert sent(d, "open") == "55 12 34 03 01 AD 8A"
    assert sent(d, "close") == "55 12 34 03 02 ED 8B"
    assert sent(d, "stop") == "55 12 34 03 03 2C 4B"
    assert sent(d, "position", 30) == "55 12 34 03 04 1E C8 E5"
    assert sent(d, "read_position") == "55 12 34 01 02 01 2B 4D"
    assert heard(d, "55 12 34 01 01 1E 6A 75") == {"position": 30}
    assert heard(d, "55 12 34 01 01 FF AA 3D") == {}  # FF: limits not set, not "fully open"
    assert heard(d, "55 12 34 01 01 1E 6A 76") == {}  # bad CRC
    assert heard(d, "55 FE FE 01 01 1E C4 7A") == {}  # another motor
    assert d.command("open").then == "read_position"
    factory = make("dooya_rs485_curtain")
    assert sent(factory, "open") == "55 FE FE 03 01 B9 24"
    assert sent(factory, "position", 30) == "55 FE FE 03 04 1E 66 EA"
    assert sent(factory, "read_position") == "55 FE FE 01 02 01 85 42"


def test_aok():
    d = make("aok_rs485_curtain", id="09", ch="80 00")  # the protocol sheet's ID 9, channel 8
    assert sent(d, "open") == "9A 09 80 00 0A DD 5E"
    assert sent(d, "stop") == "9A 09 80 00 0A CC 4F"
    assert sent(d, "close") == "9A 09 80 00 0A EE 6D"
    assert sent(d, "position", 30) == "9A 09 80 00 DD 1E 4A"
    assert sent(d, "status") == "9A 09 80 00 CC 00 45"
    d = make("aok_rs485_curtain")  # ID 1, channel 1
    assert [sent(d, c) for c in ("open", "stop", "close", "status")] == [
        "9A 01 01 00 0A DD D7", "9A 01 01 00 0A CC C6", "9A 01 01 00 0A EE E4", "9A 01 01 00 CC 00 CC"]
    assert sent(d, "position", 30) == "9A 01 01 00 DD 1E C3"
    assert dv.to_device(d, "position", 30) == 70  # the motor counts the other way (0 = open)
    assert heard(d, "D8 01 01 00 00 DC 00 1E 02 C0") == {"position": 70}  # motor 30 = 70 % open
    assert heard(d, "D8 01 01 00 00 DC 00 1E 02 C1") == {}  # bad XOR
    assert heard(d, "D8 01 02 00 00 DC 00 1E 02 C3") == {}  # another channel
    assert heard(d, "D8 01 01 00 03 00 50 CA 41 D8") == {}  # function enquiry answer: CA is not a position


def test_waveshare_relay():
    d = make("waveshare_modbus_relay")
    assert sent(d, "on") == "01 05 00 00 FF 00 8C 3A"
    assert sent(d, "off") == "01 05 00 00 00 00 CD CA"
    assert sent(d, "flip") == "01 05 00 00 55 00 F2 9A"
    ch8 = make("waveshare_modbus_relay", coil="00 07")
    assert (sent(ch8, "on"), sent(ch8, "off")) == ("01 05 00 07 FF 00 3D FB", "01 05 00 07 00 00 7C 0B")
    assert heard(d, "01 05 00 00 FF 00 8C 3A") == {"power": True}  # the board echoes a write
    assert heard(d, "01 05 00 00 00 00 CD CA") == {"power": False}
    assert heard(d, "01 05 00 07 FF 00 3D FB") == {}  # channel 8's write
    assert heard(d, "01 01 01 01 90 48") == {}  # a read answer, but not to this channel's read
    assert heard(d, "01 01 01 01 90 48", reply_to="read") == {"power": True}
    assert heard(d, "01 01 01 00 51 88", reply_to="read") == {"power": False}


def test_xymd02():
    d = make("xymd02_modbus_th")
    assert sent(d, "read") == "01 04 00 01 00 02 20 0B"
    assert heard(d, "01 04 04 01 31 02 22 2A CE") == {"temperature": 30.5, "humidity": 54.6}
    assert heard(d, "01 04 04 FF 33 02 22 BA E6") == {"temperature": -20.5, "humidity": 54.6}
    assert heard(make("xymd02_modbus_th", addr="02"), "01 04 04 01 31 02 22 2A CE") == {}


def test_epson():
    d = make("epson_escvp21_projector")
    assert sent(d, "power_on") == b"PWR ON\r" and sent(d, "hdmi2") == b"SOURCE A0\r"
    assert d.command("hdmi2").then == "source_query"
    assert heard(d, b"PWR=01\r:") == {"power": True}
    assert heard(d, b"PWR=02\r:") == {"power": True}  # warming up
    assert heard(d, b"PWR=04\r:") == {"power": False}
    assert heard(d, b"SOURCE=A0\r:") == {"source": "HDMI 2"}
    assert heard(d, b"MUTE=ON\r:") == {"mute": True}
    assert heard(d, b"ERR\r:") == {} and heard(d, b":") == {}


def test_benq():
    d = make("benq_rs232_projector")
    assert sent(d, "power_on") == b"\r*pow=on#\r"
    assert heard(d, b">*pow=?#\r\n*POW=OFF#\r\n") == {"power": False}  # echo, then the answer
    assert heard(d, b"*pow=on#\r\n*POW=ON#\r\n") == {"power": True}
    assert heard(d, b"*SOUR=HDMI2#\r\n") == {"source": "HDMI 2"}
    assert heard(d, b">*sour=hdmi2#\r\n*Block item#\r\n") == {}  # refused: the echo alone changes nothing
    assert heard(d, b"*SOUR=RGB#\r\n") == {"source": "Computer"}


def test_denon():
    d = make("denon_marantz_avr")
    assert sent(d, "volume_set", 50) == b"MV50\r"
    assert dv.to_device(d, "volume", 0.5) == 40  # 100 % = MV80 (0 dB)
    assert heard(d, b"MV50\rMVMAX 98\r") == {"volume": 0.625}
    assert heard(d, b"MV505\r") == {"volume": 0.625}
    assert heard(d, b"MV85\r") == {"volume": 1.0}
    assert heard(d, b"MV99\r") == {}  # some documents write the minimum as 99
    assert heard(d, b"PWON\rZMON\r") == {"power": True}
    assert heard(d, b"SITV\r") == {"source": "TV audio"} and heard(d, b"SITUNER\r") == {"source": "Tuner"}
    assert heard(d, b"SISAT/CBL\r") == {"source": "Cable / Sat"}


def test_matrices():
    extron = make("extron_sis_matrix_output", output="2")
    assert sent(extron, "in1") == b"1*2!" and sent(extron, "off") == b"0*2!"
    assert sent(extron, "verbose") == b"\x1b3CV\r"
    assert heard(extron, b"Out2 In1 All\r\n") == {"option": "Input 1"}
    assert heard(extron, b"Out02 In03 Vid\r\n") == {"option": "Input 3"}
    assert heard(extron, b"Out12 In1 All\r\n") == {} and heard(extron, b"Out3 In1 All\r\n") == {}
    blackbird = make("blackbird_hdmi_matrix_output", output="2")
    assert sent(blackbird, "in3") == b"3V2." and sent(blackbird, "status") == b"Status2."
    assert heard(blackbird, b"AV:03->02") == {"option": "Input 3"}
    assert heard(blackbird, b"AV:01->12") == {} and heard(blackbird, b"AV:01->2\r\n") == {"option": "Input 1"}


@pytest.mark.parametrize("language", tl.LANGUAGES)
def test_templates_survive_a_save_round_trip(language):
    """What instantiate() gives is what the device store keeps: nothing a template uses is dropped."""
    from dataclasses import asdict

    for template in BUILTIN:
        device = make(template.id, language)
        again = dv.Device.from_dict(asdict(device))
        dv.validate(again)
        assert asdict(again) == asdict(device), template.id


def test_answered_commands_hold_the_line():
    """Every command a device answers waits for the answer (half-duplex RS485: no request on top of it)."""
    answered = {
        "dooya_rs485_curtain": {"open", "close", "stop", "position", "read_position"},
        "aok_rs485_curtain": {"status"},
        "waveshare_modbus_relay": {"on", "off", "flip", "read"},
        "xymd02_modbus_th": {"read"},
    }
    for template_id, ids in answered.items():
        device = make(template_id)
        assert {c.id for c in device.commands if c.wait_ms > 0} == ids, template_id
