import io
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from hybridftp.client import connect_and_run, open_style_run
from hybridftp.server import DEFAULT_HOST, serve, start_test_server


def recv_reply(sock):
    data = bytearray()
    while not data.endswith(b"\r\n"):
        chunk = sock.recv(1)
        if not chunk:
            break
        data.extend(chunk)
    return bytes(data).decode("utf-8")


def assert_order(testcase, text, *needles):
    position = -1
    for needle in needles:
        next_position = text.find(needle, position + 1)
        testcase.assertNotEqual(next_position, -1, f"missing {needle!r} after offset {position}")
        position = next_position


class TCPSmokeTests(unittest.TestCase):
    def start_server(self, tmp):
        root = Path(tmp) / "server_root"
        log_file = Path(tmp) / "server.log"
        server = start_test_server(root=root, log_file=log_file)
        return server, root, log_file

    def test_server_control_line_smoke(self):
        with tempfile.TemporaryDirectory() as tmp:
            server, root, log_file = self.start_server(tmp)
            try:
                with socket.create_connection((server.host, server.port), timeout=2.0) as sock:
                    self.assertEqual(recv_reply(sock), "220 Hybrid FTP server ready\r\n")
                    sock.sendall(b"NOOP\r\n")
                    self.assertEqual(recv_reply(sock), "200 NOOP ok\r\n")
                    sock.sendall(b"BOGUS\r\n")
                    self.assertEqual(recv_reply(sock), "500 Unknown command\r\n")
                    sock.sendall(b"USER \xff\r\n")
                    self.assertEqual(recv_reply(sock), "501 Syntax error in parameters or arguments\r\n")
                    sock.sendall(b"X" * 1025 + b"\r\n")
                    self.assertEqual(recv_reply(sock), "501 Syntax error in parameters or arguments\r\n")
                    sock.sendall(b"QUIT\r\n")
                    self.assertEqual(recv_reply(sock), "221 Goodbye\r\n")
            finally:
                server.stop()
                server.join()
            self.assertTrue(root.exists())
            self.assertIn(str(root.resolve()), log_file.read_text(encoding="utf-8"))

    def test_filesystem_navigation_listing_metadata_and_mutations(self):
        with tempfile.TemporaryDirectory() as tmp:
            server, root, log_file = self.start_server(tmp)
            (root / "docs").mkdir()
            (root / "docs" / "readme.txt").write_text("hello phase two", encoding="utf-8")
            (root / "empty").mkdir()
            (root / "nested" / "child").mkdir(parents=True)
            (root / "delete-me.txt").write_text("delete", encoding="utf-8")
            (root / "old.txt").write_text("old", encoding="utf-8")
            (root / "name with space.txt").write_text("space", encoding="utf-8")
            transcript = io.StringIO()
            try:
                connect_and_run(
                    server.host,
                    server.port,
                    commands=[
                        "USER student",
                        "PASS cs494",
                        "PWD",
                        "CWD docs",
                        "PWD",
                        "CDUP",
                        "PWD",
                        "LIST /",
                        "NLST /",
                        "STAT",
                        "STAT /",
                        "SIZE /docs/readme.txt",
                        "MDTM /docs/readme.txt",
                        "MKD newdir",
                        "RMD empty",
                        "DELE delete-me.txt",
                        "RNTO nope.txt",
                        "RNFR old.txt",
                        "STAT",
                        "PWD",
                        "RNTO renamed.txt",
                        "RMD /",
                        "RNFR /",
                        "QUIT",
                    ],
                    transcript=transcript,
                )
            finally:
                server.stop()
                server.join()
            text = transcript.getvalue()
            for expected in [
                '257 "/" is current directory',
                '250 Directory changed to "/docs"',
                '257 "/docs" is current directory',
                "212-",
                "dir entries=",
                "readme.txt",
                "cwd=/ root=/",
                "213 15",
                "257 \"/newdir\" created",
                "250 Requested file action okay, completed",
                "503 Bad sequence of commands",
                "350 Requested file action pending further information",
                "pending_rename=/old.txt",
                "550 Cannot remove the current directory, its parent, or root",
                "550 Cannot rename root, current directory, or its parent",
                "221 Goodbye",
            ]:
                self.assertIn(expected, text)
            self.assertNotIn("150 Opening UDP data connection", text)
            self.assertNotIn("226 Transfer complete", text)
            self.assertTrue((root / "renamed.txt").exists())
            self.assertFalse((root / "old.txt").exists())
            log_text = log_file.read_text(encoding="utf-8")
            self.assertIn("command=LIST /", log_text)
            self.assertIn("reply=212", log_text)
            self.assertNotIn("hello phase two", log_text)

    def test_unauthenticated_filesystem_commands_are_gated_before_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            server, _, _ = self.start_server(tmp)
            transcript = io.StringIO()
            try:
                connect_and_run(
                    server.host,
                    server.port,
                    commands=["PWD", "CWD ", "SIZE missing.txt", "MKD bad", "DELE bad", "RNFR old", "RNTO new", "RETR file.txt", "QUIT"],
                    transcript=transcript,
                )
            finally:
                server.stop()
                server.join()
            text = transcript.getvalue()
            self.assertGreaterEqual(text.count("530 Not logged in"), 8)
            self.assertIn("221 Goodbye", text)

    def test_abor_cancels_active_udp_transfer(self):
        with tempfile.TemporaryDirectory() as tmp:
            server, root, _ = self.start_server(tmp)
            try:
                with socket.create_connection((server.host, server.port), timeout=2.0) as sock:
                    sock.settimeout(2.0)
                    self.assertEqual(recv_reply(sock), "220 Hybrid FTP server ready\r\n")
                    for command, expected in [(b"USER student\r\n", "331"), (b"PASS cs494\r\n", "230"), (b"PASV\r\n", "227")]:
                        sock.sendall(command)
                        self.assertTrue(recv_reply(sock).startswith(expected))
                    sock.sendall(b"STOR aborted.bin\r\n")
                    self.assertTrue(recv_reply(sock).startswith("150"))
                    sock.sendall(b"ABOR\r\n")
                    replies = [recv_reply(sock), recv_reply(sock)]
                    self.assertIn("226 Abort successful\r\n", replies)
                    self.assertIn("426 Connection closed; transfer aborted\r\n", replies)
                    sock.sendall(b"QUIT\r\n")
                    self.assertEqual(recv_reply(sock), "221 Goodbye\r\n")
            finally:
                server.stop()
                server.join()
            self.assertFalse((root / "aborted.bin").exists())
            self.assertFalse(list(root.glob("*.part")))

    def test_scripted_client_flow_and_multiline_sync(self):
        with tempfile.TemporaryDirectory() as tmp:
            server, _, _ = self.start_server(tmp)
            transcript = io.StringIO()
            try:
                connect_and_run(
                    server.host,
                    server.port,
                    commands=[
                        "USER unknown",
                        "PASS anything",
                        "LIST",
                        "USER student",
                        "PASS cs494",
                        "HELP",
                        "HELP USER",
                        "NOOP",
                        "BOGUS",
                        "LIST",
                        "QUIT",
                    ],
                    transcript=transcript,
                )
            finally:
                server.stop()
                server.join()
            text = transcript.getvalue()
            for expected in [
                "220 Hybrid FTP server ready",
                "530 Invalid username",
                "503 Bad sequence of commands",
                "530 Not logged in",
                "331 User name okay, need password",
                "230 User logged in",
                "214-",
                "200 NOOP ok",
                "500 Unknown command",
                "212 End",
                "221 Goodbye",
            ]:
                self.assertIn(expected, text)
            assert_order(
                self,
                text,
                "ftp> HELP\n",
                "214 End of help\n",
                "ftp> HELP USER\n",
                "214 End of help\n",
                "ftp> NOOP\n",
                "200 NOOP ok",
            )
            self.assertIn("ftp> PASS ********", text)
            self.assertNotIn("anything", text)
            self.assertNotIn("cs494", text)

    def test_open_style_client_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            server, _, _ = self.start_server(tmp)
            transcript = io.StringIO()
            try:
                open_style_run(
                    commands=[f"open {server.host} {server.port}", "NOOP", "QUIT"],
                    transcript=transcript,
                )
            finally:
                server.stop()
                server.join()
            text = transcript.getvalue()
            assert_order(
                self,
                text,
                f"ftp> open {server.host} {server.port}",
                "220 Hybrid FTP server ready",
                "ftp> NOOP",
                "200 NOOP ok",
                "ftp> QUIT",
                "221 Goodbye",
            )

    def test_open_style_rejects_commands_before_open_and_bad_open_syntax(self):
        transcript = io.StringIO()
        open_style_run(commands=["NOOP", "open 127.0.0.1 not-a-port"], transcript=transcript)
        text = transcript.getvalue()
        assert_order(
            self,
            text,
            "ftp> NOOP",
            "530 Not connected; use open <host> <port>",
            "ftp> open 127.0.0.1 not-a-port",
            "501 Syntax error in parameters or arguments",
        )

    def test_cli_help_entrypoints_expose_phase1_options(self):
        project_root = Path(__file__).resolve().parents[1]
        commands = [
            [sys.executable, "-m", "hybridftp.server", "--help"],
            [sys.executable, "server.py", "--help"],
            [sys.executable, "-m", "hybridftp.client", "--help"],
            [sys.executable, "client.py", "--help"],
        ]
        for command in commands:
            with self.subTest(command=command):
                result = subprocess.run(command, cwd=project_root, text=True, capture_output=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr)
                output = result.stdout
                if "server" in command[-2] or command[1:3] == ["-m", "hybridftp.server"]:
                    self.assertIn("--host", output)
                    self.assertIn("--port", output)
                    self.assertIn("--root", output)
                    self.assertIn("--log-file", output)
                else:
                    self.assertIn("host", output)
                    self.assertIn("port", output)
                    self.assertIn("--commands", output)
                    self.assertIn("--no-connect", output)

    def test_ctrl_c_shutdown_is_logged_before_handler_cleanup(self):
        class InterruptingSocket:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def setsockopt(self, *args):
                pass

            def bind(self, address):
                pass

            def listen(self, backlog):
                pass

            def settimeout(self, timeout):
                pass

            def getsockname(self):
                return (DEFAULT_HOST, 2121)

            def accept(self):
                raise KeyboardInterrupt

        with tempfile.TemporaryDirectory() as tmp:
            log_file = Path(tmp) / "server.log"
            with mock.patch("hybridftp.server.socket.socket", return_value=InterruptingSocket()):
                self.assertEqual(serve(DEFAULT_HOST, 2121, Path(tmp) / "server_root", log_file=log_file), 0)
            log_text = log_file.read_text(encoding="utf-8")
            self.assertIn("graceful shutdown requested by Ctrl+C", log_text)
            self.assertIn("shutdown complete", log_text)


if __name__ == "__main__":
    unittest.main()
