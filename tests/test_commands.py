import unittest

from hybridftp.commands import ParseError, help_reply, is_protected_placeholder, parse_control_line
from hybridftp.replies import format_reply


class CommandParsingTests(unittest.TestCase):
    def test_uppercases_verb_and_preserves_argument(self):
        command = parse_control_line(b"user student\r\n")
        self.assertEqual(command.verb, "USER")
        self.assertEqual(command.argument, "student")

    def test_accepts_lf_and_preserves_topic(self):
        command = parse_control_line(b"HELP USER\n")
        self.assertEqual(command.verb, "HELP")
        self.assertEqual(command.argument, "USER")

    def test_rejects_overlong_line(self):
        with self.assertRaises(ParseError):
            parse_control_line(b"X" * 1025 + b"\r\n")

    def test_rejects_undecodable_bytes(self):
        with self.assertRaises(ParseError):
            parse_control_line(b"USER \xff\r\n")

    def test_protected_placeholder_membership(self):
        self.assertTrue(is_protected_placeholder("LIST"))
        self.assertTrue(is_protected_placeholder("HASH"))
        self.assertFalse(is_protected_placeholder("NOOP"))

    def test_help_user_text(self):
        encoded = format_reply(help_reply("USER")).decode("utf-8")
        self.assertIn("214-USER <username>", encoded)
        self.assertTrue(encoded.endswith("214 End of help\r\n"))


if __name__ == "__main__":
    unittest.main()
