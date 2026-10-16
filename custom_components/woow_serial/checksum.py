"""Checksums used by RS485 / RS232 device protocols, and spotting which one a frame carries.

Custom protocols almost always end in one of a handful of checks. Naming it on every frame the
monitor hears is what lets a user build a working command from a captured one later.
"""

from __future__ import annotations

from collections.abc import Callable


def sum8(data: bytes) -> bytes:
    return bytes([sum(data) & 0xFF])


def sum8_neg(data: bytes) -> bytes:
    """Two's complement of the sum (the frame then sums to zero)."""
    return bytes([-sum(data) & 0xFF])


def xor8(data: bytes) -> bytes:
    value = 0
    for b in data:
        value ^= b
    return bytes([value])


def sum16(data: bytes) -> bytes:
    return (sum(data) & 0xFFFF).to_bytes(2, "big")


def _crc8(data: bytes, poly: int, init: int, reflect: bool) -> int:
    crc = init
    for b in data:
        if reflect:
            crc ^= b
            for _ in range(8):
                crc = (crc >> 1) ^ poly if crc & 1 else crc >> 1
        else:
            crc ^= b
            for _ in range(8):
                crc = ((crc << 1) ^ poly) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


def crc8(data: bytes) -> bytes:
    return bytes([_crc8(data, 0x07, 0x00, False)])


def crc8_maxim(data: bytes) -> bytes:
    return bytes([_crc8(data, 0x8C, 0x00, True)])


def _crc16_reflected(data: bytes, poly: int, init: int) -> int:
    crc = init
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ poly if crc & 1 else crc >> 1
    return crc


def _crc16(data: bytes, poly: int, init: int) -> int:
    crc = init
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ poly) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def crc16_modbus(data: bytes) -> bytes:
    """CRC-16/MODBUS, low byte first (Modbus RTU, Dooya and many curtain / lighting buses)."""
    return _crc16_reflected(data, 0xA001, 0xFFFF).to_bytes(2, "little")


def crc16_ccitt(data: bytes) -> bytes:
    """CRC-16/CCITT-FALSE, high byte first."""
    return _crc16(data, 0x1021, 0xFFFF).to_bytes(2, "big")


def crc16_xmodem(data: bytes) -> bytes:
    return _crc16(data, 0x1021, 0x0000).to_bytes(2, "big")


ALGORITHMS: dict[str, Callable[[bytes], bytes]] = {
    "crc16_modbus": crc16_modbus,
    "crc16_ccitt": crc16_ccitt,
    "crc16_xmodem": crc16_xmodem,
    "sum16": sum16,
    "crc8": crc8,
    "crc8_maxim": crc8_maxim,
    "xor8": xor8,
    "sum8": sum8,
    "sum8_neg": sum8_neg,
}
# Bytes skipped before the checked range: a fixed header (55, AA 55, ...) is often left out.
_STARTS = (0, 1, 2)


def compute(name: str, data: bytes, start: int = 0) -> bytes:
    """Checksum `name` over data[start:]."""
    return ALGORITHMS[name](data[start:])


def detect(frame: bytes) -> list[str]:
    """Every checksum that closes this frame, as "name" or "name@start" (16-bit ones first).

    A 16-bit match by accident is negligible, but an 8-bit one fits a random frame about once
    in 256 tries, and there are fifteen tries here: "57 4F 4F 57" ends in its own XOR. So one
    frame only nominates candidates; the monitor names a group's checksum once its frames
    agree (see catalog._consensus).
    """
    found: list[str] = []
    for name, func in ALGORITHMS.items():
        width = len(func(b"\x00"))
        body, tail = frame[:-width], frame[-width:]
        for start in _STARTS:
            if len(body) - start < 2:  # a check over fewer than two bytes proves nothing
                break
            if func(body[start:]) == tail:
                found.append(name if start == 0 else f"{name}@{start}")
    return found


def is_wide(label: str | None) -> bool:
    """True for 16-bit checks, which one frame alone is enough to trust."""
    return bool(label) and label.split("@")[0] in ("crc16_modbus", "crc16_ccitt", "crc16_xmodem", "sum16")
