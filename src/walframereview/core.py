import argparse
import hashlib
import json
import os
import stat
import struct

MAX_BYTES = 16 * 1024 * 1024
MAX_RECORDS = 100000


class Invalid(ValueError):
    pass


class Unsupported(ValueError):
    pass


def require(ok, code):
    if not ok:
        raise Invalid(code)


def unpack(fmt, data, offset=0):
    require(
        offset >= 0 and offset + struct.calcsize(fmt) <= len(data), "truncated_field"
    )
    return struct.unpack_from(fmt, data, offset)


def text(data, encoding="utf-8"):
    try:
        return data.decode(encoding)
    except UnicodeError:
        raise Invalid("invalid_text_encoding") from None


def inspect(data):
    if not isinstance(data, bytes):
        raise TypeError("input must be bytes")
    digest = hashlib.sha256(data).hexdigest()
    try:
        require(len(data) <= MAX_BYTES, "input_limit")
        result = analyze(data)
        result.setdefault("status", "PASS")
        result.setdefault("complete", result["status"] == "PASS")
        result.setdefault("findings", [])
    except Unsupported as exc:
        result = {"status": "OPEN", "complete": False, "findings": [str(exc)]}
    except Invalid as exc:
        result = {"status": "FAIL", "complete": False, "findings": [str(exc)]}
    result.update(
        {
            "input_sha256": digest,
            "input_bytes": len(data),
            "claim": "Recorded format checks only; no authenticity, runtime or CVP approval conclusion.",
        }
    )
    return result


def read_local(path):
    fd = os.open(
        path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    )
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode), "regular_file_required")
        require(info.st_size <= MAX_BYTES, "input_limit")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read(MAX_BYTES + 1)
        require(len(data) <= MAX_BYTES, "input_limit")
        after = os.fstat(fd)
        require(
            (info.st_size, info.st_mtime_ns, info.st_ino)
            == (after.st_size, after.st_mtime_ns, after.st_ino),
            "input_changed_during_read",
        )
        return data
    finally:
        os.close(fd)


def main():
    parser = argparse.ArgumentParser(
        description="Read an explicitly supplied local evidence file and print a private-safe JSON report."
    )
    parser.add_argument("input")
    args = parser.parse_args()
    try:
        report = inspect(read_local(args.input))
    except (OSError, Invalid):
        report = {
            "status": "FAIL",
            "complete": False,
            "findings": ["input_read_failed"],
        }
    print(json.dumps(report, sort_keys=True, ensure_ascii=True))
    return {"PASS": 0, "FAIL": 1, "OPEN": 2}[report["status"]]


def checksum(data, endian, state=(0, 0)):
    require(len(data) % 8 == 0, "checksum_alignment")
    a, b = state
    for x, y in struct.iter_unpack(endian + "II", data):
        a = (a + x + b) & 0xFFFFFFFF
        b = (b + y + a) & 0xFFFFFFFF
    return a, b


def analyze(data):
    magic, version, page_size, sequence, salt1, salt2, check1, check2 = unpack(
        ">8I", data
    )
    if magic not in (0x377F0682, 0x377F0683):
        raise Invalid("invalid_wal_magic")
    if version != 3007000:
        raise Unsupported("unsupported_wal_version")
    require(
        512 <= page_size <= 65536 and page_size & (page_size - 1) == 0,
        "invalid_page_size",
    )
    endian = "<" if magic == 0x377F0682 else ">"
    state = checksum(data[:24], endian)
    require(state == (check1, check2), "header_checksum_mismatch")
    stride = page_size + 24
    require((len(data) - 32) % stride == 0, "truncated_frame")
    count = (len(data) - 32) // stride
    require(count <= MAX_RECORDS, "frame_limit")
    frames, commits = [], []
    for i in range(count):
        offset = 32 + i * stride
        page, db_size, s1, s2, c1, c2 = unpack(">6I", data, offset)
        require(page > 0 and page != 0xFFFFFFFF, "invalid_page_number")
        require((s1, s2) == (salt1, salt2), "frame_salt_mismatch")
        state = checksum(
            data[offset : offset + 8] + data[offset + 24 : offset + stride],
            endian,
            state,
        )
        require(state == (c1, c2), "frame_checksum_mismatch")
        frames.append(
            {
                "frame": i + 1,
                "offset": offset,
                "page_number": page,
                "commit_pages": db_size,
            }
        )
        if db_size:
            require(db_size != 0xFFFFFFFF, "invalid_commit_size")
            commits.append({"frame": i + 1, "database_pages": db_size})
    committed = commits[-1]["frame"] if commits else 0
    tail = count - committed
    return {
        "frames": frames,
        "frame_count": count,
        "page_size": page_size,
        "checkpoint_sequence": sequence,
        "commits": commits,
        "uncommitted_frames": tail,
        "status": "OPEN" if tail else "PASS",
        "complete": not tail,
        "findings": ["valid_uncommitted_tail"] if tail else [],
        "scope": "WAL file checksums and commit boundaries; no SQL execution, page decoding or database recovery.",
    }
