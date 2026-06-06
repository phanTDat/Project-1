import io
import socket
import tempfile
import unittest
from pathlib import Path

from hybridftp.client import connect_and_run, open_style_run
from hybridftp.server import start_test_server


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
                "502 Command not implemented yet",
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


if __name__ == "__main__":
    unittest.main()
