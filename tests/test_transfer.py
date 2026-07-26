import tempfile
import threading
import unittest
from pathlib import Path

from hybridftp.rdt import new_transfer_id
from hybridftp.transfer import receive_file, send_file


class TransferTests(unittest.TestCase):
    def test_binary_transfer_uses_window_and_atomic_destination(self):
        payload = bytes(range(256)) * 20 + b"final\x00bytes"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.bin"
            destination = root / "nested" / "received.bin"
            source.write_bytes(payload)
            import socket

            receiver_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            receiver_socket.bind(("127.0.0.1", 0))
            sender_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            transfer_id = new_transfer_id()
            result_box = {}

            def receive():
                result_box["receive"] = receive_file(receiver_socket, None, destination, transfer_id, window_size=3)

            worker = threading.Thread(target=receive)
            worker.start()
            try:
                sent = send_file(sender_socket, receiver_socket.getsockname(), source, transfer_id, window_size=3)
            finally:
                worker.join(timeout=5)
                sender_socket.close()
                receiver_socket.close()
            self.assertFalse(worker.is_alive())
            received = result_box["receive"]
            self.assertEqual(destination.read_bytes(), payload)
            self.assertEqual(sent.sha256, received.sha256)
            self.assertEqual(sent.bytes_transferred, len(payload))
            self.assertGreater(sent.packets, 1)
            self.assertFalse(list(destination.parent.glob("*.part")))


if __name__ == "__main__":
    unittest.main()
