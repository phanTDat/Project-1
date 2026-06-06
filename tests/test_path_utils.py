import tempfile
import unittest
from pathlib import Path

from hybridftp.path_utils import ensure_within_root, resolve_server_root


class PathUtilsTests(unittest.TestCase):
    def test_resolve_server_root_creates_missing_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "missing"
            resolved = resolve_server_root(root)
            self.assertTrue(resolved.is_absolute())
            self.assertTrue(resolved.is_dir())

    def test_ensure_within_root_accepts_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = resolve_server_root(Path(tmp) / "root")
            child = ensure_within_root(root, root / "child.txt")
            self.assertEqual(child, (root / "child.txt").resolve())

    def test_ensure_within_root_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = resolve_server_root(base / "root")
            outside = base / "outside.txt"
            with self.assertRaises(ValueError):
                ensure_within_root(root, root / ".." / outside.name)


if __name__ == "__main__":
    unittest.main()
