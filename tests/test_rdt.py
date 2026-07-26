import unittest

from hybridftp.rdt import (
    DEFAULT_WINDOW,
    FLAG_ACK,
    FLAG_DATA,
    HEADER_SIZE,
    MAX_PAYLOAD,
    Packet,
    PacketError,
    ack_packet,
    data_packet,
    fin_packet,
)


class RDTPacketTests(unittest.TestCase):
    def test_data_round_trip_preserves_all_header_fields(self):
        original = data_packet(123, 7, b"binary\x00payload", window=3)
        datagram = original.encode()
        decoded = Packet.decode(datagram)
        self.assertEqual(decoded, original)
        self.assertEqual(len(datagram), HEADER_SIZE + len(original.payload))
        self.assertEqual(decoded.flags, FLAG_DATA)

    def test_ack_and_fin_packets_are_valid_control_packets(self):
        ack = ack_packet(99, 12, window=4)
        self.assertEqual(Packet.decode(ack.encode()).flags, FLAG_ACK)
        self.assertEqual(Packet.decode(fin_packet(99, 13).encode()).sequence, 13)

    def test_checksum_and_length_tampering_are_rejected(self):
        datagram = bytearray(data_packet(5, 0, b"safe").encode())
        datagram[-1] ^= 0xFF
        with self.assertRaises(PacketError):
            Packet.decode(bytes(datagram))
        with self.assertRaises(PacketError):
            Packet.decode(b"too short")

    def test_invalid_packets_are_rejected(self):
        with self.assertRaises(PacketError):
            data_packet(0, 0, b"payload").encode()
        with self.assertRaises(PacketError):
            data_packet(1, 0, b"x" * (MAX_PAYLOAD + 1)).encode()
        with self.assertRaises(PacketError):
            Packet(FLAG_DATA | FLAG_ACK, 1, payload=b"x").encode()
        with self.assertRaises(PacketError):
            Packet(FLAG_ACK, 1, payload=b"x").encode()

    def test_default_window_is_explicit(self):
        self.assertEqual(Packet.decode(data_packet(1, 0, b"x").encode()).window, DEFAULT_WINDOW)


if __name__ == "__main__":
    unittest.main()
