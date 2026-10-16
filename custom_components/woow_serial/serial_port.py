"""A raw serial port driven from the asyncio loop (stdlib termios, no extra packages)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import fcntl
import os
import struct
import termios
import time

from .const import MAX_FRAME

TIOCMBIS, TIOCMBIC, TIOCM_LOOP, TIOCGICOUNT = 0x5416, 0x5417, 0x8000, 0x545D
_SIZES = {5: termios.CS5, 6: termios.CS6, 7: termios.CS7, 8: termios.CS8}


@dataclass
class SerialConfig:
    """Line settings plus framing behaviour."""

    path: str
    baudrate: int = 9600
    bytesize: int = 8
    parity: str = "N"
    stopbits: int = 1
    frame_gap_ms: int = 0
    echo_filter: bool = False
    loop_flush: bool = False

    @property
    def char_bits(self) -> int:
        """Bits on the wire per character (start + data + parity + stop)."""
        return 1 + self.bytesize + (self.parity != "N") + self.stopbits

    @property
    def gap(self) -> float:
        """Idle time that ends a frame.

        UARTs hand data over in FIFO-sized batches (8 chars on the SC16IS752, 16 on the
        PL011, measured 2026-10-16), so the automatic gap is 24 character times, at least
        20 ms: 25 ms at 9600 baud.
        """
        if self.frame_gap_ms:
            return self.frame_gap_ms / 1000
        return max(0.02, 24 * self.char_bits / self.baudrate)


class SerialPort:
    """Reads frames (split on idle gaps) and writes bytes without blocking the loop."""

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        cfg: SerialConfig,
        on_frame: Callable[[bytes], None],
        on_tx: Callable[[bytes, str | None], None],
        on_lost: Callable[[Exception], None],
    ) -> None:
        self._loop = loop
        self.cfg = cfg
        self._on_frame = on_frame
        self._on_tx = on_tx
        self._on_lost = on_lost
        self._fd: int | None = None
        self._buf = bytearray()
        self._gap_timer: asyncio.TimerHandle | None = None
        self._echo = bytearray()
        self._echo_until = 0.0
        self._write_lock = asyncio.Lock()
        self._waiters: list[asyncio.Future[bytes]] = []
        self.rx_bytes = self.tx_bytes = self.rx_frames = self.tx_frames = 0

    @property
    def is_open(self) -> bool:
        return self._fd is not None

    # ---- open / close -------------------------------------------------------------
    def _open_blocking(self) -> int:
        cfg = self.cfg
        fd = os.open(cfg.path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        try:
            fcntl.ioctl(fd, termios.TIOCEXCL)
            attrs = termios.tcgetattr(fd)
            cflag = termios.CREAD | termios.CLOCAL | _SIZES[cfg.bytesize]
            if cfg.parity != "N":
                cflag |= termios.PARENB | (termios.PARODD if cfg.parity == "O" else 0)
            if cfg.stopbits == 2:
                cflag |= termios.CSTOPB
            speed = getattr(termios, f"B{cfg.baudrate}")
            attrs[0] = termios.INPCK if cfg.parity != "N" else 0
            attrs[1] = 0
            attrs[2] = cflag
            attrs[3] = 0
            attrs[4] = attrs[5] = speed
            attrs[6][termios.VMIN] = 0
            attrs[6][termios.VTIME] = 0
            termios.tcsetattr(fd, termios.TCSANOW, attrs)
            if cfg.loop_flush:
                _loop_flush(fd)
            termios.tcflush(fd, termios.TCIOFLUSH)
        except Exception:
            os.close(fd)
            raise
        return fd

    async def open(self) -> None:
        self._fd = await self._loop.run_in_executor(None, self._open_blocking)
        self._loop.add_reader(self._fd, self._readable)

    async def close(self) -> None:
        fd, self._fd = self._fd, None
        if self._gap_timer:
            self._gap_timer.cancel()
            self._gap_timer = None
        self._fail_waiters(OSError("serial port closed"))
        if fd is None:
            return
        self._loop.remove_reader(fd)
        self._loop.remove_writer(fd)
        await self._loop.run_in_executor(None, os.close, fd)

    def _lost(self, err: Exception) -> None:
        if self._fd is not None:
            self._loop.remove_reader(self._fd)
            os.close(self._fd)
            self._fd = None
        self._fail_waiters(err)
        self._on_lost(err)

    def _fail_waiters(self, err: Exception) -> None:
        for fut in self._waiters:
            if not fut.done():
                fut.set_exception(err)

    # ---- receive ------------------------------------------------------------------
    def _readable(self) -> None:
        try:
            data = os.read(self._fd, 4096)
        except BlockingIOError:
            return
        except OSError as err:
            self._lost(err)
            return
        if not data:
            self._lost(EOFError("serial port hung up"))
            return
        if self._echo:
            data = self._strip_echo(data)
            if not data:
                return
        self.rx_bytes += len(data)
        self._buf += data
        if self._gap_timer:
            self._gap_timer.cancel()
        if len(self._buf) >= MAX_FRAME:
            self._end_frame()
        else:
            self._gap_timer = self._loop.call_later(self.cfg.gap, self._end_frame)

    def _strip_echo(self, data: bytes) -> bytes:
        """Drop our own transmission heard back on a half-duplex (RS485) line."""
        if time.monotonic() > self._echo_until:
            self._echo.clear()
            return data
        n = 0
        while n < len(data) and n < len(self._echo) and data[n] == self._echo[n]:
            n += 1
        if n == 0:
            self._echo.clear()  # not our echo after all (collision or no echo on this line)
            return data
        del self._echo[:n]
        return data[n:]

    def _end_frame(self) -> None:
        self._gap_timer = None
        frame = bytes(self._buf[:MAX_FRAME])
        del self._buf[:MAX_FRAME]
        if not frame:
            return
        self.rx_frames += 1
        for fut in self._waiters:
            if not fut.done():
                fut.set_result(frame)
        self._on_frame(frame)

    # ---- transmit -----------------------------------------------------------------
    async def write(self, data: bytes, origin: str | None = None) -> None:
        if self._fd is None:
            raise OSError("serial port is not open")
        async with self._write_lock:
            fd = self._fd
            if self.cfg.echo_filter:
                # The echo arrives while we transmit; keep the window short so a device
                # reply that repeats the request (e.g. Modbus 06) is never eaten instead.
                self._echo = bytearray(data)
                airtime = len(data) * self.cfg.char_bits / self.cfg.baudrate
                self._echo_until = time.monotonic() + airtime + 0.1
            view = memoryview(data)
            while view:
                try:
                    view = view[os.write(fd, view):]
                except BlockingIOError:
                    await self._wait_writable(fd)
            await self._loop.run_in_executor(None, termios.tcdrain, fd)
            self.tx_bytes += len(data)
            self.tx_frames += 1
            self._on_tx(data, origin)
            # Keep the line quiet for one frame gap before the next send, so back-to-back
            # sends stay separate frames at the receiver (847767 merged them, 2026-10-16).
            await asyncio.sleep(self.cfg.gap)

    async def _wait_writable(self, fd: int) -> None:
        fut = self._loop.create_future()

        def ready() -> None:
            if not fut.done():
                fut.set_result(None)

        self._loop.add_writer(fd, ready)
        try:
            await fut
        finally:
            self._loop.remove_writer(fd)

    async def request(self, data: bytes, timeout: float, origin: str | None = None) -> bytes | None:
        """Write, then return the next received frame (None on timeout)."""
        fut: asyncio.Future[bytes] = self._loop.create_future()
        self._waiters.append(fut)
        try:
            await self.write(data, origin)
            return await asyncio.wait_for(fut, timeout)
        except TimeoutError:
            return None
        finally:
            self._waiters.remove(fut)

    # ---- diagnostics --------------------------------------------------------------
    def line_errors(self) -> dict[str, int] | None:
        """Kernel line error counters (TIOCGICOUNT), None if unavailable."""
        if self._fd is None:
            return None
        try:
            raw = fcntl.ioctl(self._fd, TIOCGICOUNT, bytes(80))
        except OSError:
            return None
        v = struct.unpack("20i", raw)
        return {"frame": v[6], "overrun": v[7], "parity": v[8], "break": v[9], "buffer_overrun": v[10]}


def _loop_flush(fd: int) -> None:
    """Send one byte through the UART's internal loopback right after open.

    On 2026-10-15 ttySC0 (SC16IS752 channel A) prefixed its first transmission with 128
    stale FIFO bytes; anything stuck that way now goes round the internal loop instead of
    onto the bus. Verified 2026-10-16 that nothing reaches the wire in loopback.
    """
    try:
        fcntl.ioctl(fd, TIOCMBIS, struct.pack("I", TIOCM_LOOP))
    except OSError:
        return
    try:
        time.sleep(0.05)
        os.write(fd, b"\x00")
        termios.tcdrain(fd)
        time.sleep(0.05)
    finally:
        fcntl.ioctl(fd, TIOCMBIC, struct.pack("I", TIOCM_LOOP))
        time.sleep(0.05)


def probe(path: str) -> None:
    """Raise OSError if the port cannot be opened right now."""
    os.close(os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK))
