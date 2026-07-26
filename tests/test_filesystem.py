import tempfile
import unittest
from pathlib import Path, PurePosixPath

from hybridftp.filesystem import (
    FilesystemError,
    change_directory,
    change_to_parent,
    delete_file,
    file_size,
    list_detailed,
    list_names,
    make_directory,
    modified_time,
    remove_directory,
    rename_from,
    rename_to,
    resolve_virtual_path,
    stat_path,
    virtual_to_text,
)
from hybridftp.path_utils import resolve_server_root
from hybridftp.session import Session


def build_tree(root: Path) -> None:
    (root / "docs").mkdir(parents=True)
    (root / "empty").mkdir()
    (root / "nested" / "child").mkdir(parents=True)
    (root / "docs" / "readme.txt").write_text("hello phase two", encoding="utf-8")
    (root / "root.txt").write_text("root", encoding="utf-8")
    (root / ".hidden").write_text("hidden", encoding="utf-8")
    (root / "name with space.txt").write_text("space", encoding="utf-8")


class FilesystemHelperTests(unittest.TestCase):
    def make_session(self):
        tmp = tempfile.TemporaryDirectory()
        root = resolve_server_root(Path(tmp.name) / "root")
        build_tree(root)
        session = Session(session_id=1, client_address=("127.0.0.1", 12345), server_root=root)
        self.addCleanup(tmp.cleanup)
        return session, root

    def test_virtual_resolution_and_rejections(self):
        session, root = self.make_session()
        self.assertEqual(resolve_virtual_path(session, "/").virtual, PurePosixPath("/"))
        self.assertEqual(resolve_virtual_path(session, "docs").virtual, PurePosixPath("/docs"))
        self.assertEqual(resolve_virtual_path(session, " docs/readme.txt ").virtual, PurePosixPath("/docs/readme.txt"))
        self.assertEqual(resolve_virtual_path(session, "name with space.txt").virtual, PurePosixPath("/name with space.txt"))
        with self.assertRaises(FilesystemError):
            resolve_virtual_path(session, "../../outside")
        with self.assertRaises(FilesystemError):
            resolve_virtual_path(session, "bad\\path")
        with self.assertRaises(FilesystemError):
            resolve_virtual_path(session, "bad\x00path")
        with self.assertRaises(FilesystemError) as cm:
            resolve_virtual_path(session, "", required=True)
        self.assertEqual(cm.exception.code, 501)

    def test_listing_and_metadata_format(self):
        session, _ = self.make_session()
        target, detailed = list_detailed(session, "/")
        self.assertEqual(target, PurePosixPath("/"))
        names = [line.split(" name=", 1)[1] for line in detailed]
        self.assertEqual(names[:3], ["docs", "empty", "nested"])
        self.assertIn(".hidden", names)
        self.assertRegex(detailed[0], r"mtime=[0-9]{14}")
        file_target, file_lines = list_detailed(session, "/docs/readme.txt")
        self.assertEqual(file_target, PurePosixPath("/docs/readme.txt"))
        self.assertEqual(len(file_lines), 1)
        _, name_lines = list_names(session, "/docs/readme.txt")
        self.assertEqual(name_lines, ["readme.txt"])
        stat_target, stat_line = stat_path(session, "/")
        self.assertEqual(stat_target, PurePosixPath("/"))
        self.assertIn("entries=", stat_line)
        self.assertRegex(modified_time(session, "/docs"), r"^[0-9]{14}$")

    def test_navigation_and_mutation_safety(self):
        session, root = self.make_session()
        self.assertEqual(change_directory(session, "/docs"), PurePosixPath("/docs"))
        before = session.cwd
        with self.assertRaises(FilesystemError):
            change_directory(session, "/missing")
        self.assertEqual(session.cwd, before)
        self.assertEqual(change_to_parent(session), PurePosixPath("/"))
        self.assertEqual(change_to_parent(session), PurePosixPath("/"))
        self.assertEqual(make_directory(session, "newdir"), PurePosixPath("/newdir"))
        with self.assertRaises(FilesystemError):
            make_directory(session, "newdir")
        with self.assertRaises(FilesystemError):
            remove_directory(session, "/")
        with self.assertRaises(FilesystemError):
            delete_file(session, "/")
        with self.assertRaises(FilesystemError):
            file_size(session, "/")
        self.assertEqual(file_size(session, "/docs/readme.txt"), len("hello phase two"))
        self.assertEqual(delete_file(session, "/root.txt"), PurePosixPath("/root.txt"))
        self.assertFalse((root / "root.txt").exists())
        self.assertEqual(remove_directory(session, "/empty"), PurePosixPath("/empty"))
        with self.assertRaises(FilesystemError):
            remove_directory(session, "/docs")

    def test_rmd_rejects_cwd_and_parent(self):
        session, _ = self.make_session()
        change_directory(session, "/nested/child")
        with self.assertRaises(FilesystemError):
            remove_directory(session, "/nested/child")
        with self.assertRaises(FilesystemError):
            remove_directory(session, "/nested")

    def test_rename_validation_and_state_clearing(self):
        session, root = self.make_session()
        with self.assertRaises(FilesystemError):
            rename_from(session, "/")
        self.assertIsNone(session.rename_from_virtual)
        self.assertEqual(rename_from(session, "/docs/readme.txt"), PurePosixPath("/docs/readme.txt"))
        self.assertEqual(session.rename_from_virtual, PurePosixPath("/docs/readme.txt"))
        with self.assertRaises(FilesystemError):
            rename_to(session, "/docs")
        self.assertIsNone(session.rename_from_virtual)
        self.assertEqual(rename_from(session, "/docs/readme.txt"), PurePosixPath("/docs/readme.txt"))
        with self.assertRaises(FilesystemError):
            rename_to(session, "/nested/missing-parent/file.txt")
        self.assertIsNone(session.rename_from_virtual)
        self.assertEqual(rename_from(session, "/docs"), PurePosixPath("/docs"))
        with self.assertRaises(FilesystemError):
            rename_to(session, "/docs/inside")
        self.assertIsNone(session.rename_from_virtual)
        self.assertEqual(rename_from(session, "/docs/readme.txt"), PurePosixPath("/docs/readme.txt"))
        self.assertEqual(rename_to(session, "/renamed.txt"), PurePosixPath("/renamed.txt"))
        self.assertTrue((root / "renamed.txt").exists())
        self.assertFalse((root / "docs" / "readme.txt").exists())


if __name__ == "__main__":
    unittest.main()
