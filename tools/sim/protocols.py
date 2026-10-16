"""Simulated RS485 / RS232 equipment for the WOOW Serial test matrix (stdlib only, no Home Assistant).

Each model answers frames the way the real device does, written from the makers' protocol documents
(not from the integration's templates, so the two check each other). A model gets every frame on its
line and answers only what is addressed to it, so several share one RS485 bus as in a real building.

    handle(frame) -> list of (delay s, bytes) to send back
    event(name, **args) -> list of (delay s, bytes): things the device does by itself (a key press, a knob)
    state() -> dict, set(**values)
"""

from __future__ import annotations

import re
import time
from typing import Any


# ---- checksums ----------------------------------------------------------------------------
def crc16_modbus(data: bytes) -> bytes:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc.to_bytes(2, "little")


def xor8(data: bytes) -> int:
    out = 0
    for byte in data:
        out ^= byte
    return out


def sum8(data: bytes) -> int:
    return sum(data) & 0xFF


def with_crc(body: bytes) -> bytes:
    return body + crc16_modbus(body)


def crc_ok(frame: bytes) -> bool:
    return len(frame) >= 4 and crc16_modbus(frame[:-2]) == frame[-2:]


REPLY = 0.02  # s: how long a device takes to answer


def _complete(chunk: bytes) -> bool:
    """A whole frame of one of the binary protocols here, judged by its checksum."""
    if chunk[:1] == b"\x9a":
        return len(chunk) == 7 and xor8(chunk[1:6]) == chunk[6]
    if chunk[:1] == b"\xd8":
        return len(chunk) == 10 and xor8(chunk[1:9]) == chunk[9]
    if chunk[:2] == b"\xa5\x5a":
        return len(chunk) == 5 and sum8(chunk[:4]) == chunk[4]
    return len(chunk) >= 4 and crc_ok(chunk)


def split_frames(data: bytes) -> list[bytes]:
    """Frames that reached us joined together (an HA-WF485-V3 joins frames less than ~0.1 s apart) taken
    apart again at checksum boundaries, the way a bus sniffer does. Bytes that make no frame stay as they are."""
    out: list[bytes] = []
    start = 0
    while start < len(data):
        for end in range(start + 4, min(len(data), start + 64) + 1):
            if _complete(data[start:end]):
                out.append(data[start:end])
                start = end
                break
        else:
            out.append(data[start:])
            break
    return out


class Model:
    kind = "binary"  # binary: one frame per gap; text: commands end in CR

    def __init__(self, name: str, **cfg: Any) -> None:
        self.name = name
        self.quiet = False  # stops answering (a dead device)
        self.heard: list[str] = []  # frames addressed to this model, as HEX (or text)

    def handle(self, frame: bytes) -> list[tuple[float, bytes]]:
        return []

    def event(self, name: str, **args: Any) -> list[tuple[float, bytes]]:
        raise ValueError(f"{self.name}: no event {name}")

    def state(self) -> dict[str, Any]:
        return {}

    def set(self, **values: Any) -> None:
        for key, value in values.items():
            if key == "quiet":
                self.quiet = bool(value)
            elif not hasattr(self, key):
                raise ValueError(f"{self.name}: no field {key}")
            else:
                setattr(self, key, value)


def _hex(data: bytes) -> str:
    return data.hex(" ").upper()


# ---- RS485 curtain motors -------------------------------------------------------------------
class _Travel:
    """A motor moving between 0 and 100 at a fixed speed."""

    def __init__(self, travel_s: float) -> None:
        self.travel_s = travel_s
        self._pos = 0.0
        self._target = 0.0
        self._since = time.monotonic()

    def now(self) -> float:
        t = time.monotonic()
        step = (t - self._since) * 100 / self.travel_s
        if self._pos < self._target:
            self._pos = min(self._target, self._pos + step)
        elif self._pos > self._target:
            self._pos = max(self._target, self._pos - step)
        self._since = t
        return self._pos

    def go(self, target: float) -> None:
        self.now()
        self._target = max(0.0, min(100.0, target))

    def stop(self) -> None:
        self._target = self.now()

    def put(self, position: float) -> None:
        self._pos = self._target = float(position)
        self._since = time.monotonic()

    @property
    def moving(self) -> int:
        """0 stopped, 1 opening (towards 100), 2 closing."""
        pos = self.now()
        return 0 if pos == self._target else (1 if self._target > pos else 2)


class Dooya(Model):
    """Dooya RS485 protocol A4: 55 ID_L ID_H func data CRC16/Modbus (low first). Position 100 = open."""

    def __init__(self, name: str, addr: str = "FE FE", travel_s: float = 4.0, position: float = 0,
                 calibrated: bool = True, **cfg: Any) -> None:
        super().__init__(name)
        self.addr = bytes.fromhex(addr.replace(" ", ""))
        self.motor = _Travel(float(travel_s))
        self.motor.put(position)
        self.calibrated = calibrated

    def handle(self, frame: bytes) -> list[tuple[float, bytes]]:
        if len(frame) < 6 or frame[0] != 0x55 or not crc_ok(frame):
            return []
        target, func = frame[1:3], frame[3]
        broadcast = target == b"\x00\x00"
        if target != self.addr and not broadcast:
            return []
        self.heard.append(_hex(frame))
        if self.quiet:
            return []
        if func == 0x03:  # control: answered with the same frame (FF in the data when it cannot)
            command = frame[4]
            if command == 0x01:
                self.motor.go(100)
            elif command == 0x02:
                self.motor.go(0)
            elif command == 0x03:
                self.motor.stop()
            elif command == 0x04 and len(frame) == 8:
                if not self.calibrated:
                    return [] if broadcast else [(REPLY, with_crc(frame[:5] + b"\xff"))]
                self.motor.go(frame[5])
            else:
                return []
            return [] if broadcast else [(REPLY, frame)]
        if func == 0x01 and len(frame) == 8 and not broadcast:  # read register(s): 55 ID 01 len data CRC
            register = frame[4]
            if register == 0x02:
                value = round(self.motor.now()) if self.calibrated else 0xFF
            elif register == 0x05:
                value = self.motor.moving
            else:
                return []
            return [(REPLY, with_crc(b"\x55" + self.addr + bytes([0x01, 0x01, value])))]
        return []

    def state(self) -> dict[str, Any]:
        return {"position": round(self.motor.now(), 1), "moving": self.motor.moving, "calibrated": self.calibrated}

    def set(self, **values: Any) -> None:
        if "position" in values:
            self.motor.put(values.pop("position"))
        super().set(**values)


class AOK(Model):
    """A-OK RS-485 v05: 9A ID CH_L CH_H CMD DATA XOR; replies (queries only) D8 ID CH_L CH_H D4..D8 XOR.
    The motor's position runs the other way: 0 = open (up limit), 100 = closed."""

    def __init__(self, name: str, id: str = "01", ch: str = "01 00", travel_s: float = 4.0, position: float = 100,
                 **cfg: Any) -> None:
        super().__init__(name)
        self.id = int(id, 16)
        self.ch = bytes.fromhex(ch.replace(" ", ""))
        self.mask = int.from_bytes(self.ch, "little")
        self.motor = _Travel(float(travel_s))
        self.motor.put(position)

    def handle(self, frame: bytes) -> list[tuple[float, bytes]]:
        if len(frame) != 7 or frame[0] != 0x9A or xor8(frame[1:6]) != frame[6]:
            return []
        motor_id, mask, command, data = frame[1], int.from_bytes(frame[2:4], "little"), frame[4], frame[5]
        group = motor_id == 0
        if not group and (motor_id != self.id or not mask & self.mask):
            return []
        self.heard.append(_hex(frame))
        if self.quiet:
            return []
        if command == 0x0A:  # control: never answered
            if data == 0xDD:
                self.motor.go(0)  # open
            elif data == 0xEE:
                self.motor.go(100)  # close
            elif data == 0xCC:
                self.motor.stop()
            return []
        if command == 0xDD:
            self.motor.go(data)
            return []
        if command == 0xCC and (data == 0x00 and not group or data == 0xCC):
            flags = (1 if self.motor.moving else 0) | 0x02
            body = bytes([self.id]) + self.ch + bytes([0x00, 0xDC, 0x00, round(self.motor.now()), flags])
            return [(0.05, b"\xd8" + body + bytes([xor8(body)]))]
        return []

    def state(self) -> dict[str, Any]:
        return {"position": round(self.motor.now(), 1), "moving": self.motor.moving}

    def set(self, **values: Any) -> None:
        if "position" in values:
            self.motor.put(values.pop("position"))
        super().set(**values)


# ---- Modbus RTU -------------------------------------------------------------------------------
class _Modbus(Model):
    def __init__(self, name: str, addr: str = "01", **cfg: Any) -> None:
        super().__init__(name)
        self.addr = int(addr, 16)

    def handle(self, frame: bytes) -> list[tuple[float, bytes]]:
        if len(frame) < 4 or not crc_ok(frame) or frame[0] not in (self.addr, 0):
            return []
        self.heard.append(_hex(frame))
        if self.quiet:
            return []
        reply = self.request(frame[1], frame[2:-2], broadcast=frame[0] == 0)
        if reply is None or frame[0] == 0 and not self.answers_broadcast(frame):
            return []
        return [(REPLY, with_crc(bytes([self.addr]) + reply))]

    def answers_broadcast(self, frame: bytes) -> bool:
        return False

    def request(self, function: int, data: bytes, broadcast: bool) -> bytes | None:
        return bytes([function | 0x80, 0x01])  # illegal function

    @staticmethod
    def exception(function: int, code: int) -> bytes:
        return bytes([function | 0x80, code])


class WaveshareRelay(_Modbus):
    """Waveshare Modbus RTU Relay: coils 0000-0007; 05 FF00 on / 0000 off / 5500 flip (its own value);
    coil 00FF = all; 01 reads coils; 0F writes several; 03/06 on 4000 = the address (broadcast answered)."""

    def __init__(self, name: str, addr: str = "01", channels: int = 8, **cfg: Any) -> None:
        super().__init__(name, addr)
        self.coils = [False] * int(channels)

    def answers_broadcast(self, frame: bytes) -> bool:
        return frame[1] in (0x03, 0x06) and frame[2:4] == b"\x40\x00"

    def request(self, function: int, data: bytes, broadcast: bool) -> bytes | None:
        if function == 0x01 and len(data) == 4:
            start, count = int.from_bytes(data[:2], "big"), int.from_bytes(data[2:], "big")
            if not 1 <= count <= len(self.coils) or start + count > len(self.coils):
                return self.exception(function, 0x02)
            bits = 0
            for i in range(count):
                bits |= self.coils[start + i] << i
            size = (count + 7) // 8
            return bytes([0x01, size]) + bits.to_bytes(size, "little")
        if function == 0x05 and len(data) == 4:
            coil, value = int.from_bytes(data[:2], "big"), data[2:]
            targets = range(len(self.coils)) if coil == 0x00FF else [coil] if coil < len(self.coils) else None
            if targets is None:
                return self.exception(function, 0x02)
            for i in targets:
                if value == b"\xff\x00":
                    self.coils[i] = True
                elif value == b"\x00\x00":
                    self.coils[i] = False
                elif value == b"\x55\x00":
                    self.coils[i] = not self.coils[i]
                else:
                    return self.exception(function, 0x03)
            return bytes([0x05]) + data  # a write is answered with the same frame
        if function == 0x0F and len(data) >= 5:
            start, count = int.from_bytes(data[:2], "big"), int.from_bytes(data[2:4], "big")
            bits = int.from_bytes(data[5:5 + data[4]], "little")
            for i in range(count):
                if start + i < len(self.coils):
                    self.coils[start + i] = bool(bits >> i & 1)
            return bytes([0x0F]) + data[:4]
        if function == 0x03 and data[:2] == b"\x40\x00":
            return bytes([0x03, 0x02, 0x00, self.addr])
        return self.exception(function, 0x01)

    def state(self) -> dict[str, Any]:
        return {"coils": self.coils}

    def set(self, **values: Any) -> None:
        if "coils" in values:
            self.coils = [bool(v) for v in values.pop("coils")]
        for key in [k for k in values if k.startswith("coil")]:
            self.coils[int(key[4:])] = bool(values.pop(key))
        super().set(**values)


class XYMD02(_Modbus):
    """XY-MD02: input registers 0001 temperature (signed, x10) and 0002 humidity (x10); 0101 = address."""

    def __init__(self, name: str, addr: str = "01", temperature: float = 25.0, humidity: float = 50.0,
                 **cfg: Any) -> None:
        super().__init__(name, addr)
        self.temperature = float(temperature)
        self.humidity = float(humidity)

    def request(self, function: int, data: bytes, broadcast: bool) -> bytes | None:
        if function == 0x04 and len(data) == 4:
            start, count = int.from_bytes(data[:2], "big"), int.from_bytes(data[2:], "big")
            registers = {1: round(self.temperature * 10), 2: round(self.humidity * 10)}
            if count < 1 or any(r not in registers for r in range(start, start + count)):
                return self.exception(function, 0x02)
            values = b"".join(registers[r].to_bytes(2, "big", signed=True) for r in range(start, start + count))
            return bytes([0x04, len(values)]) + values
        if function == 0x03 and data[:2] == b"\x01\x01":
            return bytes([0x03, 0x02, 0x00, self.addr])
        return self.exception(function, 0x01)

    def state(self) -> dict[str, Any]:
        return {"temperature": self.temperature, "humidity": self.humidity}

    def set(self, **values: Any) -> None:
        for key in ("temperature", "humidity"):
            if key in values:
                setattr(self, key, float(values.pop(key)))
        super().set(**values)


class ModbusDimmer(_Modbus):
    """A dimmer with holding registers: 0000 level 0-100, 0001 on (1) / off (0). 06 writes (echoed), 03 reads."""

    def __init__(self, name: str, addr: str = "05", level: int = 0, on: bool = False, **cfg: Any) -> None:
        super().__init__(name, addr)
        self.registers = {0: int(level), 1: int(bool(on))}

    def request(self, function: int, data: bytes, broadcast: bool) -> bytes | None:
        if function == 0x06 and len(data) == 4:
            register, value = int.from_bytes(data[:2], "big"), int.from_bytes(data[2:], "big")
            if register not in self.registers or register == 0 and value > 100:
                return self.exception(function, 0x03 if register in self.registers else 0x02)
            self.registers[register] = value
            return bytes([0x06]) + data
        if function == 0x03 and len(data) == 4:
            start, count = int.from_bytes(data[:2], "big"), int.from_bytes(data[2:], "big")
            if count < 1 or any(r not in self.registers for r in range(start, start + count)):
                return self.exception(function, 0x02)
            values = b"".join(self.registers[r].to_bytes(2, "big") for r in range(start, start + count))
            return bytes([0x03, len(values)]) + values
        return self.exception(function, 0x01)

    def state(self) -> dict[str, Any]:
        return {"level": self.registers[0], "on": bool(self.registers[1])}

    def set(self, **values: Any) -> None:
        if "level" in values:
            self.registers[0] = int(values.pop("level"))
        if "on" in values:
            self.registers[1] = int(bool(values.pop("on")))
        super().set(**values)


class Keypad(Model):
    """A wall keypad that sends a frame of its own when a key is pressed: A5 5A <addr> <key> <sum8>.
    (Real panels are configured per site; this layout is the test's own.) It answers nothing."""

    def __init__(self, name: str, addr: str = "10", **cfg: Any) -> None:
        super().__init__(name)
        self.addr = int(addr, 16)
        self.presses = 0

    def frame(self, key: int) -> bytes:
        body = bytes([0xA5, 0x5A, self.addr, key])
        return body + bytes([sum8(body)])

    def event(self, name: str, key: int = 1, repeat: int = 1, gap_ms: int = 60, joined: bool = False,
              keys: list[int] | None = None, **args: Any) -> list[tuple[float, bytes]]:
        """A press, sent `repeat` times `gap_ms` apart — or `joined`: all in one write, back to back
        (as some panels send a press twice; `keys` joins different keys)."""
        if name != "press":
            return super().event(name)
        self.presses += 1
        frames = [self.frame(int(k)) for k in keys] if keys else [self.frame(int(key))] * int(repeat)
        if joined:
            return [(0.0, b"".join(frames))]
        return [(i * gap_ms / 1000, frame) for i, frame in enumerate(frames)]

    def state(self) -> dict[str, Any]:
        return {"presses": self.presses}


# ---- RS232 text devices -----------------------------------------------------------------------
class _Text(Model):
    kind = "text"
    terminator = b"\r"

    def __init__(self, name: str, **cfg: Any) -> None:
        super().__init__(name)
        self._buffer = b""

    def handle(self, frame: bytes) -> list[tuple[float, bytes]]:
        self._buffer += frame
        out: list[tuple[float, bytes]] = []
        while self.terminator in self._buffer:
            line, self._buffer = self._buffer.split(self.terminator, 1)
            text = line.decode("latin-1")
            self.heard.append(text)
            if not self.quiet:
                out += [(REPLY, r) for r in self.command(text)]
        return out

    def command(self, text: str) -> list[bytes]:
        return []


class Epson(_Text):
    """ESC/VP21: 'PWR ON\\r' ... answers ':' when ready, 'NAME=value\\r:' to queries, 'ERR\\r:' when it cannot.
    PWR: 00/04 standby, 01 on, 02 warming up, 03 cooling down. Most commands fail unless the lamp is on."""

    def __init__(self, name: str, warmup_s: float = 3.0, cooldown_s: float = 2.0, **cfg: Any) -> None:
        super().__init__(name)
        self.warmup_s, self.cooldown_s = float(warmup_s), float(cooldown_s)
        self._power, self._since = "04", time.monotonic()
        self.source, self.mute, self.volume = "30", False, 10

    @property
    def power(self) -> str:
        elapsed = time.monotonic() - self._since
        if self._power == "02" and elapsed >= self.warmup_s:
            self._power = "01"
        elif self._power == "03" and elapsed >= self.cooldown_s:
            self._power = "04"
        return self._power

    def command(self, text: str) -> list[bytes]:
        text = text.strip()
        power = self.power
        if not text:
            return [b":"]
        if text == "PWR?":
            return [f"PWR={power}\r:".encode()]
        if text == "PWR ON":
            if power in ("00", "04"):
                self._power, self._since = "02", time.monotonic()
            return [b":"] if power != "03" else [b"ERR\r:"]
        if text == "PWR OFF":
            if power in ("01", "02"):
                self._power, self._since = "03", time.monotonic()
            return [b":"]
        if power != "01":
            return [b"ERR\r:"]  # standby, warming up or cooling down
        if m := re.fullmatch(r"SOURCE ([0-9A-F]{2})", text):
            self.source = m.group(1)
            return [b":"]
        if text == "SOURCE?":
            return [f"SOURCE={self.source}\r:".encode()]
        if text in ("MUTE ON", "MUTE OFF"):
            self.mute = text.endswith("ON")
            return [b":"]
        if text == "MUTE?":
            return [f"MUTE={'ON' if self.mute else 'OFF'}\r:".encode()]
        if text in ("VOL INC", "VOL DEC"):
            self.volume = max(0, min(20, self.volume + (1 if text.endswith("INC") else -1)))
            return [b":"]
        if text == "VOL?":
            return [f"VOL={self.volume}\r:".encode()]
        return [b"ERR\r:"]

    def state(self) -> dict[str, Any]:
        return {"power": self.power, "source": self.source, "mute": self.mute, "volume": self.volume}

    def set(self, **values: Any) -> None:
        if "power" in values:
            self._power, self._since = str(values.pop("power")), time.monotonic()
        super().set(**values)


class BenQ(_Text):
    """BenQ: '\\r*key=value#\\r'; over RS-232 the projector echoes the command after a '>' prompt, then
    answers '*KEY=VALUE#'; lines end CR LF. In transition it answers '*Block item#'."""

    SOURCES = {"HDMI": "HDMI", "HDMI2": "HDMI2", "RGB": "RGB", "RGB2": "RGB2", "VID": "VID", "SVID": "SVID"}

    def __init__(self, name: str, transition_s: float = 2.0, **cfg: Any) -> None:
        super().__init__(name)
        self.transition_s = float(transition_s)
        self.power, self._since = "OFF", 0.0
        self.source, self.mute, self.volume = "HDMI", False, 5

    def command(self, text: str) -> list[bytes]:
        text = text.strip()
        if not text:
            return [b"\r\n>"]
        m = re.fullmatch(r"\*(\w+)=([^#]+)#", text)
        echo = f">{text}\r\n"
        if not m:
            return [f"{echo}*Illegal format#\r\n".encode()]
        key, value = m.group(1).lower(), m.group(2).upper()
        busy = time.monotonic() - self._since < self.transition_s
        if key == "pow":
            if value == "?":
                return [f"{echo}*POW={self.power}#\r\n".encode()]
            if busy:
                return [f"{echo}*Block item#\r\n".encode()]
            if value in ("ON", "OFF") and value != self.power:
                self.power, self._since = value, time.monotonic()
            return [f"{echo}*POW={value}#\r\n".encode()]
        if self.power != "ON" or busy:
            return [f"{echo}*Block item#\r\n".encode()]
        if key == "sour":
            if value != "?":
                if value not in self.SOURCES:
                    return [f"{echo}*Unsupported item#\r\n".encode()]
                self.source = value
            return [f"{echo}*SOUR={self.source}#\r\n".encode()]
        if key == "mute":
            if value in ("ON", "OFF"):
                self.mute = value == "ON"
            return [f"{echo}*MUTE={'ON' if self.mute else 'OFF'}#\r\n".encode()]
        if key == "vol":
            if value in ("+", "-"):
                self.volume = max(0, min(20, self.volume + (1 if value == "+" else -1)))
                return [f"{echo}*VOL={value}#\r\n".encode()]
            return [f"{echo}*VOL={self.volume}#\r\n".encode()]
        return [f"{echo}*Unsupported item#\r\n".encode()]

    def state(self) -> dict[str, Any]:
        return {"power": self.power, "source": self.source, "mute": self.mute, "volume": self.volume}


class Denon(_Text):
    """Denon / Marantz: 2-letter commands + CR. Every change is announced as an event in the command's own
    form (from RS-232, the remote or the knob). MV: 80 = 0 dB, half steps as 3 digits (MV505)."""

    SOURCES = ("CD", "DVD", "BD", "GAME", "TV", "SAT/CBL", "MPLAY", "TUNER", "AUX1", "NET")

    def __init__(self, name: str, **cfg: Any) -> None:
        super().__init__(name)
        self.power, self.volume, self.mute, self.source = "STANDBY", 50.0, False, "DVD"

    @staticmethod
    def mv(volume: float) -> str:
        whole = int(volume)
        return f"MV{whole:02d}5" if volume - whole >= 0.5 else f"MV{whole:02d}"

    def command(self, text: str) -> list[bytes]:
        text = text.strip()
        if text == "PW?":
            return [f"PW{self.power}\r".encode()]
        if text in ("PWON", "PWSTANDBY"):
            self.power = text[2:]
            zone = "ZMON" if self.power == "ON" else "ZMOFF"
            return [f"{text}\r{zone}\r".encode()]
        if self.power != "ON":
            return []  # in standby only power commands are answered
        if text == "MV?":
            return [f"{self.mv(self.volume)}\rMVMAX 98\r".encode()]
        if text in ("MVUP", "MVDOWN"):
            self.volume = max(0.0, min(98.0, self.volume + (0.5 if text == "MVUP" else -0.5)))
            return [f"{self.mv(self.volume)}\r".encode()]
        if m := re.fullmatch(r"MV(\d\d)(5?)", text):
            self.volume = min(98.0, int(m.group(1)) + (0.5 if m.group(2) else 0.0))
            return [f"{self.mv(self.volume)}\r".encode()]
        if text in ("MUON", "MUOFF", "MU?"):
            if text != "MU?":
                self.mute = text == "MUON"
            return [f"MU{'ON' if self.mute else 'OFF'}\r".encode()]
        if text == "SI?":
            return [f"SI{self.source}\r".encode()]
        if text.startswith("SI") and text[2:] in self.SOURCES:
            self.source = text[2:]
            return [f"SI{self.source}\rMSSTEREO\r".encode()]  # a source change also reports the surround mode
        return []

    def event(self, name: str, volume: float | None = None, **args: Any) -> list[tuple[float, bytes]]:
        if name == "knob" and volume is not None:  # someone turns the volume knob
            self.volume = float(volume)
            return [(0.0, f"{self.mv(self.volume)}\r".encode())]
        return super().event(name)

    def state(self) -> dict[str, Any]:
        return {"power": self.power, "volume": self.volume, "mute": self.mute, "source": self.source}


class Extron(_Text):
    """Extron SIS matrix: 'I*O!' ties input I to output O (audio + video), answered 'OutO InI All\\r\\n';
    'O!' views (verbose 0/1: 'I\\r\\n'); ESC 'nCV' CR sets the verbose mode. Commands need no terminator."""

    terminator = b"!"

    def __init__(self, name: str, inputs: int = 4, outputs: int = 4, **cfg: Any) -> None:
        super().__init__(name)
        self.inputs, self.outputs = int(inputs), int(outputs)
        self.ties = {o: 0 for o in range(1, self.outputs + 1)}
        self.verbose = 1

    def handle(self, frame: bytes) -> list[tuple[float, bytes]]:
        out: list[tuple[float, bytes]] = []
        for m in re.finditer(rb"\x1b(\d)CV\r", frame):  # ESC commands end in CR
            self.verbose = int(m.group(1))
            self.heard.append(f"ESC {m.group(1).decode()}CV")
            out.append((REPLY, f"Vrb{self.verbose}\r\n".encode()))
        frame = re.sub(rb"\x1b\dCV\r", b"", frame)
        return out + super().handle(frame)

    def command(self, text: str) -> list[bytes]:
        text = text.strip()
        if m := re.fullmatch(r"(\d+)\*(\d+)", text):
            source, output = int(m.group(1)), int(m.group(2))
            if source > self.inputs:
                return [b"E01\r\n"]
            if output < 1 or output > self.outputs:
                return [b"E12\r\n"]
            self.ties[output] = source
            return [f"Out{output} In{source} All\r\n".encode()]
        if m := re.fullmatch(r"(\d+)", text):
            output = int(m.group(1))
            if output not in self.ties:
                return [b"E12\r\n"]
            if self.verbose >= 2:
                return [f"Out{output} In{self.ties[output]} All\r\n".encode()]
            return [f"{self.ties[output]}\r\n".encode()]
        return [b"E10\r\n"]

    def state(self) -> dict[str, Any]:
        return {"ties": {str(k): v for k, v in self.ties.items()}, "verbose": self.verbose}

    def set(self, **values: Any) -> None:
        if "ties" in values:  # from JSON: output numbers arrive as text
            self.ties.update({int(k): int(v) for k, v in values.pop("ties").items()})
        super().set(**values)


class Blackbird(_Text):
    """'1V2.' ties input 1 to output 2, answered 'AV:01->02'; 'Status2.' reports output 2; '.' ends a command."""

    terminator = b"."

    def __init__(self, name: str, inputs: int = 4, outputs: int = 4, **cfg: Any) -> None:
        super().__init__(name)
        self.inputs, self.outputs = int(inputs), int(outputs)
        self.ties = {o: o if o <= self.inputs else 1 for o in range(1, self.outputs + 1)}

    def command(self, text: str) -> list[bytes]:
        text = text.strip()
        if m := re.fullmatch(r"(\d+)V([\d,]+)", text):
            source = int(m.group(1))
            outputs = [int(o) for o in m.group(2).split(",")]
            if not 1 <= source <= self.inputs or any(not 1 <= o <= self.outputs for o in outputs):
                return [b"Error\r\n"]
            for output in outputs:
                self.ties[output] = source
            return [f"AV:{source:02d}->{o:02d}\r\n".encode() for o in outputs]
        if m := re.fullmatch(r"Status(\d*)", text):
            outputs = [int(m.group(1))] if m.group(1) else sorted(self.ties)
            return [f"AV:{self.ties[o]:02d}->{o:02d}\r\n".encode() for o in outputs if o in self.ties]
        return [b"Error\r\n"]

    def state(self) -> dict[str, Any]:
        return {"ties": {str(k): v for k, v in self.ties.items()}}

    def set(self, **values: Any) -> None:
        if "ties" in values:  # from JSON: output numbers arrive as text
            self.ties.update({int(k): int(v) for k, v in values.pop("ties").items()})
        super().set(**values)


MODELS: dict[str, type[Model]] = {
    "dooya": Dooya, "aok": AOK, "waveshare_relay": WaveshareRelay, "xymd02": XYMD02, "modbus_dimmer": ModbusDimmer,
    "keypad": Keypad, "epson": Epson, "benq": BenQ, "denon": Denon, "extron": Extron, "blackbird": Blackbird,
}
