"""Command templates and receive patterns.

Commands are written the way protocol sheets print them, with placeholders where a value goes:

    55 {addr} 03 {value:u8} {crc16_modbus}    HEX: a device parameter, a value, a checksum
    PWR ON\\r      VOL {value:03d}\\r            text: escapes, Python format specs

Receive patterns read frames back, for state feedback and sensors:

    55 {addr} 03 ?? {pos:u8} {crc16_modbus}    ?? any byte, {name:type} captures a number,
                                               a parameter must match, a checksum must be valid,
                                               * at the end accepts any remaining bytes
    ^PWR=(?P<power>\\d+)                        text: a regular expression with named groups;
    Out0*{output} In(?P<input>\\d+)              {param} stands for a device parameter's text

Errors carry a code and details so the panel can explain them in the user's language.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from . import checksum
from .codec import parse_hex, unescape

FORMATS = ("hex", "text")

# name -> (bytes, byte order, signed)
NUMBERS: dict[str, tuple[int, str, bool]] = {
    "u8": (1, "big", False), "s8": (1, "big", True),
    "u16": (2, "big", False), "u16be": (2, "big", False), "u16le": (2, "little", False),
    "s16": (2, "big", True), "s16be": (2, "big", True), "s16le": (2, "little", True),
    "u24": (3, "big", False), "u24be": (3, "big", False), "u24le": (3, "little", False),
    "u32": (4, "big", False), "u32be": (4, "big", False), "u32le": (4, "little", False),
    "s32": (4, "big", True), "s32be": (4, "big", True), "s32le": (4, "little", True),
}
BCD = {"bcd": 1, "bcd2": 2}

_TOKEN = re.compile(r"\s+|,|\{([^{}]*)\}|\?\?|\*|(?:0[xX])?([0-9A-Fa-f]+)")
_FIELD = re.compile(r"^(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?:@(?P<start>\d+))?(?::(?P<type>[A-Za-z0-9]+))?$")
_TEXT_FIELD = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)(?::([^{}]*))?\}")


class TemplateError(ValueError):
    """A template or pattern that cannot be used; `code` + `info` are for translation."""

    def __init__(self, code: str, **info: Any) -> None:
        super().__init__(f"{code}: {info}" if info else code)
        self.code = code
        self.info = info


@dataclass(frozen=True, slots=True)
class _Field:
    name: str
    start: int
    type: str | None


def _field(spec: str) -> _Field:
    m = _FIELD.match(spec.strip())
    if not m:
        raise TemplateError("bad_field", field=spec)
    kind = m.group("type")
    if kind and kind not in NUMBERS and kind not in BCD and kind != "hex":
        raise TemplateError("bad_type", field=spec, type=kind)
    return _Field(m.group("name"), int(m.group("start") or 0), kind)


def _tokens(text: str) -> list[tuple[str, Any]]:
    """("bytes", b) | ("field", _Field) | ("any", None) | ("rest", None)."""
    out: list[tuple[str, Any]] = []
    pos = 0
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m or m.end() == pos:
            raise TemplateError("bad_token", at=pos + 1, text=text[pos:pos + 8])
        token = m.group(0)
        if m.group(1) is not None:
            out.append(("field", _field(m.group(1))))
        elif token == "??":
            out.append(("any", None))
        elif token == "*":
            out.append(("rest", None))
        elif m.group(2) is not None:
            digits = m.group(2)
            if len(digits) % 2:
                raise TemplateError("odd_hex", text=token)
            out.append(("bytes", bytes.fromhex(digits)))
        pos = m.end()
    return out


def _encode(value: Any, kind: str | None, name: str) -> bytes:
    if kind is None or kind == "hex":
        if isinstance(value, (bytes, bytearray)):
            return bytes(value)
        if isinstance(value, str):
            try:
                return parse_hex(value)
            except ValueError as err:
                raise TemplateError("bad_param", field=name, value=value) from err
        kind = "u8"
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError) as err:
        raise TemplateError("not_number", field=name, value=value) from err
    if kind in BCD:
        width = BCD[kind]
        if not 0 <= number < 10 ** (2 * width):
            raise TemplateError("range", field=name, value=number)
        digits = f"{number:0{2 * width}d}"
        return bytes(int(digits[i:i + 2], 16) for i in range(0, 2 * width, 2))
    width, order, signed = NUMBERS[kind]
    try:
        return number.to_bytes(width, order, signed=signed)
    except OverflowError as err:
        raise TemplateError("range", field=name, value=number) from err


def _decode(raw: bytes, kind: str) -> int:
    if kind in BCD:
        digits = raw.hex()
        if not digits.isdigit():
            raise ValueError("not BCD")
        return int(digits)
    _width, order, signed = NUMBERS[kind]
    return int.from_bytes(raw, order, signed=signed)


def _width(kind: str) -> int:
    return BCD[kind] if kind in BCD else NUMBERS[kind][0]


def fields_used(template: str, fmt: str) -> set[str]:
    """Names a command template needs (checksums excluded)."""
    if fmt == "text":
        return {m.group(1) for m in _TEXT_FIELD.finditer(template)}
    return {v.name for k, v in _tokens(template) if k == "field" and v.name not in checksum.ALGORITHMS}


# ---- commands ---------------------------------------------------------------------------
def render_hex(template: str, variables: dict[str, Any]) -> bytes:
    parts: list[bytes | _Field] = []
    for kind, value in _tokens(template):
        if kind in ("any", "rest"):
            raise TemplateError("wildcard_in_command")
        if kind == "bytes":
            parts.append(value)
        elif value.name in checksum.ALGORITHMS:
            parts.append(value)
        elif value.name not in variables:
            raise TemplateError("no_value", field=value.name)
        else:
            parts.append(_encode(variables[value.name], value.type, value.name))
    out = bytearray()
    for part in parts:  # checksums last, over the bytes in front of them
        out += checksum.compute(part.name, bytes(out), part.start) if isinstance(part, _Field) else part
    return bytes(out)


def render_text(template: str, variables: dict[str, Any]) -> bytes:
    def sub(m: re.Match[str]) -> str:
        name, spec = m.group(1), m.group(2) or ""
        if name not in variables:
            raise TemplateError("no_value", field=name)
        value = variables[name]
        if spec and spec[-1:] in "dxXob" and not isinstance(value, int):
            try:
                value = int(round(float(value)))
            except (TypeError, ValueError) as err:
                raise TemplateError("not_number", field=name, value=value) from err
        try:
            return format(value, spec)
        except (TypeError, ValueError) as err:
            raise TemplateError("bad_format", field=name, spec=spec) from err

    try:
        return unescape(_TEXT_FIELD.sub(sub, template))
    except TemplateError:
        raise
    except ValueError as err:
        raise TemplateError("bad_escape", detail=str(err)) from err


def render(template: str, fmt: str, variables: dict[str, Any]) -> bytes:
    if fmt == "text":
        return render_text(template, variables)
    return render_hex(template, variables)


# ---- receive patterns -------------------------------------------------------------------
class Pattern:
    """A compiled receive pattern; match() returns the captures, or None."""

    def __init__(self, text: str, fmt: str, params: dict[str, str]) -> None:
        self.text = text
        self.fmt = fmt
        self.regex: re.Pattern[str] | None = None
        self.items: list[tuple[str, Any]] = []
        self.captures: list[str] = []
        self.length: int | None = None
        if fmt == "text":
            def param(m: re.Match[str]) -> str:  # {output} -> the parameter, escaped; \d{2} stays a quantifier
                name = m.group(1)
                return re.escape(params[name]) if name in params and m.group(2) is None else m.group(0)

            try:
                self.regex = re.compile(_TEXT_FIELD.sub(param, text))
            except re.error as err:
                raise TemplateError("bad_regex", detail=str(err)) from err
            return
        tokens = _tokens(text)
        for index, (kind, value) in enumerate(tokens):
            if kind == "rest" and index != len(tokens) - 1:
                raise TemplateError("rest_not_last")
            if kind == "field":
                if value.name in checksum.ALGORITHMS:
                    kind = "check"
                elif value.name in params and value.type is None:
                    kind, value = "bytes", _encode(params[value.name], None, value.name)
                elif value.type is None or value.type == "hex":
                    raise TemplateError("capture_needs_type", field=value.name)
                else:
                    kind = "number"
            self.items.append((kind, value))
        self.captures = [v.name for k, v in self.items if k == "number"]
        self.length = self._length()

    def _length(self) -> int | None:
        """Bytes in a frame this HEX pattern matches; None for text and for patterns ending in *."""
        if self.regex is not None or any(kind == "rest" for kind, _ in self.items):
            return None
        total = 0
        for kind, value in self.items:
            if kind == "bytes":
                total += len(value)
            elif kind == "any":
                total += 1
            elif kind == "number":
                total += _width(value.type)
            else:
                total += len(checksum.compute(value.name, b""))
        return total

    def match(self, data: bytes) -> dict[str, Any] | None:
        if self.regex is not None:
            m = self.regex.search(data.decode("utf-8", "replace"))
            if m is None:
                return None
            return {k: _number(v) for k, v in m.groupdict().items() if v is not None}
        pos, found = 0, {}
        for kind, value in self.items:
            if kind == "rest":
                return found
            if kind == "bytes":
                if data[pos:pos + len(value)] != value:
                    return None
                pos += len(value)
            elif kind == "any":
                if pos >= len(data):
                    return None
                pos += 1
            elif kind == "number":
                width = _width(value.type)
                raw = data[pos:pos + width]
                if len(raw) < width:
                    return None
                try:
                    found[value.name] = _decode(raw, value.type)
                except ValueError:
                    return None
                pos += width
            else:  # checksum over the bytes in front of it
                expected = checksum.compute(value.name, data[:pos], value.start)
                if data[pos:pos + len(expected)] != expected:
                    return None
                pos += len(expected)
        return found if pos == len(data) else None


def _number(text: str) -> Any:
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return text
