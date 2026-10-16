"""Monitor (HAIR's Sniffer, for bytes): every frame the ports hear, grouped and counted.

Serial frames are digital, so a frame's identity is simply its bytes; what needs care is the
grouping. On a multi-drop RS485 line the first bytes are usually the protocol header and the
device address, so frames are grouped by them (per port, adjustable). Mostly-ASCII frames
(RS232 audio / video gear) form one "text" group per port.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, fields
import hashlib
import time
from typing import Any

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.storage import Store

from . import checksum
from .bus import BusFrame
from .codec import printable, to_hex
from .const import CATALOG_GROUP_ROWS, CATALOG_PREFIX, CATALOG_TOTAL_ROWS, DOMAIN, LIVE_PUSH

SAVE_DELAY = 30


def make_id(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:12]


def is_text(data: bytes) -> bool:
    """Mostly printable ASCII (RS232 command sets such as 'PWR ON\\r')."""
    if len(data) < 2:
        return False
    printable_count = sum(1 for b in data if 0x20 <= b < 0x7F or b in (0x09, 0x0A, 0x0D))
    return printable_count >= 0.9 * len(data) and any(0x41 <= (b | 0x20) <= 0x7A for b in data)


def _load(cls, raw: dict[str, Any]):
    names = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in raw.items() if k in names})


@dataclass
class Group:
    id: str
    port_id: str
    key: str  # what the frames share: first bytes ("A5 5A"), "text", or "*" (no grouping)
    alias: str = ""
    hidden: bool = False
    order: float = 0.0  # ascending; a new group lands on top until the user moves it
    count: int = 0
    first_seen: float = 0.0
    last_seen: float = 0.0


@dataclass
class Row:
    id: str
    group_id: str
    port_id: str
    hex: str
    length: int
    text: str | None = None  # readable form of a mostly-ASCII frame
    checks: list[str] = field(default_factory=list)  # checksums this frame ends in: "crc16_modbus", "sum8@1"
    alias: str = ""
    count: int = 0
    first_seen: float = 0.0
    last_seen: float = 0.0


class Catalog:
    """Groups and rows, persisted, with batched pushes to the panel."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store: Store[dict[str, Any]] = Store(hass, 1, f"{DOMAIN}.catalog")
        self.groups: dict[str, Group] = {}
        self.rows: dict[str, Row] = {}
        self.prefix: dict[str, int] = {}  # port id -> grouping length
        self._by_group: dict[str, set[str]] = {}
        self._rate: dict[str, list[float]] = {}  # group id -> [window start, frames, rate]
        self._listeners: list[Callable[[dict[str, Any]], None]] = []
        self._dirty_groups: set[str] = set()
        self._dirty_rows: set[str] = set()
        self._removed: set[str] = set()
        self._push_handle = None

    # ---- persistence ----------------------------------------------------------------
    async def async_load(self) -> None:
        data = await self._store.async_load() or {}
        for raw in data.get("groups", []):
            group = _load(Group, raw)
            self.groups[group.id] = group
        for raw in data.get("rows", []):
            row = _load(Row, raw)
            if row.group_id in self.groups:
                self.rows[row.id] = row
                self._by_group.setdefault(row.group_id, set()).add(row.id)
        self.prefix = {k: int(v) for k, v in data.get("prefix", {}).items()}

    def _data(self) -> dict[str, Any]:
        return {"groups": [asdict(g) for g in self.groups.values()],
                "rows": [asdict(r) for r in self.rows.values()], "prefix": self.prefix}

    async def async_flush(self) -> None:
        await self._store.async_save(self._data())

    # ---- intake ---------------------------------------------------------------------
    @callback
    def on_frame(self, frame: BusFrame) -> None:
        now = frame.time
        text = is_text(frame.data)
        if text:
            group_key = "text"
        else:
            n = self.prefix.get(frame.port_id, CATALOG_PREFIX)
            group_key = to_hex(frame.data[:n]) if n else "*"
        row_key = frame.data.hex()
        group_id = make_id(frame.port_id, group_key)
        group = self.groups.get(group_id)
        if group is None:
            group = self.groups[group_id] = Group(group_id, frame.port_id, group_key, order=-now, first_seen=now)
        group.count += 1
        group.last_seen = now
        self._count_rate(group_id, now)

        row_id = make_id(frame.port_id, group_key, row_key)
        row = self.rows.get(row_id)
        if row is None:
            row = self.rows[row_id] = Row(
                row_id, group_id, frame.port_id, to_hex(frame.data), len(frame.data),
                text=printable(frame.data) if text else None,
                checks=[] if text else checksum.detect(frame.data), first_seen=now)
            self._by_group.setdefault(group_id, set()).add(row_id)
            self._evict(group_id)
        row.count += 1
        row.last_seen = now
        self._touch(group_id, row_id)

    def _count_rate(self, group_id: str, now: float) -> None:
        window = self._rate.get(group_id)
        if window is None:
            self._rate[group_id] = [now, 1, 0.0]
            return
        window[1] += 1
        if now - window[0] >= 2.0:
            window[2] = window[1] / (now - window[0])
            window[0], window[1] = now, 0

    def _evict(self, group_id: str) -> None:
        """Keep the newest rows; named rows (an alias) are never evicted."""
        members = self._by_group[group_id]
        if len(members) > CATALOG_GROUP_ROWS:
            self._drop_oldest(members, len(members) - CATALOG_GROUP_ROWS)
        if len(self.rows) > CATALOG_TOTAL_ROWS:
            self._drop_oldest(set(self.rows), len(self.rows) - CATALOG_TOTAL_ROWS)

    def _drop_oldest(self, candidates: set[str], count: int) -> None:
        unnamed = sorted((r for r in (self.rows[i] for i in candidates) if not r.alias), key=lambda r: r.last_seen)
        for row in unnamed[:count]:
            self._remove_row(row.id)

    def _remove_row(self, row_id: str) -> None:
        row = self.rows.pop(row_id, None)
        if row is None:
            return
        self._by_group.get(row.group_id, set()).discard(row_id)
        self._dirty_rows.discard(row_id)
        self._removed.add(row_id)

    # ---- what the panel reads -------------------------------------------------------
    def group_dict(self, group: Group) -> dict[str, Any]:
        members = [self.rows[i] for i in self._by_group.get(group.id, ())]
        rate = self._rate.get(group.id)
        return {**asdict(group), "rows": len(members), "checksum": _consensus(members),
                "rate": round(rate[2], 2) if rate and time.time() - group.last_seen < 5 else 0.0}

    def snapshot(self) -> dict[str, Any]:
        return {"groups": [self.group_dict(g) for g in self.groups.values()],
                "rows": [asdict(r) for r in self.rows.values()], "prefix": self.prefix}

    # ---- edits from the panel -------------------------------------------------------
    def update_group(self, group_id: str, **changes: Any) -> None:
        group = self.groups[group_id]
        for key in ("alias", "hidden", "order"):
            if changes.get(key) is not None:
                setattr(group, key, changes[key])
        self._touch(group_id, None)

    def update_row(self, row_id: str, alias: str) -> None:
        row = self.rows[row_id]
        row.alias = alias
        self._touch(row.group_id, row_id)

    def delete_group(self, group_id: str) -> None:
        """Frames heard again come back as a new group; hiding is the way to keep one away."""
        for row_id in list(self._by_group.pop(group_id, ())):
            self._remove_row(row_id)
        self.groups.pop(group_id, None)
        self._rate.pop(group_id, None)
        self._dirty_groups.discard(group_id)
        self._removed.add(group_id)
        self._changed()

    def delete_row(self, row_id: str) -> None:
        row = self.rows.get(row_id)
        if row is not None:
            self._remove_row(row_id)
            self._touch(row.group_id, None)

    def clear(self, port_id: str | None = None) -> None:
        for group in list(self.groups.values()):
            if port_id is None or group.port_id == port_id:
                self.delete_group(group.id)

    def set_prefix(self, port_id: str, length: int) -> None:
        """New grouping for frames heard from now on; the port's old groups are cleared."""
        self.prefix[port_id] = length
        self.clear(port_id)

    # ---- pushes ---------------------------------------------------------------------
    @callback
    def subscribe(self, cb: Callable[[dict[str, Any]], None]) -> CALLBACK_TYPE:
        self._listeners.append(cb)
        return lambda: self._listeners.remove(cb)

    def _touch(self, group_id: str, row_id: str | None) -> None:
        self._dirty_groups.add(group_id)
        if row_id is not None:
            self._dirty_rows.add(row_id)
        self._changed()

    def _changed(self) -> None:
        self._store.async_delay_save(self._data, SAVE_DELAY)
        if self._listeners and self._push_handle is None:
            self._push_handle = self.hass.loop.call_later(LIVE_PUSH, self._push)

    @callback
    def _push(self) -> None:
        self._push_handle = None
        payload = {
            "groups": [self.group_dict(self.groups[i]) for i in self._dirty_groups if i in self.groups],
            "rows": [asdict(self.rows[i]) for i in self._dirty_rows if i in self.rows],
            "removed": sorted(self._removed),
        }
        self._dirty_groups.clear()
        self._dirty_rows.clear()
        self._removed.clear()
        for cb in list(self._listeners):
            cb(payload)


def _consensus(rows: list[Row]) -> str | None:
    """The checksum a group's frames agree on.

    A 16-bit check needs half the frames behind it; an 8-bit one needs at least three frames
    and nearly all of them, because single frames match 8-bit checks by accident.
    """
    votes = Counter(label for r in rows for label in r.checks)
    for label, count in votes.most_common():
        if checksum.is_wide(label) and count >= 0.5 * len(rows):
            return label
        if count >= 3 and count >= 0.9 * len(rows):
            return label
    return None
