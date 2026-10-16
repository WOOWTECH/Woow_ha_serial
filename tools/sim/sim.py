"""Run simulated equipment on one line, for the WOOW Serial test matrix (stdlib only).

Transports:
  --transport uart  --port /dev/ttySC0 --baud 9600     an on-board UART, opened directly (run it inside the
                                                       Core container while that port's WOOW Serial entry
                                                       is disabled: the port is opened exclusively)
  --transport wf485 --tag f507a4                       an HA-WF485-V3 through Home Assistant (run in the SSH
                                                       add-on): frames come from its uart_net_hex sensor and
                                                       go out through its hex_data_tx text entity

Models: --model NAME=TYPE[:key=value,key=value]  (types in protocols.MODELS), as many as share the line.

Control: one JSON object per line on stdin, one answer per line on stdout:
  {"op": "state"} | {"op": "log", "clear": true} | {"op": "set", "model": m, "values": {...}}
  {"op": "event", "model": m, "name": "press", "args": {...}} | {"op": "raw", "hex": "..."} | {"op": "quit"}
"""

from __future__ import annotations

import argparse
import heapq
import json
import os
import select
import sys
import threading
import time
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from protocols import MODELS, Model, split_frames  # noqa: E402

LOG_MAX = 500


def _hex(data: bytes) -> str:
    return data.hex(" ").upper()


class Uart:
    """Raw termios port; a frame ends after an idle gap (as WOOW Serial splits them)."""

    def __init__(self, path: str, baud: int, bytesize: int = 8, parity: str = "N", stopbits: int = 1,
                 gap_ms: int = 0) -> None:
        import fcntl
        import termios

        self.termios = termios
        self.fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        fcntl.ioctl(self.fd, termios.TIOCEXCL)
        attrs = termios.tcgetattr(self.fd)
        sizes = {5: termios.CS5, 6: termios.CS6, 7: termios.CS7, 8: termios.CS8}
        cflag = termios.CREAD | termios.CLOCAL | sizes[bytesize]
        if parity != "N":
            cflag |= termios.PARENB | (termios.PARODD if parity == "O" else 0)
        if stopbits == 2:
            cflag |= termios.CSTOPB
        speed = getattr(termios, f"B{baud}")
        attrs[0], attrs[1], attrs[2], attrs[3] = 0, 0, cflag, 0
        attrs[4] = attrs[5] = speed
        attrs[6][termios.VMIN] = 0
        attrs[6][termios.VTIME] = 0
        termios.tcsetattr(self.fd, termios.TCSANOW, attrs)
        termios.tcflush(self.fd, termios.TCIOFLUSH)
        bits = 1 + bytesize + (parity != "N") + stopbits
        self.gap = gap_ms / 1000 if gap_ms else max(0.02, 24 * bits / baud)
        self.spacing = self.gap
        self._sent: list[tuple[float, bytes]] = []  # what we wrote, to drop a transceiver's echo of it

    def read_frames(self, on_frame) -> None:
        buf = b""
        while True:
            ready, _, _ = select.select([self.fd], [], [], self.gap if buf else 1.0)
            if ready:
                try:
                    chunk = os.read(self.fd, 4096)
                except BlockingIOError:
                    chunk = b""
                buf += chunk
                continue
            if buf:
                frame, buf = self._drop_echo(buf), b""
                if frame:
                    on_frame(frame)

    def _drop_echo(self, frame: bytes) -> bytes:
        now = time.monotonic()
        self._sent = [(t, d) for t, d in self._sent if now - t < 1.0]
        for t, data in self._sent:
            if frame.startswith(data):
                self._sent.remove((t, data))
                return frame[len(data):]
        return frame

    def write(self, data: bytes) -> None:
        self._sent.append((time.monotonic(), data))
        view = memoryview(data)
        while view:
            try:
                n = os.write(self.fd, view)
            except BlockingIOError:
                select.select([], [self.fd], [], 1.0)
                continue
            view = view[n:]
        self.termios.tcdrain(self.fd)


class Wf485:
    """An HA-WF485-V3 driven through Home Assistant's websocket API (frames are its sensor's states)."""

    IDLE = {"", "idle", "unknown", "unavailable"}

    def __init__(self, tag: str) -> None:
        here = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, os.path.dirname(here))
        from wsclient import WS  # noqa: PLC0415

        self.rx = f"sensor.ha_wf485_v3_{tag}_uart_net_hex"
        self.tx = f"text.ha_wf485_v3_{tag}_hex_data_tx"
        self.ws = WS()
        self.ws.id += 1
        self.ws.send({"id": self.ws.id, "type": "subscribe_events", "event_type": "state_changed"})
        self.spacing = 0.12  # the board needs a pause between frames or it joins them
        self._lock = threading.Lock()

    def read_frames(self, on_frame) -> None:
        while True:
            msg = self.ws.recv()
            if msg.get("type") != "event":
                continue
            data = msg["event"].get("data", {})
            if data.get("entity_id") != self.rx or not data.get("new_state"):
                continue
            value = data["new_state"]["state"]
            if value.strip().lower() in self.IDLE:
                continue
            try:
                on_frame(bytes.fromhex(value.replace(" ", "")))
            except ValueError:
                print(f"not HEX from {self.rx}: {value!r}", file=sys.stderr)

    def write(self, data: bytes) -> None:
        with self._lock:
            self.ws.id += 1
            self.ws.send({"id": self.ws.id, "type": "call_service", "domain": "text", "service": "set_value",
                          "service_data": {"entity_id": self.tx, "value": _hex(data)}})


class Simulator:
    def __init__(self, transport: Any, models: list[Model]) -> None:
        self.transport = transport
        self.models = {m.name: m for m in models}
        self.split = any(m.kind == "binary" for m in models)  # text models find their own line ends
        self.rx: list[tuple[float, str]] = []
        self.tx: list[tuple[float, str]] = []
        self._queue: list[tuple[float, int, bytes]] = []
        self._seq = 0
        self._cv = threading.Condition()
        self._t0 = time.monotonic()

    def start(self) -> None:
        threading.Thread(target=self.transport.read_frames, args=(self.on_frame,), daemon=True).start()
        threading.Thread(target=self._writer, daemon=True).start()

    def _log(self, log: list, data: bytes) -> None:
        log.append((round(time.monotonic() - self._t0, 3), _hex(data)))
        del log[:-LOG_MAX]

    def on_frame(self, data: bytes) -> None:
        self._log(self.rx, data)
        for frame in split_frames(data) if self.split else [data]:
            for model in self.models.values():
                try:
                    self.schedule(model.handle(frame))
                except Exception as err:  # noqa: BLE001  (a model bug must not stop the line)
                    print(f"{model.name}: {err!r}", file=sys.stderr)

    def schedule(self, replies: list[tuple[float, bytes]]) -> None:
        with self._cv:
            for delay, data in replies:
                self._seq += 1
                heapq.heappush(self._queue, (time.monotonic() + delay, self._seq, data))
            self._cv.notify()

    def _writer(self) -> None:
        last = 0.0
        while True:
            with self._cv:
                while not self._queue or self._queue[0][0] > time.monotonic():
                    self._cv.wait(None if not self._queue else max(0.0, self._queue[0][0] - time.monotonic()))
                _, _, data = heapq.heappop(self._queue)
            pause = last + self.transport.spacing - time.monotonic()
            if pause > 0:
                time.sleep(pause)
            self.transport.write(data)
            last = time.monotonic()
            self._log(self.tx, data)

    def control(self, msg: dict[str, Any]) -> dict[str, Any]:
        op = msg.get("op")
        if op == "ping":
            return {"ok": True}
        if op == "state":
            return {"ok": True, "models": {n: {**m.state(), "heard": len(m.heard)} for n, m in self.models.items()}}
        if op == "log":
            out = {"ok": True, "rx": list(self.rx), "tx": list(self.tx),
                   "heard": {n: list(m.heard) for n, m in self.models.items()}}
            if msg.get("clear"):
                self.rx.clear()
                self.tx.clear()
                for model in self.models.values():
                    model.heard.clear()
            return out
        if op == "set":
            self.models[msg["model"]].set(**msg.get("values", {}))
            return {"ok": True, "state": self.models[msg["model"]].state()}
        if op == "event":
            frames = self.models[msg["model"]].event(msg["name"], **msg.get("args", {}))
            self.schedule(frames)
            return {"ok": True, "sent": [_hex(f) for _, f in frames]}
        if op == "raw":
            data = bytes.fromhex(msg["hex"].replace(" ", "")) if "hex" in msg else msg["text"].encode("latin-1")
            self.schedule([(0.0, data)])
            return {"ok": True}
        raise ValueError(f"unknown op {op!r}")


def parse_model(spec: str) -> Model:
    """NAME=TYPE[:key=value,key=value]"""
    name, _, rest = spec.partition("=")
    kind, _, args = rest.partition(":")
    cfg = dict(item.split("=", 1) for item in args.split(",") if item) if args else {}
    return MODELS[kind](name, **cfg)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transport", choices=("uart", "wf485"), required=True)
    parser.add_argument("--port")
    parser.add_argument("--baud", type=int, default=9600)
    parser.add_argument("--bytesize", type=int, default=8)
    parser.add_argument("--parity", default="N")
    parser.add_argument("--stopbits", type=int, default=1)
    parser.add_argument("--gap-ms", type=int, default=0)
    parser.add_argument("--tag")
    parser.add_argument("--model", action="append", default=[])
    args = parser.parse_args()
    if args.transport == "uart":
        transport: Any = Uart(args.port, args.baud, args.bytesize, args.parity, args.stopbits, args.gap_ms)
    else:
        transport = Wf485(args.tag)
    sim = Simulator(transport, [parse_model(m) for m in args.model])
    sim.start()
    print(json.dumps({"ok": True, "ready": True, "models": list(sim.models)}), flush=True)
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
            if msg.get("op") == "quit":
                print(json.dumps({"ok": True}), flush=True)
                break
            answer = sim.control(msg)
        except Exception as err:  # noqa: BLE001
            answer = {"ok": False, "error": repr(err)}
        print(json.dumps(answer, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
