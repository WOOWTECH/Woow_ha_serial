"""Tiny Home Assistant websocket + REST client for test scripts run in the SSH add-on (stdlib only).

Talks to Core through the Supervisor proxy with $SUPERVISOR_TOKEN, so it needs no user token.
"""

import base64
import json
import os
import socket
import struct
import threading
import urllib.request

TOKEN = os.environ["SUPERVISOR_TOKEN"]


class WS:
    def __init__(self):
        self.sock = socket.create_connection(("supervisor", 80), timeout=300)
        self._send_lock = threading.Lock()  # a reader thread answers pings while another thread sends
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall(f"GET /core/websocket HTTP/1.1\r\nHost: supervisor\r\nUpgrade: websocket\r\n"
                          f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n".encode())
        self.buf = b""
        while b"\r\n\r\n" not in self.buf:
            self.buf += self.sock.recv(4096)
        head, self.buf = self.buf.split(b"\r\n\r\n", 1)
        assert b" 101 " in head.split(b"\r\n")[0], head
        assert self.recv()["type"] == "auth_required"
        self.send({"type": "auth", "access_token": TOKEN})
        assert self.recv()["type"] == "auth_ok"
        self.id = 0
        self.pending = []  # messages that arrived while waiting for a result

    def read(self, n):
        while len(self.buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise EOFError
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def recv(self):
        msg = b""
        while True:
            b1, b2 = self.read(2)
            n = b2 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self.read(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self.read(8))[0]
            payload = self.read(n)
            if (b1 & 0x0F) == 9:  # ping: answer it, or Home Assistant drops the connection after ~1 min
                self._frame(0x8A, payload)
                continue
            if (b1 & 0x0F) == 10:  # pong
                continue
            msg += payload
            if b1 & 0x80:
                return json.loads(msg)

    def send(self, obj):
        self._frame(0x81, json.dumps(obj).encode())

    def _frame(self, first, data):
        mask = os.urandom(4)
        head = bytearray([first])
        if len(data) < 126:
            head.append(0x80 | len(data))
        elif len(data) < 65536:
            head.append(0x80 | 126)
            head += struct.pack(">H", len(data))
        else:
            head.append(0x80 | 127)
            head += struct.pack(">Q", len(data))
        with self._send_lock:
            self.sock.sendall(bytes(head) + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def call(self, msg_type, **kwargs):
        """Send one command and return its result ({"__error__": ...} on failure)."""
        self.id += 1
        self.send({"id": self.id, "type": msg_type, **kwargs})
        while True:
            reply = self.recv()
            if reply.get("id") == self.id and reply.get("type") == "result":
                return reply["result"] if reply.get("success") else {"__error__": reply.get("error")}
            self.pending.append(reply)


def rest(method, path, body=None):
    req = urllib.request.Request(
        "http://supervisor/core/api" + path, method=method,
        headers={"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"},
        data=None if body is None else json.dumps(body).encode())
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read() or b"null")
