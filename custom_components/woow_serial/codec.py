"""HEX / escaped-text conversions shared by entities and services."""

from __future__ import annotations

import re

HEX_PATTERN = r"^[0-9A-Fa-fxX\s,:\-]*$"
_PREFIX = re.compile(r"(?<![0-9A-Fa-f])0[xX]")
_SEPARATORS = re.compile(r"[\s,:\-]")
_ESCAPES = {"r": b"\r", "n": b"\n", "t": b"\t", "0": b"\0", "\\": b"\\"}
_SHOW = {0x0D: "\\r", 0x0A: "\\n", 0x09: "\\t", 0x5C: "\\\\"}


def parse_hex(text: str) -> bytes:
    """'A5 5A 01', 'a55a01', '0xA5,0x5A' -> bytes."""
    digits = _SEPARATORS.sub("", _PREFIX.sub("", text))
    if len(digits) % 2:
        raise ValueError("odd number of hex digits")
    return bytes.fromhex(digits)


def to_hex(data: bytes) -> str:
    return data.hex(" ").upper()


def unescape(text: str) -> bytes:
    r"""Text with \r \n \t \0 \\ \xHH escapes -> bytes (other characters as UTF-8)."""
    out, i = bytearray(), 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text):
            nxt = text[i + 1]
            if nxt in _ESCAPES:
                out += _ESCAPES[nxt]
                i += 2
                continue
            if nxt in "xX":
                pair = text[i + 2:i + 4]
                if len(pair) != 2 or any(c not in "0123456789abcdefABCDEF" for c in pair):
                    raise ValueError(f"bad escape {text[i:i + 4]!r}, use \\xHH")
                out.append(int(pair, 16))
                i += 4
                continue
        out += ch.encode()
        i += 1
    return bytes(out)


def printable(data: bytes) -> str:
    """Bytes -> readable text: printable ASCII as is, the rest as escapes."""
    return "".join(
        _SHOW.get(b) or (chr(b) if 0x20 <= b < 0x7F else f"\\x{b:02X}") for b in data
    )


def describe(data: bytes) -> dict:
    return {"hex": to_hex(data), "text": printable(data), "length": len(data)}


def clip(text: str, limit: int = 255) -> str:
    """Fit a state value into HA's 255-character limit."""
    return text if len(text) <= limit else text[:limit - 1] + "…"
