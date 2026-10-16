"""A virtual bus: each built-in template drives the simulated device written from the same maker's document
(tools/sim/protocols.py), and reads the device's answers back. The two were written separately, so a
mistake in either shows up here — without hardware, in CI. The live matrix (tools/sim/matrix.py) does the
same over real RS485 / RS232 lines."""

from __future__ import annotations

from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).parents[1] / "tools" / "sim"))

import protocols as sim  # noqa: E402
from test_templates import heard, make  # noqa: E402

from custom_components.woow_serial import devices as dv  # noqa: E402
from custom_components.woow_serial.template import render  # noqa: E402


def run(device: dv.Device, model: sim.Model, command_id: str, ha_value: float | None = None,
        field: str | None = None) -> tuple[bytes, list[bytes], dict]:
    """Send one command to the model; return (frame, answers, what the device read from the answers)."""
    command = device.command(command_id)
    variables = dict(device.params)
    if ha_value is not None:
        variables["value"] = dv.to_device(device, field, ha_value)
    frame = render(command.payload, command.format, variables)
    answers = [data for _, data in model.handle(frame)]
    state: dict = {}
    for answer in answers:
        state.update(heard(device, answer, reply_to=command_id))
    return frame, answers, state


def test_dooya_motor():
    device = make("dooya_rs485_curtain", addr="01 02")
    motor = sim.Dooya("m", addr="01 02", travel_s=0.2, position=0)
    frame, answers, _ = run(device, motor, "open")
    assert answers == [frame]  # a control command is answered with the same frame
    time.sleep(0.25)
    assert run(device, motor, "read_position")[2] == {"position": 100}
    run(device, motor, "position", 30, "position")
    time.sleep(0.25)
    assert run(device, motor, "read_position")[2] == {"position": 30}
    motor.set(calibrated=False)
    assert run(device, motor, "read_position")[2] == {}  # FF is not a position
    other = make("dooya_rs485_curtain", addr="03 04")
    assert run(other, motor, "open")[1] == []  # another address: silence


def test_aok_motor():
    device = make("aok_rs485_curtain", id="05", ch="02 00")
    motor = sim.AOK("m", id="05", ch="02 00", travel_s=0.2, position=100)  # motor 100 = closed
    assert run(device, motor, "status")[2] == {"position": 0}
    assert run(device, motor, "open")[1] == []  # control commands are never answered
    time.sleep(0.25)
    assert run(device, motor, "status")[2] == {"position": 100}
    run(device, motor, "position", 25, "position")  # 25 % open = motor 75
    time.sleep(0.25)
    assert motor.state()["position"] == 75
    assert run(device, motor, "status")[2] == {"position": 25}
    assert run(make("aok_rs485_curtain", id="05", ch="01 00"), motor, "status")[1] == []  # another channel


def test_waveshare_channels():
    ch1 = make("waveshare_modbus_relay", addr="03", coil="00 00")
    ch2 = make("waveshare_modbus_relay", addr="03", coil="00 01")
    board = sim.WaveshareRelay("r", addr="03")
    frame, answers, state = run(ch1, board, "on")
    assert answers == [frame] and state == {"power": True} and board.coils[:2] == [True, False]
    assert heard(ch2, answers[0]) == {}  # channel 2 does not take channel 1's confirmation
    assert run(ch2, board, "read")[2] == {"power": False}  # each channel reads its own coil
    assert run(ch1, board, "read")[2] == {"power": True}
    run(ch1, board, "flip")
    assert board.coils[0] is False
    bad = render("03 05 00 00 12 34 {crc16_modbus}", "hex", {})
    assert board.handle(bad)[0][1][1] == 0x85  # an unknown value is an exception, not a write


def test_xymd02_sensor():
    device = make("xymd02_modbus_th", addr="04")
    sensor = sim.XYMD02("t", addr="04", temperature=-3.2, humidity=61.5)
    assert run(device, sensor, "read")[2] == {"temperature": -3.2, "humidity": 61.5}


def test_epson_projector():
    device = make("epson_escvp21_projector")
    projector = sim.Epson("p", warmup_s=0.2, cooldown_s=0.1)
    assert run(device, projector, "power_query")[2] == {"power": False}
    assert run(device, projector, "hdmi2")[1] == [b"ERR\r:"]  # in standby
    assert run(device, projector, "power_on")[1] == [b":"]
    assert run(device, projector, "power_query")[2] == {"power": True}  # 02, warming up
    time.sleep(0.25)
    run(device, projector, "hdmi2")
    assert run(device, projector, "source_query")[2] == {"source": "HDMI 2"}
    run(device, projector, "mute_on")
    assert run(device, projector, "mute_query")[2] == {"mute": True}
    run(device, projector, "power_off")
    assert run(device, projector, "power_query")[2] == {"power": False}  # 03, cooling down


def test_benq_projector():
    device = make("benq_rs232_projector")
    projector = sim.BenQ("p", transition_s=0.1)
    assert run(device, projector, "power_on")[2] == {"power": True}
    assert run(device, projector, "hdmi2")[2] == {}  # warming up: '*Block item#'
    time.sleep(0.15)
    assert run(device, projector, "hdmi2")[2] == {"source": "HDMI 2"}
    assert run(device, projector, "mute_on")[2] == {"mute": True}
    assert run(device, projector, "power_query")[2] == {"power": True}


def test_denon_receiver():
    device = make("denon_marantz_avr")
    avr = sim.Denon("a")
    assert run(device, avr, "power_query")[2] == {"power": False}
    assert run(device, avr, "power_on")[2] == {"power": True}
    assert run(device, avr, "volume_set", 0.5, "volume")[2] == {"volume": 0.5}  # MV40
    assert run(device, avr, "volume_up")[2] == {"volume": 0.5}  # MV405 reads as 40
    assert run(device, avr, "si_bd")[2] == {"source": "Blu-ray"}
    knob = avr.event("knob", volume=60)[0][1]
    assert heard(device, knob) == {"volume": 0.75}  # a change made on the receiver itself
    assert run(device, avr, "mute_on")[2] == {"mute": True}


def test_matrices():
    extron = make("extron_sis_matrix_output", output="2")
    switcher = sim.Extron("x")
    assert run(extron, switcher, "in3")[2] == {"option": "Input 3"} and switcher.ties[2] == 3
    assert switcher.handle(render(extron.command("verbose").payload, "text", {}))[0][1] == b"Vrb3\r\n"
    blackbird = make("blackbird_hdmi_matrix_output", output="1")
    matrix = sim.Blackbird("b")
    assert run(blackbird, matrix, "in2")[2] == {"option": "Input 2"}
    assert run(blackbird, matrix, "status")[2] == {"option": "Input 2"}


def test_keypad_frames():
    keypad = sim.Keypad("k", addr="10")
    frames = keypad.event("press", key=2, repeat=3, gap_ms=50)
    assert [round(d, 2) for d, _ in frames] == [0.0, 0.05, 0.1]
    assert frames[0][1].hex(" ").upper() == "A5 5A 10 02 11"


def test_joined_frames_are_split():
    """An HA-WF485-V3 joins frames less than ~0.1 s apart; the simulator takes them apart by checksum."""
    joined = bytes.fromhex("550A0B010201075B" "9A050100CC00C8" "A55A100312" "06060001000119BD")
    assert [f.hex(" ").upper() for f in sim.split_frames(joined)] == [
        "55 0A 0B 01 02 01 07 5B", "9A 05 01 00 CC 00 C8", "A5 5A 10 03 12", "06 06 00 01 00 01 19 BD"]
    assert sim.split_frames(b"\x01\x02\x03") == [b"\x01\x02\x03"]  # no frame in it: left alone
