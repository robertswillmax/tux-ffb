"""Serial transport for the MOZA config channel.

Two things shape this design, both learned from hardware:

*Replies are self-identifying* — every reply echoes the command id, and indexed
replies echo the index too. So requests need not be serialised: a whole batch can
be sent and the replies matched by echo. A full 238-address read takes ~0.1 s
this way versus minutes serialised.

*The log channel is a broadcast* — ASCII frames arrive unprompted and must never
be attributed to an outstanding request. Only a data frame whose payload starts
with the bytes we asked for counts as an answer.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterable, Sequence

import serial

from .discovery import find_port
from .framing import (DEVICE_MAIN, GET_GROUP, PARAM_GROUP, PARAM_READ_CMD,
                      SET_GROUP, Frame, decode, encode)

BAUD = 115200


class Transport:
    """Owns the serial port and a background reader.

    Opened non-exclusively on purpose: boxflat may hold a port for a racing base
    on the same machine, and neither tool should lock the other out. We only ever
    open a port we have identified as a flight base.
    """

    def __init__(self, path: str | None = None, device: int = DEVICE_MAIN):
        # Never default to ttyACM0: the node number moves. A VM passthrough
        # cycle is enough to shift it, and it did during development.
        path = path or find_port()
        if path is None:
            raise FileNotFoundError("no MOZA flight base found on any serial port")
        self.path = path
        self.device = device
        self._buf = bytearray()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._log: list[str] = []
        self._serial = serial.Serial(path, BAUD, timeout=0.005, exclusive=False)
        self._reader = threading.Thread(target=self._pump, daemon=True)
        self._reader.start()
        time.sleep(0.3)

    # -- lifecycle ---------------------------------------------------------
    def close(self) -> None:
        self._stop.set()
        time.sleep(0.2)
        try:
            self._serial.close()
        except Exception:
            pass

    def __enter__(self) -> "Transport":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _pump(self) -> None:
        while not self._stop.is_set():
            try:
                data = self._serial.read(4096)
            except Exception:
                return
            if data:
                with self._lock:
                    self._buf.extend(data)

    # -- low level ---------------------------------------------------------
    def _take_frames(self) -> list[Frame]:
        with self._lock:
            frames, consumed = decode(bytes(self._buf))
            if consumed:
                del self._buf[:consumed]
        for f in frames:
            if f.is_log:
                self._log.append(f.log_text)
        return [f for f in frames if not f.is_log]

    def drain(self, quiet: float = 0.05, cap: float = 1.0) -> None:
        """Wait until the line has been quiet, then discard what's buffered."""
        deadline = time.time() + cap
        last = -1
        while time.time() < deadline:
            with self._lock:
                n = len(self._buf)
            if n == last:
                break
            last = n
            time.sleep(quiet)
        with self._lock:
            self._buf.clear()
        self._log.clear()

    def send(self, group: int, payload: Sequence[int]) -> None:
        self._serial.write(encode(group, self.device, list(payload)))
        self._serial.flush()

    def take_log(self) -> str:
        """Consume the ASCII log accumulated since the last call."""
        self._take_frames()
        text = "".join(self._log)
        self._log.clear()
        return text

    # -- request/response --------------------------------------------------
    def request_many(self, addresses: Iterable[Sequence[int]], *,
                     batch: int = 128, timeout: float = 0.7,
                     rounds: int = 3) -> dict[tuple[int, ...], bytes]:
        """Pipelined read. `addresses` are payload prefixes, e.g. (cmd,) or (cmd, index).

        Returns {address: value_bytes} for everything that answered.
        """
        pending = [tuple(a) for a in addresses]
        got: dict[tuple[int, ...], bytes] = {}
        for _ in range(rounds):
            if not pending:
                break
            missed: list[tuple[int, ...]] = []
            for start in range(0, len(pending), batch):
                chunk = pending[start:start + batch]
                self.drain()
                for addr in chunk:
                    self.send(GET_GROUP, addr)
                outstanding = set(chunk)
                deadline = time.time() + timeout
                while outstanding and time.time() < deadline:
                    time.sleep(0.01)
                    for frame in self._take_frames():
                        for addr in list(outstanding):
                            n = len(addr)
                            if frame.payload[:n] == bytes(addr):
                                got[addr] = frame.payload[n:]
                                outstanding.discard(addr)
                                break
                missed.extend(outstanding)
            pending = missed
        return got

    def request(self, address: Sequence[int], timeout: float = 0.5) -> bytes | None:
        return self.request_many([address], batch=1, timeout=timeout, rounds=2).get(tuple(address))

    def write_raw(self, payload: Sequence[int]) -> str:
        """Send a set-group frame and return whatever the firmware logged.

        There is no reply frame for a write. Confirmation comes from the log
        channel and, properly, from reading the value back — which is the
        caller's job, and is not optional: a wrong-width write can store the
        wrong value with no warning at all.
        """
        self.drain()
        self.send(SET_GROUP, payload)
        time.sleep(0.5)
        return self.take_log()

    # -- raw parameter store ----------------------------------------------
    NOT_IMPLEMENTED = 0x00008000

    def read_params(self, indices: Iterable[int]) -> dict[int, int]:
        """Read the flat parameter store (group 14, cmd 0) by 16-bit index.

        Indices that do not exist answer with 0x00008000 rather than an error, so
        those are filtered out here — an unimplemented parameter is absence, not
        a value.
        """
        indices = list(indices)
        pending = list(indices)
        got: dict[int, int] = {}
        for _ in range(3):
            if not pending:
                break
            missed: list[int] = []
            for start in range(0, len(pending), 96):
                chunk = pending[start:start + 96]
                self.drain()
                for idx in chunk:
                    self.send(PARAM_GROUP,
                              [PARAM_READ_CMD, (idx >> 8) & 0xFF, idx & 0xFF])
                outstanding = set(chunk)
                deadline = time.time() + 0.8
                while outstanding and time.time() < deadline:
                    time.sleep(0.01)
                    for frame in self._take_frames():
                        p = frame.payload
                        if p[:1] != bytes([PARAM_READ_CMD]) or len(p) < 7:
                            continue
                        idx = (p[1] << 8) | p[2]
                        if idx in outstanding:
                            got[idx] = int.from_bytes(p[3:7], "big")
                            outstanding.discard(idx)
                missed.extend(outstanding)
            pending = missed
        return {k: v for k, v in got.items() if v != self.NOT_IMPLEMENTED}
