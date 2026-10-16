"""Live test matrix: WOOW Serial against simulated equipment over the real RS485 / RS232 loops.

Run in the SSH add-on (Home Assistant OS) on a test system wired as:
  RS485-1 (/dev/ttySC0) <-> HA-WF485-V3 f507a4      RS232 (/dev/ttyAMA0) <-> HA-WF485-V3 847767
Each loop is tested both ways: the on-board port controls while the WF485 plays the equipment, then the
WF485 controls while the simulator opens the on-board UART itself (its WOOW Serial entry is disabled for
that, and enabled again afterwards). Devices are made the way an AI agent makes them — create_from_template
and save_device, by name, with notes — and operated through Home Assistant entities and services.

  python3 matrix.py [rs485_local rs485_external rs232_local rs232_external] [--restart]

Everything it creates is named "矩陣測試 …" and deleted at the end of each scenario.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
import traceback
from typing import Any, Callable
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from wsclient import TOKEN, WS  # noqa: E402

API = "http://supervisor/core/api"
PREFIX = "矩陣測試"
NOTE = "測試矩陣自動建立"
CORE = "homeassistant"


# ---- Home Assistant ---------------------------------------------------------------------------
def rest(method: str, path: str, data: Any = None) -> tuple[int, Any]:
    req = urllib.request.Request(API + path, method=method, data=None if data is None else json.dumps(data).encode(),
                                 headers={"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read()
            return r.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode()[:400]


def woow(service: str, data: dict | None = None) -> Any:
    status, body = rest("POST", f"/services/woow_serial/{service}?return_response", data or {})
    if status != 200:
        raise RuntimeError(f"woow_serial.{service}: HTTP {status} {body}")
    return body["service_response"]


def ha(domain: str, service: str, data: dict) -> None:
    status, body = rest("POST", f"/services/{domain}/{service}", data)
    if status != 200:
        raise RuntimeError(f"{domain}.{service}: HTTP {status} {body}")


def state(entity_id: str) -> dict:
    status, body = rest("GET", f"/states/{entity_id}")
    return body if status == 200 else {}


def attr(entity_id: str, name: str) -> Any:
    return state(entity_id).get("attributes", {}).get(name)


def until(probe: Callable[[], Any], timeout: float = 10, interval: float = 0.25) -> tuple[bool, Any]:
    end = time.monotonic() + timeout
    value = None
    while True:
        try:
            value = probe()
        except Exception as err:  # noqa: BLE001
            value = f"error: {err!r}"
        if value is True or (value and not isinstance(value, str)):
            return True, value
        if time.monotonic() > end:
            return False, value
        time.sleep(interval)


class Events(threading.Thread):
    """woow_serial_button events as they arrive."""

    def __init__(self) -> None:
        super().__init__(daemon=True)
        self.ws = WS()
        self.ws.id += 1
        self.ws.send({"id": self.ws.id, "type": "subscribe_events", "event_type": "woow_serial_button"})
        self.items: list[dict] = []

    def run(self) -> None:
        try:
            while True:
                msg = self.ws.recv()
                if msg.get("type") == "event":
                    self.items.append(msg["event"]["data"])
        except Exception:  # noqa: BLE001  (Home Assistant restarting)
            return

    def take(self) -> list[dict]:
        items, self.items = self.items, []
        return items


# ---- simulators -------------------------------------------------------------------------------
class Sim:
    def __init__(self, label: str, command: list[str]) -> None:
        self.label = label
        self.err = open(f"/tmp/sim_{label}.err", "w")  # noqa: SIM115
        self.proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.err,
                                     text=True, bufsize=1)
        ready = self.proc.stdout.readline()
        if not ready:
            raise RuntimeError(f"simulator {label} did not start: {open(self.err.name).read()[-600:]}")
        self.ready = json.loads(ready)

    def __call__(self, op: str, **kwargs: Any) -> dict:
        self.proc.stdin.write(json.dumps({"op": op, **kwargs}) + "\n")
        self.proc.stdin.flush()
        answer = json.loads(self.proc.stdout.readline())
        if not answer.get("ok"):
            raise RuntimeError(f"simulator {self.label}: {answer}")
        return answer

    def model(self, name: str) -> dict:
        return self("state")["models"][name]

    def heard(self, name: str, clear: bool = False) -> list[str]:
        return self("log", clear=clear)["heard"][name]

    def close(self) -> None:
        if self.err.closed:
            return  # already closed (before a restart, then again on the way out)
        try:
            self("quit")
            self.proc.wait(5)
        except Exception:  # noqa: BLE001
            self.proc.kill()
        for pipe in (self.proc.stdin, self.proc.stdout):
            try:
                pipe.close()
            except OSError:
                pass
        self.err.close()


def install_in_core() -> None:
    """The UART simulator runs inside the Core container, which owns the serial devices."""
    tar = subprocess.run(["tar", "-czf", "-", "-C", HERE, "protocols.py", "sim.py"], capture_output=True, check=True).stdout
    subprocess.run(["docker", "exec", "-i", CORE, "sh", "-c", "rm -rf /tmp/sim && mkdir -p /tmp/sim && tar -xz -C /tmp/sim"],
                   input=tar, check=True)


def uart_sim(label: str, path: str, models: list[str]) -> Sim:
    command = ["docker", "exec", "-i", CORE, "python3", "-u", "/tmp/sim/sim.py", "--transport", "uart", "--port", path,
               "--baud", "9600"]
    return Sim(label, command + [a for m in models for a in ("--model", m)])


def wf485_sim(label: str, tag: str, models: list[str]) -> Sim:
    command = [sys.executable, "-u", os.path.join(HERE, "sim.py"), "--transport", "wf485", "--tag", tag]
    return Sim(label, command + [a for m in models for a in ("--model", m)])


def set_entry(entry_id: str, enabled: bool) -> None:
    ws = WS()
    result = ws.call("config_entries/disable", entry_id=entry_id, disabled_by=None if enabled else "user")
    if isinstance(result, dict) and "__error__" in result:
        raise RuntimeError(f"config_entries/disable: {result}")
    ws.sock.close()


def ensure_enabled() -> None:
    """Safety net: no WOOW Serial entry stays disabled after the matrix, whatever happened."""
    for _ in range(3):
        try:
            ws = WS()
            for entry in ws.call("config_entries/get", domain="woow_serial"):
                if entry.get("disabled_by"):
                    print(f"re-enabling {entry['title']}", flush=True)
                    ws.call("config_entries/disable", entry_id=entry["entry_id"], disabled_by=None)
            ws.sock.close()
            return
        except Exception as err:  # noqa: BLE001
            print(f"ensure_enabled: {err!r}", flush=True)
            time.sleep(5)


# ---- report -----------------------------------------------------------------------------------
class Report:
    def __init__(self) -> None:
        self.rows: list[dict] = []
        self.scenario = ""

    def check(self, name: str, ok: bool, detail: Any = "") -> bool:
        self.rows.append({"scenario": self.scenario, "check": name, "ok": bool(ok), "detail": str(detail)[:300]})
        print(f"{'PASS' if ok else 'FAIL'}  [{self.scenario}] {name}  {str(detail)[:200]}", flush=True)
        return bool(ok)

    def run(self, name: str, fn: Callable[[], Any]) -> None:
        """A step that raises is a failed check, and the matrix goes on."""
        try:
            fn()
        except Exception as err:  # noqa: BLE001
            self.check(name, False, f"{err!r} {traceback.format_exc(limit=2)[-300:]}")


R = Report()


# ---- devices made like an agent makes them ----------------------------------------------------
def entity(device: dict, domain: str) -> str:
    return next(e for e in device["entities"] if e.startswith(domain + "."))


def create(template: str, port: str, name: str, params: dict | None = None) -> dict:
    answer = woow("create_from_template", {"template": template, "port": port, "name": name, "params": params or {},
                                           "note": NOTE})
    if not answer.get("ok"):
        raise RuntimeError(f"create_from_template {template}: {answer}")
    answer["device"]["port_settings"] = answer.get("port_settings")
    return answer["device"]


def save(device: dict) -> dict:
    answer = woow("save_device", {"device": device, "note": NOTE})
    if not answer.get("ok"):
        raise RuntimeError(f"save_device {device['name']}: {answer}")
    return answer["device"]


def device_state(name: str) -> dict:
    return woow("get_device", {"device": name})["device"]["state"]


def cleanup() -> int:
    removed = 0
    for device in woow("list_devices")["devices"]:
        if device["name"].startswith(PREFIX):
            woow("delete_device", {"device": device["name"], "note": "測試矩陣清理"})
            removed += 1
    return removed


def run_command(device: str, command: str, value: float | None = None) -> dict:
    data = {"device": device, "command": command, "note": NOTE}
    if value is not None:
        data["value"] = value
    return woow("run_command", data)


# ---- RS485 ------------------------------------------------------------------------------------
RS485_MODELS = [
    "dooya=dooya:addr=0A0B,travel_s=4,position=0",
    "aok=aok:id=05,ch=0100,travel_s=4,position=100",
    "relay=waveshare_relay:addr=03",
    "th=xymd02:addr=04,temperature=23.4,humidity=56.7",
    "dimmer=modbus_dimmer:addr=06",
    "keypad=keypad:addr=10",
]


def slow_equipment(names: list[str], wait_ms: int = 1500) -> None:
    """Equipment that answers slowly: give its answered commands a longer wait, as an agent would
    after seeing late answers (and the edit path through save_device gets used)."""
    for name in names:
        device = woow("get_device", {"device": name})["device"]
        for command in device["commands"]:
            if command["wait_ms"]:
                command["wait_ms"] = max(command["wait_ms"], wait_ms)
        save({k: v for k, v in device.items() if k not in ("state", "entities", "port")})


def rs485(port: str, sim: Sim, events: Events, slow: bool = False) -> None:
    dooya = create("dooya_rs485_curtain", port, f"{PREFIX} 杜亞窗簾", {"addr": "0A 0B"})
    aok = create("aok_rs485_curtain", port, f"{PREFIX} A-OK 窗簾", {"id": "05", "ch": "01 00"})
    relay1 = create("waveshare_modbus_relay", port, f"{PREFIX} 繼電器1", {"addr": "03", "coil": "00 00"})
    relay2 = create("waveshare_modbus_relay", port, f"{PREFIX} 繼電器2", {"addr": "03", "coil": "00 01"})
    create("xymd02_modbus_th", port, f"{PREFIX} 溫濕度", {"addr": "04"})
    expects = aok["port_settings"]["template_expects"].get("baudrate")
    R.check("template reports the line speed it expects", expects == 2400, aok["port_settings"])
    dimmer = save({
        "name": f"{PREFIX} 調光燈", "type": "light", "port": port, "params": {"addr": "06"},
        "commands": [
            # wait_ms: the dimmer answers every request; hold the line until it has (half duplex)
            {"name": "亮度", "payload": "{addr} 06 00 00 {value:u16} {crc16_modbus}", "wait_ms": 500},
            {"name": "開", "payload": "{addr} 06 00 01 00 01 {crc16_modbus}", "wait_ms": 500},
            {"name": "關", "payload": "{addr} 06 00 01 00 00 {crc16_modbus}", "wait_ms": 500},
            {"name": "讀取", "payload": "{addr} 03 00 00 00 02 {crc16_modbus}", "wait_ms": 500},
            # 0.5 s apart: a WF485 shows the same frame again only after its sensor went back to IDLE.
            # The dimmer answers every repeat, so the last one waits too: otherwise the next request can
            # collide with that answer on the half-duplex line (seen in the matrix, 2026-10-16).
            {"name": "閃三下", "payload": "{addr} 06 00 01 00 01 {crc16_modbus}", "repeat": 3, "gap_ms": 500,
             "wait_ms": 500},
        ],
        "actions": {"turn_on": "開", "turn_off": "關", "set_brightness": "亮度"},
        "rules": [
            {"pattern": "{addr} 06 00 00 {lv:u16} {crc16_modbus}", "field": "brightness", "value": "{lv}"},
            {"pattern": "{addr} 06 00 01 00 01 {crc16_modbus}", "field": "power", "value": "on"},
            {"pattern": "{addr} 06 00 01 00 00 {crc16_modbus}", "field": "power", "value": "off"},
            {"pattern": "{addr} 03 04 {lv:u16} {on:u16} {crc16_modbus}", "field": "brightness", "value": "{lv}",
             "reply_to": "讀取"},
            {"pattern": "{addr} 03 04 {lv:u16} {on:u16} {crc16_modbus}", "field": "power", "value": "{on}",
             "reply_to": "讀取"},
        ],
        "ranges": {"brightness": [0, 100]},
    })
    keypad = save({
        "name": f"{PREFIX} 面板", "type": "keypad", "port": port, "params": {"addr": "10"},
        # 800 ms: a WF485 in between stretches the gaps of a key's repeated frames past the default 300 ms
        "buttons": [
            {"name": "情境1", "pattern": "A5 5A {addr} 01 {sum8}", "target": f"{PREFIX} 繼電器1", "action": "toggle",
             "debounce_ms": 800},
            {"name": "情境2", "pattern": "A5 5A {addr} 02 {sum8}", "target": f"{PREFIX} 杜亞窗簾",
             "action": "set_position", "value": 50, "debounce_ms": 800},
            {"name": "情境3", "pattern": "A5 5A {addr} 03 {sum8}", "debounce_ms": 800},
        ],
    })
    R.check("devices created by name (templates and save_device)", len(keypad["buttons"]) == 3 and dimmer["entities"])
    if slow:  # the WF485 plays the equipment: its answers come back 0.3–0.7 s late
        slow_equipment([f"{PREFIX} {n}" for n in ("杜亞窗簾", "A-OK 窗簾", "繼電器1", "繼電器2", "溫濕度", "調光燈")])
        R.check("slow equipment: waits raised with save_device",
                all(c["wait_ms"] >= 1500 for c in woow("get_device", {"device": f"{PREFIX} 杜亞窗簾"})["device"]["commands"]))
    cover, aok_cover = entity(dooya, "cover"), entity(aok, "cover")
    sw1, sw2, light = entity(relay1, "switch"), entity(relay2, "switch"), entity(dimmer, "light")
    sim("log", clear=True)

    def dooya_open() -> None:
        ha("cover", "open_cover", {"entity_id": cover})
        ok, heard = until(lambda: sim.heard("dooya")[:1], 3)
        R.check("Dooya: open frame on the wire", ok and heard[0] == "55 0A 0B 03 01 9B 26", heard)
        R.check("Dooya: motor opens", until(lambda: sim.model("dooya")["position"] == 100, 8)[0], sim.model("dooya"))
        ok, pos = until(lambda: attr(cover, "current_position") == 100 and 100, 16)
        R.check("Dooya: position read back (follow-up read + polling)", ok, attr(cover, "current_position"))

    def dooya_position() -> None:
        ha("cover", "set_cover_position", {"entity_id": cover, "position": 30})
        R.check("Dooya: goes to 30 %", until(lambda: sim.model("dooya")["position"] == 30, 8)[0], sim.model("dooya"))
        R.check("Dooya: 30 % read back", until(lambda: attr(cover, "current_position") == 30, 16)[0],
                attr(cover, "current_position"))

    def dooya_stop() -> None:
        ha("cover", "open_cover", {"entity_id": cover})
        time.sleep(1.2)
        ha("cover", "stop_cover", {"entity_id": cover})
        time.sleep(0.5)
        stopped = sim.model("dooya")
        R.check("Dooya: stops midway", stopped["moving"] == 0 and 35 < stopped["position"] < 95, stopped)
        target = round(stopped["position"])
        R.check("Dooya: stopped position read back",
                until(lambda: abs((attr(cover, "current_position") or -9) - target) <= 1, 6)[0],
                (attr(cover, "current_position"), target))

    def dooya_faults() -> None:
        before = attr(cover, "current_position")
        sim("set", model="dooya", values={"calibrated": False})
        run_command(f"{PREFIX} 杜亞窗簾", "讀取位置")
        time.sleep(2)
        R.check("Dooya: FF (limits not set) is not taken as a position", attr(cover, "current_position") == before,
                (before, attr(cover, "current_position")))
        sim("set", model="dooya", values={"calibrated": True})
        sim("raw", hex="55 0A 0B 01 01 05 00 00")  # a position answer with a broken CRC
        time.sleep(2)
        R.check("Dooya: frame with a bad CRC ignored", attr(cover, "current_position") == before,
                attr(cover, "current_position"))

    def aok_moves() -> None:
        sim("log", clear=True)
        ha("cover", "open_cover", {"entity_id": aok_cover})
        ok, heard = until(lambda: "9A 05 01 00 0A DD D3" in sim.heard("aok"), 3)
        R.check("A-OK: open frame on the wire", ok, sim.heard("aok"))
        R.check("A-OK: motor opens (its 0 = open)", until(lambda: sim.model("aok")["position"] == 0, 8)[0],
                sim.model("aok"))
        R.check("A-OK: reversed position read back as 100 %",
                until(lambda: attr(aok_cover, "current_position") == 100, 16)[0], attr(aok_cover, "current_position"))
        ha("cover", "set_cover_position", {"entity_id": aok_cover, "position": 25})
        R.check("A-OK: 25 % open is motor position 75", until(lambda: sim.model("aok")["position"] == 75, 8)[0],
                sim.model("aok"))
        R.check("A-OK: 25 % read back", until(lambda: attr(aok_cover, "current_position") == 25, 16)[0],
                attr(aok_cover, "current_position"))

    def relays() -> None:
        ha("switch", "turn_on", {"entity_id": sw1})
        R.check("relay: channel 1 on (FC05 FF00)", until(lambda: sim.model("relay")["coils"][0] is True, 4)[0],
                sim.model("relay")["coils"][:2])
        R.check("relay: confirmed by the board's echo", until(lambda: state(sw1).get("state") == "on", 4)[0],
                state(sw1).get("state"))
        R.check("relay: channel 2 not changed by channel 1's echo", state(sw2).get("state") != "on", state(sw2).get("state"))
        sim("set", model="relay", values={"coil1": True})  # someone switched channel 2 at the board
        run_command(f"{PREFIX} 繼電器2", "讀取狀態")
        R.check("relay: channel 2 reads its own coil (reply_to)", until(lambda: state(sw2).get("state") == "on", 4)[0],
                state(sw2).get("state"))
        run_command(f"{PREFIX} 繼電器1", "讀取狀態")
        time.sleep(1.5)
        R.check("relay: channel 1 still on after its own read", state(sw1).get("state") == "on", state(sw1).get("state"))
        run_command(f"{PREFIX} 繼電器2", "翻轉（重送會再翻回來）")
        R.check("relay: flip (5500) toggles the coil", until(lambda: sim.model("relay")["coils"][1] is False, 4)[0],
                sim.model("relay")["coils"][:2])
        ha("switch", "turn_off", {"entity_id": sw1})
        R.check("relay: channel 1 off", until(lambda: state(sw1).get("state") == "off", 4)[0], state(sw1).get("state"))

    def sensor() -> None:
        run_command(f"{PREFIX} 溫濕度", "讀取")
        ok, st = until(lambda: (s := device_state(f"{PREFIX} 溫濕度")).get("sensor:temperature") == 23.4 and s, 5)
        R.check("XY-MD02: 23.4 °C / 56.7 %", ok and st.get("sensor:humidity") == 56.7, st)
        sim("set", model="th", values={"temperature": -5.5})
        run_command(f"{PREFIX} 溫濕度", "讀取")
        R.check("XY-MD02: negative temperature (signed register)",
                until(lambda: device_state(f"{PREFIX} 溫濕度").get("sensor:temperature") == -5.5, 5)[0],
                device_state(f"{PREFIX} 溫濕度"))

    def dimmer_light() -> None:
        ha("light", "turn_on", {"entity_id": light})
        R.check("dimmer: turned on", until(lambda: sim.model("dimmer")["on"] and state(light).get("state") == "on", 5)[0],
                (sim.model("dimmer"), state(light).get("state")))
        ha("light", "turn_on", {"entity_id": light, "brightness": 128})
        R.check("dimmer: brightness 128 is level 50", until(lambda: sim.model("dimmer")["level"] == 50, 4)[0],
                sim.model("dimmer"))
        R.check("dimmer: brightness confirmed", until(lambda: attr(light, "brightness") == 128, 4)[0],
                attr(light, "brightness"))
        sim("set", model="dimmer", values={"level": 20})  # changed at the dimmer itself
        run_command(f"{PREFIX} 調光燈", "讀取")
        R.check("dimmer: read back (two registers in one answer)", until(lambda: attr(light, "brightness") == 51, 4)[0],
                attr(light, "brightness"))
        ha("light", "turn_off", {"entity_id": light})
        R.check("dimmer: turned off", until(lambda: state(light).get("state") == "off", 4)[0], state(light).get("state"))

    def repeat_and_burst() -> None:
        sim("log", clear=True)
        run_command(f"{PREFIX} 調光燈", "閃三下")
        ok, heard = until(lambda: len(sim.heard("dimmer")) >= 3 and sim.heard("dimmer"), 5)
        R.check("repeat 3 with a 500 ms gap: three frames", ok and len(set(heard)) == 1 and len(heard) == 3, heard)
        sim("log", clear=True)
        for level in (10, 20, 30, 40, 50):
            run_command(f"{PREFIX} 調光燈", "亮度", level)
        until(lambda: len(sim.heard("dimmer")) >= 5, 5)
        heard = sim.heard("dimmer")
        levels = [int(h.split()[4] + h.split()[5], 16) for h in heard if h.split()[1:4] == ["06", "00", "00"]]
        R.check("burst of 5 commands arrives complete and in order", levels == [10, 20, 30, 40, 50], (levels, heard))

    def wait_for_reply() -> None:
        frame = woow("preview_command", {"payload": "04 04 00 01 00 02 {crc16_modbus}"})["sent"]
        for level in (11, 22, 33):  # other traffic answered on the line meanwhile
            run_command(f"{PREFIX} 調光燈", "亮度", level)
        answer = woow("send", {"port": port, "hex": frame, "expect": "04 04 04 {t:s16} {h:u16} {crc16_modbus}",
                               "wait_ms": 3000, "note": NOTE})
        reply = answer.get("reply") or {}
        R.check("send + expect returns the answer it waits for, with captures and checksum",
                reply.get("hex", "").startswith("04 04 04") and "crc16_modbus" in reply.get("checks", [])
                and reply.get("captures") == {"t": -55, "h": 567},
                {k: answer.get(k) for k in ("reply", "elapsed_ms", "timeout")})

    def press(key: int, **args: Any) -> tuple[bool, list[dict], int]:
        """Press like a person: once more if nothing happened (an unsolicited frame can collide with a
        poll on a half-duplex bus)."""
        for attempt in (1, 2):
            events.take()
            sim("event", model="keypad", name="press", args={"key": key, **args})
            ok, _ = until(lambda: events.items[:], 3)
            if ok:
                time.sleep(1.5)  # let repeats and joined pieces arrive, then take everything at once
                return True, events.take(), attempt
            frames = woow("get_monitor", {"port": port, "limit": 3})["groups"]
            print(f"      no event for key {key}; recent frames: {[(g['key'], [f['hex'] for f in g['frames'][:2]]) for g in frames]}")
        return False, [], 2

    def keypad_presses() -> None:
        ok, got, attempt = press(3)
        R.check("keypad: press fires woow_serial_button", ok and got[0]["button"] == "情境3", (got[:1], f"attempt {attempt}"))
        time.sleep(1.0)
        ok, got, attempt = press(3, repeat=3, joined=True)
        R.check("keypad: a key sent 3 times back to back (one joined frame) counts once",
                ok and len(got) == 1, (len(got), f"attempt {attempt}"))
        time.sleep(1.0)
        ok, got, attempt = press(0, keys=[3, 1], joined=True)
        R.check("keypad: two keys in one joined frame are two presses",
                ok and sorted(e["button"] for e in got) == ["情境1", "情境3"], ([e["button"] for e in got], f"attempt {attempt}"))
        time.sleep(1.5)
        sim("event", model="keypad", name="press", args={"key": 1})  # undo the toggle of relay 1 above
        time.sleep(1.5)
        coil = sim.model("relay")["coils"][0]
        sim("event", model="keypad", name="press", args={"key": 1})
        R.check("keypad: binding toggles relay 1 by itself",
                until(lambda: sim.model("relay")["coils"][0] is (not coil), 4)[0], sim.model("relay")["coils"][:2])
        time.sleep(1.5)
        sim("event", model="keypad", name="press", args={"key": 1})
        R.check("keypad: pressed again, toggles back", until(lambda: sim.model("relay")["coils"][0] is coil, 4)[0],
                sim.model("relay")["coils"][:2])
        sim("event", model="keypad", name="press", args={"key": 2})
        R.check("keypad: binding sends the curtain to 50 %",
                until(lambda: abs(sim.model("dooya")["position"] - 50) < 1, 8)[0], sim.model("dooya"))

    def activity() -> None:
        entries = woow("get_activity", {"limit": 200})["activity"]
        notes = [e for e in entries if e["note"] == NOTE]
        kinds = {e["msg"] for e in notes}
        R.check("activity log keeps the agent's changes with its note",
                {"device_from_template", "device_created", "command_sent"} <= kinds, sorted(kinds))

    for name, step in (("Dooya open", dooya_open), ("Dooya position", dooya_position), ("Dooya stop", dooya_stop),
                       ("Dooya faults", dooya_faults), ("A-OK", aok_moves), ("relays", relays), ("XY-MD02", sensor),
                       ("dimmer", dimmer_light), ("repeat/burst", repeat_and_burst), ("wait_ms", wait_for_reply),
                       ("keypad", keypad_presses), ("activity", activity)):
        R.run(name, step)


# ---- RS232 ------------------------------------------------------------------------------------
def rs232(port: str, start_sim: Callable[[str], Sim]) -> None:
    def media(template: str, model: str, label: str, steps: Callable[[Sim, str, str], None], **params: str) -> None:
        sim = start_sim(model)
        try:
            device = create(template, port, f"{PREFIX} {label}", params)
            steps(sim, device["name"], entity(device, "media_player" if "matrix" not in template else "select"))
        finally:
            sim.close()
            cleanup()

    def epson(sim: Sim, name: str, mp: str) -> None:
        run_command(name, "查詢電源")
        R.check("Epson: standby read as off", until(lambda: state(mp).get("state") == "off", 5)[0], state(mp).get("state"))
        ha("media_player", "turn_on", {"entity_id": mp})
        R.check("Epson: PWR ON reaches the projector", until(lambda: sim.model("p")["power"] in ("02", "01"), 4)[0],
                sim.model("p"))
        R.check("Epson: warming up (02) shown as on", until(lambda: state(mp).get("state") == "on", 6)[0],
                state(mp).get("state"))
        until(lambda: sim.model("p")["power"] == "01", 6)
        ha("media_player", "select_source", {"entity_id": mp, "source": "HDMI 2"})
        R.check("Epson: source A0 set", until(lambda: sim.model("p")["source"] == "A0", 4)[0], sim.model("p"))
        R.check("Epson: source confirmed by the follow-up query",
                until(lambda: attr(mp, "source") == "HDMI 2", 8)[0], attr(mp, "source"))
        ha("media_player", "volume_mute", {"entity_id": mp, "is_volume_muted": True})
        R.check("Epson: A/V mute confirmed", until(lambda: attr(mp, "is_volume_muted") is True, 6)[0],
                attr(mp, "is_volume_muted"))
        ha("media_player", "turn_off", {"entity_id": mp})
        R.check("Epson: off (cooling down 03)", until(lambda: state(mp).get("state") == "off", 6)[0],
                (state(mp).get("state"), sim.model("p")))

    def benq(sim: Sim, name: str, mp: str) -> None:
        ha("media_player", "turn_on", {"entity_id": mp})
        R.check("BenQ: on", until(lambda: state(mp).get("state") == "on", 5)[0], (state(mp).get("state"), sim.model("p")))
        ha("media_player", "select_source", {"entity_id": mp, "source": "HDMI 2"})
        time.sleep(1.5)
        R.check("BenQ: refused while warming up (*Block item#) leaves the source alone",
                attr(mp, "source") != "HDMI 2" and sim.model("p")["source"] == "HDMI", (attr(mp, "source"), sim.model("p")))
        time.sleep(1.0)
        ha("media_player", "select_source", {"entity_id": mp, "source": "HDMI 2"})
        R.check("BenQ: source HDMI 2 confirmed", until(lambda: attr(mp, "source") == "HDMI 2", 5)[0],
                (attr(mp, "source"), sim.model("p")))
        ha("media_player", "turn_off", {"entity_id": mp})
        R.check("BenQ: off", until(lambda: state(mp).get("state") == "off", 5)[0], state(mp).get("state"))

    def denon(sim: Sim, name: str, mp: str) -> None:
        ha("media_player", "turn_on", {"entity_id": mp})
        R.check("Denon: on", until(lambda: state(mp).get("state") == "on", 5)[0], state(mp).get("state"))
        ha("media_player", "volume_set", {"entity_id": mp, "volume_level": 0.5})
        R.check("Denon: volume 50 % is MV40", until(lambda: sim.model("a")["volume"] == 40, 4)[0], sim.model("a"))
        R.check("Denon: volume confirmed", until(lambda: attr(mp, "volume_level") == 0.5, 4)[0], attr(mp, "volume_level"))
        sim("event", model="a", name="knob", args={"volume": 60})
        R.check("Denon: knob turned on the receiver is followed",
                until(lambda: attr(mp, "volume_level") == 0.75, 4)[0], attr(mp, "volume_level"))
        ha("media_player", "select_source", {"entity_id": mp, "source": "Blu-ray"})
        R.check("Denon: input BD", until(lambda: sim.model("a")["source"] == "BD", 4)[0], sim.model("a"))
        R.check("Denon: input confirmed", until(lambda: attr(mp, "source") == "Blu-ray", 4)[0], attr(mp, "source"))
        ha("media_player", "volume_mute", {"entity_id": mp, "is_volume_muted": True})
        R.check("Denon: mute confirmed", until(lambda: attr(mp, "is_volume_muted") is True, 4)[0],
                attr(mp, "is_volume_muted"))
        ha("media_player", "turn_off", {"entity_id": mp})
        R.check("Denon: standby", until(lambda: state(mp).get("state") == "off", 4)[0], state(mp).get("state"))

    def extron(sim: Sim, name: str, sel: str) -> None:
        ha("select", "select_option", {"entity_id": sel, "option": "輸入 3"})
        R.check("Extron: input 3 tied to output 2", until(lambda: sim.model("x")["ties"]["2"] == 3, 4)[0], sim.model("x"))
        R.check("Extron: tie confirmed", until(lambda: state(sel).get("state") == "輸入 3", 4)[0], state(sel).get("state"))

    def blackbird(sim: Sim, name: str, sel: str) -> None:
        ha("select", "select_option", {"entity_id": sel, "option": "輸入 2"})
        R.check("Blackbird: input 2 to output 1", until(lambda: sim.model("b")["ties"]["1"] == 2, 4)[0], sim.model("b"))
        R.check("Blackbird: confirmed", until(lambda: state(sel).get("state") == "輸入 2", 4)[0], state(sel).get("state"))
        sim("set", model="b", values={"ties": {"1": 4, "2": 2, "3": 3, "4": 4}})  # front panel
        run_command(name, "查詢輸出")
        R.check("Blackbird: a change made at the matrix shows after a query",
                until(lambda: state(sel).get("state") == "輸入 4", 4)[0], state(sel).get("state"))

    for template, model, label, steps, params in (
        ("epson_escvp21_projector", "p=epson:warmup_s=3,cooldown_s=2", "Epson 投影機", epson, {}),
        ("benq_rs232_projector", "p=benq:transition_s=2.5", "BenQ 投影機", benq, {}),
        ("denon_marantz_avr", "a=denon", "Denon 擴大機", denon, {}),
        ("extron_sis_matrix_output", "x=extron", "Extron 輸出2", extron, {"output": "2"}),
        ("blackbird_hdmi_matrix_output", "b=blackbird", "矩陣 輸出1", blackbird, {"output": "1"}),
    ):
        R.run(label, lambda: media(template, model, label, steps, **params))


# ---- scenarios --------------------------------------------------------------------------------
SCENARIOS = {
    # name: (bus, controller port, simulator side)
    "rs485_local": ("rs485", "RS485-1", ("wf485", "f507a4")),
    "rs485_external": ("rs485", "WF485 f507a4", ("uart", "/dev/ttySC0", "RS485-1")),
    "rs232_local": ("rs232", "RS232", ("wf485", "847767")),
    "rs232_external": ("rs232", "WF485 847767", ("uart", "/dev/ttyAMA0", "RS232")),
}


def restart_check(port: str) -> None:
    """Devices, their state and their behaviour survive a Home Assistant restart."""
    cover = entity(woow("get_device", {"device": f"{PREFIX} 杜亞窗簾"})["device"], "cover")
    before = attr(cover, "current_position")
    subprocess.run(["ha", "core", "restart"], check=True, capture_output=True)
    ok, _ = until(lambda: rest("GET", "/")[0] == 200, 180, 3)
    R.check("Home Assistant back after restart", ok)
    ok, _ = until(lambda: any(d["name"] == f"{PREFIX} 面板" for d in woow("list_devices")["devices"]), 60, 2)
    R.check("devices still there after restart", ok)
    R.check("cover position restored after restart", until(lambda: attr(cover, "current_position") == before, 30, 1)[0],
            (before, attr(cover, "current_position")))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("scenarios", nargs="*", default=list(SCENARIOS))
    parser.add_argument("--restart", action="store_true", help="also restart Home Assistant once (rs485_local)")
    args = parser.parse_args()
    install_in_core()
    ports = {p["name"]: p for p in woow("list_ports")["ports"]}
    entries = {p["name"]: p["id"] for p in ports.values()}
    started = time.monotonic()
    for name in args.scenarios:
        bus, controller, side = SCENARIOS[name]
        R.scenario = name
        print(f"\n=== {name}: {controller} controls, simulator on {side[1]}", flush=True)
        cleanup()
        disabled = None
        try:
            if side[0] == "uart":
                install_in_core()  # again: a Home Assistant restart empties the container's /tmp
                disabled = entries[side[2]]
                set_entry(disabled, False)
                time.sleep(3)

            def start(*models: str, label: str = name) -> Sim:
                if side[0] == "uart":
                    return uart_sim(label, side[1], list(models))
                return wf485_sim(label, side[1], list(models))

            R.check("controller port available", until(
                lambda: next((p["available"] for p in woow("list_ports")["ports"] if p["name"] == controller), False),
                20, 1)[0], controller)
            if bus == "rs485":
                events = Events()
                events.start()
                sim = start(*RS485_MODELS)
                try:
                    rs485(controller, sim, events, slow=side[0] == "wf485")
                    if args.restart and name == "rs485_local":
                        sim.close()
                        R.run("restart", lambda: restart_check(controller))
                finally:
                    try:
                        sim.close()
                    except Exception:  # noqa: BLE001
                        pass
            else:
                rs232(controller, lambda model: start(model))
        except Exception as err:  # noqa: BLE001
            R.check("scenario", False, f"{err!r} {traceback.format_exc(limit=3)[-400:]}")
        finally:
            removed = cleanup()
            print(f"cleaned up {removed} test devices", flush=True)
            if disabled:
                set_entry(disabled, True)
                until(lambda: next((p["available"] for p in woow("list_ports")["ports"] if p["id"] == disabled), False), 30, 1)
    ensure_enabled()
    passed = sum(r["ok"] for r in R.rows)
    print(f"\n{passed}/{len(R.rows)} checks passed in {round(time.monotonic() - started)} s", flush=True)
    for row in R.rows:
        if not row["ok"]:
            print(f"FAILED [{row['scenario']}] {row['check']}: {row['detail']}")
    with open("/tmp/matrix_result.json", "w") as fh:
        json.dump(R.rows, fh, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
