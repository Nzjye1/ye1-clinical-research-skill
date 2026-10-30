"""PNG textual provenance only; preserve every existing image data chunk."""
import hashlib
from pathlib import Path
import struct
import sys
import zlib


def stamp_png(path, origin, purpose):
    if origin not in {"real", "synthetic"} or purpose not in {"engineering_test", "research_analysis"}:
        raise ValueError("PNG_CONTEXT_INVALID")
    path = Path(path)
    raw = path.read_bytes()
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("PNG_FORMAT_INVALID")
    chunks, data_before, pos, ended = [], [], 8, False
    fields = {"data_origin": origin, "task_purpose": purpose,
              "test_only": str(purpose == "engineering_test").lower(), "scientific_review": "pending"}
    while pos < len(raw):
        size = struct.unpack(">I", raw[pos:pos+4])[0]
        kind = raw[pos+4:pos+8]
        end = pos+12+size
        if end > len(raw):
            raise ValueError("PNG_CHUNK_INVALID")
        body = raw[pos+8:pos+8+size]
        if zlib.crc32(kind+body) & 0xffffffff != struct.unpack(">I", raw[pos+8+size:end])[0]:
            raise ValueError("PNG_CRC_INVALID")
        if kind == b"IDAT":
            data_before.append(body)
        if kind == b"IEND":
            for key, value in fields.items():
                payload = key.encode("ascii")+b"\0"+value.encode("ascii")
                chunks.append(struct.pack(">I",len(payload))+b"tEXt"+payload+struct.pack(">I",zlib.crc32(b"tEXt"+payload)&0xffffffff))
            chunks.append(raw[pos:end]);ended = end == len(raw)
            break
        if not (kind == b"tEXt" and body.split(b"\0",1)[0].decode("latin1") in fields):
            chunks.append(raw[pos:end])
        pos = end
    if not ended:
        raise ValueError("PNG_IEND_INVALID")
    new = raw[:8]+b"".join(chunks)
    # The PNG's encoded image stream is copied verbatim, not re-rendered.
    if b"".join(data_before) != b"".join(c[8:-4] for c in chunks if c[4:8] == b"IDAT"):
        raise ValueError("PNG_IMAGE_DATA_CHANGED")
    path.write_bytes(new)
    return hashlib.sha256(new).hexdigest()


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit(2)
    stamp_png(*sys.argv[1:])
