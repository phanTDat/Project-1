import io
import os
import tempfile
import unittest
from pathlib import Path

from hybridftp.client import connect_and_run
from hybridftp.integrity import sha256_path
from hybridftp.server import start_test_server


class TransferProtocolTests(unittest.TestCase):
    def test_passive_ascii_upload_normalizes_nvt_newlines(self):
        payload = b"first\r\nsecond\nthird\rfourth\n"
        expected = f"first{os.linesep}second{os.linesep}third{os.linesep}fourth{os.linesep}".encode("ascii")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "server"
            local = Path(tmp) / "local.txt"
            downloaded = Path(tmp) / "downloaded.txt"
            local.write_bytes(payload)
            server = start_test_server(root)
            transcript = io.StringIO()
            try:
                connect_and_run(
                    server.host,
                    server.port,
                    commands=[
                        "USER student",
                        "PASS cs494",
                        "TYPE A",
                        f"put {local} uploaded.txt",
                        f"get uploaded.txt {downloaded}",
                        "QUIT",
                    ],
                    transcript=transcript,
                )
            finally:
                server.stop()
                server.join()
            self.assertEqual((root / "uploaded.txt").read_bytes(), expected)
            self.assertEqual(downloaded.read_bytes(), expected)
            self.assertIn("SHA-256 local=", transcript.getvalue())
            self.assertIn("match=True", transcript.getvalue())

    def test_passive_binary_upload_download_and_hash(self):
        payload = bytes(range(256)) * 12 + b"\x00Hybrid FTP binary fixture"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "server"
            local = Path(tmp) / "local.bin"
            downloaded = Path(tmp) / "downloaded.bin"
            local.write_bytes(payload)
            server = start_test_server(root)
            transcript = io.StringIO()
            try:
                connect_and_run(
                    server.host,
                    server.port,
                    commands=[
                        "USER student",
                        "PASS cs494",
                        "TYPE I",
                        "MODE S",
                        f"put {local} uploaded.bin",
                        f"get uploaded.bin {downloaded}",
                        "HASH uploaded.bin",
                        "QUIT",
                    ],
                    transcript=transcript,
                )
            finally:
                server.stop()
                server.join()
            self.assertEqual((root / "uploaded.bin").read_bytes(), payload)
            self.assertEqual(downloaded.read_bytes(), payload)
            self.assertEqual(sha256_path(local), sha256_path(downloaded))
            text = transcript.getvalue()
            self.assertGreaterEqual(text.count("150 Opening UDP data connection"), 2)
            self.assertGreaterEqual(text.count("226 Transfer complete"), 2)
            self.assertIn("SHA-256 local=", text)


if __name__ == "__main__":
    unittest.main()
