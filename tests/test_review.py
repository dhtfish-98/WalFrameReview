import struct
import sqlite3
import tempfile
from pathlib import Path
import unittest
from walframereview import inspect
from walframereview.core import checksum


def sample(endian="<", commit=1):
    magic = 0x377F0682 if endian == "<" else 0x377F0683
    header = struct.pack(">6I", magic, 3007000, 512, 0, 1, 2)
    state = checksum(header, endian)
    h = header + struct.pack(">2I", *state)
    frame = struct.pack(">2I", 1, commit)
    page = b"\0" * 512
    state = checksum(frame + page, endian, state)
    return h + frame + struct.pack(">4I", 1, 2, *state) + page


class Tests(unittest.TestCase):
    def test_byte_orders(self):
        for e in ("<", ">"):
            self.assertEqual(inspect(sample(e))["status"], "PASS")

    def test_real_sqlite(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "s.db"
            db = sqlite3.connect(p)
            db.execute("pragma journal_mode=wal")
            db.execute("pragma wal_autocheckpoint=0")
            db.execute("create table evidence(i)")
            db.execute("insert into evidence values(1)")
            db.commit()
            raw = Path(str(p) + "-wal").read_bytes()
            r = inspect(raw)
            self.assertEqual(r["status"], "PASS")
            self.assertGreater(len(r["commits"]), 0)
            db.close()

    def test_partial(self):
        self.assertEqual(inspect(sample()[:-1])["status"], "FAIL")

    def test_corrupt_page(self):
        self.assertEqual(inspect(sample()[:-1] + b"x")["status"], "FAIL")

    def test_corrupt_header(self):
        self.assertEqual(inspect(b"x" + sample()[1:])["status"], "FAIL")

    def test_salt(self):
        d = bytearray(sample())
        d[40] ^= 1
        self.assertEqual(inspect(bytes(d))["status"], "FAIL")

    def test_uncommitted(self):
        self.assertEqual(inspect(sample(commit=0))["status"], "OPEN")

    def test_unknown(self):
        d = bytearray(sample())
        struct.pack_into(">I", d, 4, 1)
        self.assertEqual(inspect(bytes(d))["status"], "OPEN")

    def test_zero_page(self):
        d = bytearray(sample())
        d[32:36] = b"\0" * 4
        self.assertEqual(inspect(bytes(d))["status"], "FAIL")
