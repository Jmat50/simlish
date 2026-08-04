"""Sims 3 DBPF 2.0 package reader (index + resource bytes)."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


@dataclass(frozen=True)
class ResourceRef:
    type_id: int
    group: int
    instance_hi: int
    instance_lo: int
    offset: int
    size: int
    memsize: int
    compressed: int

    @property
    def instance(self) -> int:
        return (self.instance_hi << 32) | self.instance_lo

    @property
    def key(self) -> str:
        return f"{self.type_id:08X}_{self.group:08X}_{self.instance_hi:08X}_{self.instance_lo:08X}"


def _decompress_dbpf(src: bytes, expected: int | None = None) -> bytes:
    """RefPack / DBPF compression (SimsWiki Sims_3:DBPF/Compression)."""
    if len(src) < 5:
        raise ValueError("compressed payload too short")
    # Some packages prepend a 2- or 4-byte size before 0x10FB header
    start = 0
    if src[0] == 0xFC and len(src) > 6 and src[4] == 0x10 and src[5] == 0xFB:
        start = 4
    elif src[0] != 0x10 and src[0] != 0x40 and src[0] != 0x50 and src[0] != 0x80:
        # try skip leading dword
        if len(src) > 6 and src[4] in (0x10, 0x40, 0x50, 0x80) and src[5] == 0xFB:
            start = 4
    ctype = src[start]
    if src[start + 1] != 0xFB:
        raise ValueError(f"bad compression magic at {start}: {src[start:start+2].hex()}")
    pos = start + 2
    if ctype & 0x80:
        uncompressed_size = int.from_bytes(src[pos : pos + 4], "big")
        pos += 4
    else:
        uncompressed_size = int.from_bytes(src[pos : pos + 3], "big")
        pos += 3
    if expected is not None and uncompressed_size and uncompressed_size != expected:
        # still proceed; memsize is authoritative when present
        uncompressed_size = expected or uncompressed_size

    out = bytearray()
    while pos < len(src):
        b0 = src[pos]
        pos += 1
        if b0 < 0x80:
            if pos >= len(src):
                break
            b1 = src[pos]
            pos += 1
            num_plain = b0 & 0x03
            num_copy = ((b0 & 0x1C) >> 2) + 3
            copy_offset = ((b0 & 0x60) << 3) + b1 + 1
        elif b0 < 0xC0:
            if pos + 1 >= len(src):
                break
            b1 = src[pos]
            b2 = src[pos + 1]
            pos += 2
            num_plain = (b1 >> 6) & 0x03
            num_copy = (b0 & 0x3F) + 4
            copy_offset = ((b1 & 0x3F) << 8) + b2 + 1
        elif b0 < 0xE0:
            if pos + 2 >= len(src):
                break
            b1, b2, b3 = src[pos], src[pos + 1], src[pos + 2]
            pos += 3
            num_plain = b0 & 0x03
            num_copy = ((b0 & 0x0C) << 6) + b3 + 5
            copy_offset = ((b0 & 0x10) << 12) + (b1 << 8) + b2 + 1
        elif b0 < 0xFC:
            num_plain = ((b0 & 0x1F) << 2) + 4
            num_copy = 0
            copy_offset = 0
        else:
            num_plain = b0 & 0x03
            num_copy = 0
            copy_offset = 0
            out.extend(src[pos : pos + num_plain])
            break

        out.extend(src[pos : pos + num_plain])
        pos += num_plain
        for _ in range(num_copy):
            out.append(out[-copy_offset])

    if expected and len(out) != expected:
        # tolerate minor mismatch
        pass
    return bytes(out)


class Package:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.data = self.path.read_bytes()
        if self.data[:4] != b"DBPF":
            raise ValueError(f"not DBPF: {path}")
        self.major, self.minor = struct.unpack_from("<II", self.data, 4)
        self.index_count = struct.unpack_from("<I", self.data, 36)[0]
        self.index_position = struct.unpack_from("<I", self.data, 64)[0]
        self._entries: list[ResourceRef] | None = None

    def entries(self) -> list[ResourceRef]:
        if self._entries is not None:
            return self._entries
        pos = self.index_position
        index_type = struct.unpack_from("<I", self.data, pos)[0]
        pos += 4
        header_fields = [b for b in range(8) if index_type & (1 << b)]
        entry_fields = [b for b in range(8) if not (index_type & (1 << b))]
        header: dict[int, int] = {}
        for bit in header_fields:
            header[bit] = struct.unpack_from("<I", self.data, pos)[0]
            pos += 4
        out: list[ResourceRef] = []
        for _ in range(self.index_count):
            vals = dict(header)
            for bit in entry_fields:
                vals[bit] = struct.unpack_from("<I", self.data, pos)[0]
                pos += 4
            out.append(
                ResourceRef(
                    type_id=vals[0],
                    group=vals[1],
                    instance_hi=vals[2],
                    instance_lo=vals[3],
                    offset=vals[4],
                    size=vals[5] & 0x7FFFFFFF,
                    memsize=vals[6],
                    compressed=vals[7] & 0xFFFF,
                )
            )
        self._entries = out
        return out

    def iter_type(self, type_id: int) -> Iterator[ResourceRef]:
        for e in self.entries():
            if e.type_id == type_id:
                yield e

    def read_bytes(self, ref: ResourceRef) -> bytes:
        raw = self.data[ref.offset : ref.offset + ref.size]
        if ref.compressed == 0:
            return raw
        return _decompress_dbpf(raw, expected=ref.memsize)
