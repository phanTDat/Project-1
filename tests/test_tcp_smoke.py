import socket
import tempfile
import unittest
from pathlib import Path

from hybridftp.server import start_test_server


def recv_reply(sock):
    data = bytearray()
    while not data.endswith(b"\r\n"):
        chunk = sock.recv(1)
        if not chunk:
            break
        data.extend(chunk)
    return bytes(data).decode("utf-8")


class TCPSmokeTests(unittest.TestCase):
    def test_server_control_line_smoke(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "server_root"
            log_file = Path(tmp) / "server.log"
            server = start_test_server(root=root, log_file=log_file)
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


if __name__ == "__main__":
    unittest.main()
