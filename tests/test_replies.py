import unittest

from hybridftp.replies import format_reply, multiline, single


class ReplyFormattingTests(unittest.TestCase):
    def test_single_reply_uses_crlf(self):
        self.assertEqual(
            format_reply(single(220, "Hybrid FTP server ready")),
            b"220 Hybrid FTP server ready\r\n",
        )

    def test_multiline_reply_uses_ftp_framing(self):
        encoded = format_reply(multiline(214, ["Commands:"], "End of help"))
        self.assertIn(b"214-Commands:\r\n", encoded)
        self.assertTrue(encoded.endswith(b"214 End of help\r\n"))


if __name__ == "__main__":
    unittest.main()
