"""MOZA serial frame encoding and decoding.

Wire format, verified on AB9 hardware (see docs/02-protocol.md):

    0x7E | length | group | device | payload... | checksum

`length` counts the payload only. `checksum` is (sum of all preceding bytes + 13)
& 0xFF. Replies set bit 7 of the group byte and swap the nibbles of the device
byte.

The stream is not self-synchronising: 0x7E can occur inside a payload, so a
reader must resynchronise by scanning for a start byte and validating the
checksum. Anything that fails validation is dropped, never guessed at.
"""

from __future__ import annotations

from dataclasses import dataclass

START = 0x7E
MAGIC = 13
MAX_PAYLOAD = 64

GET_GROUP = 30          # Main_get
SET_GROUP = 31          # Main_set
PARAM_GROUP = 14        # raw parameter store, and the ASCII log channel
PARAM_READ_CMD = 0
LOG_CMD = 5
DEVICE_MAIN = 18


def checksum(data: bytes | bytearray) -> int:
    return (sum(data) + MAGIC) & 0xFF


def encode(group: int, device: int, payload: bytes | list[int]) -> bytes:
    payload = bytes(payload)
    if not 1 <= len(payload) <= MAX_PAYLOAD:
        raise ValueError(f"payload length {len(payload)} out of range")
    frame = bytearray([START, len(payload), group, device])
    frame += payload
    frame.append(checksum(frame))
    return bytes(frame)


@dataclass(frozen=True)
class Frame:
    group: int
    device: int
    payload: bytes

    @property
    def is_reply(self) -> bool:
        return bool(self.group & 0x80)

    @property
    def reply_to(self) -> int:
        """The request group this frame answers."""
        return self.group & 0x7F

    @property
    def source_device(self) -> int:
        """Replies carry the device id with its nibbles swapped."""
        if not self.is_reply:
            return self.device
        return ((self.device & 0x0F) << 4) | (self.device >> 4)

    @property
    def is_log(self) -> bool:
        """The firmware's ASCII broadcast channel.

        This is a broadcast, not a reply: log text arrives whenever the firmware
        feels like it and must never be attributed to whatever request happens to
        be outstanding. Long messages are split across frames mid-string.
        """
        return self.group & 0x7F == PARAM_GROUP and self.payload[:1] == bytes([LOG_CMD])

    @property
    def log_text(self) -> str:
        return self.payload[1:].decode("utf-8", "replace")


def decode(buffer: bytes) -> tuple[list[Frame], int]:
    """Extract whole frames from `buffer`.

    Returns the frames found and the number of bytes consumed, so a caller can
    keep the unconsumed tail for the next read.
    """
    frames: list[Frame] = []
    i = 0
    consumed = 0
    while i < len(buffer):
        if buffer[i] != START:
            i += 1
            continue
        if i + 1 >= len(buffer):
            break
        length = buffer[i + 1]
        end = i + 4 + length
        if not 1 <= length <= MAX_PAYLOAD:
            i += 1
            continue
        if end >= len(buffer):
            break                      # incomplete; wait for more bytes
        if checksum(buffer[i:end]) != buffer[end]:
            i += 1
            continue
        frames.append(Frame(buffer[i + 2], buffer[i + 3], bytes(buffer[i + 4:end])))
        i = end + 1
        consumed = i
    return frames, consumed
