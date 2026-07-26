import io
import tempfile
import unittest
from pathlib import Path

from hybridftp.integrity import HashComparison, sha256_path, sha256_stream


class IntegrityTests(unittest.TestCase):
    def test_stream_and_path_hash_binary_bytes(self):
        payload = bytes(range(256)) * 8 + b"\x00tail"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixture.bin"
            path.write_bytes(payload)
            digest = sha256_path(path)
        self.assertEqual(digest, sha256_stream(io.BytesIO(payload)))
        self.assertEqual(len(digest), 64)

    def test_comparison_reports_match_state(self):
        self.assertTrue(HashComparison("a", "A").matches)
        self.assertFalse(HashComparison("a", "b").matches)


if __name__ == "__main__":
    unittest.main()
