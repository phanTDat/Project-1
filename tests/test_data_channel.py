import unittest

from hybridftp.data_channel import DataChannelError, Endpoint, format_passive_reply, parse_passive_reply, parse_port_argument


class DataChannelTests(unittest.TestCase):
    def test_port_round_trip_and_peer_guard(self):
        endpoint = parse_port_argument("127,0,0,1,195,80", control_peer_host="127.0.0.1")
        self.assertEqual(endpoint, Endpoint("127.0.0.1", 50_000))
        self.assertEqual(parse_passive_reply(format_passive_reply(endpoint)), endpoint)

    def test_bad_or_unsafe_endpoints_are_rejected(self):
        for text in ["127,0,0,1,1", "127,0,0,1,0,0", "127,0,0,1,256,1", "8,8,8,8,1,1"]:
            with self.subTest(text=text):
                with self.assertRaises(DataChannelError):
                    parse_port_argument(text, control_peer_host="127.0.0.1")
        with self.assertRaises(DataChannelError):
            parse_port_argument("127,0,0,2,1,1", control_peer_host="127.0.0.1")


if __name__ == "__main__":
    unittest.main()
