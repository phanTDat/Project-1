import socket
import tempfile
import unittest
from pathlib import Path

from hybridftp.server import start_test_server


def reply(sock: socket.socket) -> str:
    data = bytearray()
    while not data.endswith(b"\r\n"):
        data.extend(sock.recv(1))
    return data.decode("utf-8")


class ConcurrencyTests(unittest.TestCase):
    def test_two_clients_have_isolated_working_directories_and_visible_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "server"
            root.mkdir()
            (root / "one").mkdir()
            (root / "two").mkdir()
            server = start_test_server(root)
            first = socket.create_connection((server.host, server.port), timeout=2)
            second = socket.create_connection((server.host, server.port), timeout=2)
            try:
                self.assertTrue(reply(first).startswith("220"))
                self.assertTrue(reply(second).startswith("220"))
                for client in (first, second):
                    client.sendall(b"USER student\r\n")
                    self.assertTrue(reply(client).startswith("331"))
                    client.sendall(b"PASS cs494\r\n")
                    self.assertTrue(reply(client).startswith("230"))
                first.sendall(b"CWD one\r\n")
                self.assertTrue(reply(first).startswith("250"))
                second.sendall(b"CWD two\r\n")
                self.assertTrue(reply(second).startswith("250"))
                first.sendall(b"STAT\r\n")
                status = ""
                while not status.endswith("212 End\r\n"):
                    status += reply(first)
                self.assertIn("active_sessions=2", status)
                self.assertIn("cwd=/one", status)
                self.assertIn("cwd=/two", status)
                first.sendall(b"QUIT\r\n")
                second.sendall(b"QUIT\r\n")
                self.assertTrue(reply(first).startswith("221"))
                self.assertTrue(reply(second).startswith("221"))
            finally:
                first.close()
                second.close()
                server.stop()
                server.join()


if __name__ == "__main__":
    unittest.main()
