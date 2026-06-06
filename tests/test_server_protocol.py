import logging
import unittest
from pathlib import Path

from hybridftp.commands import Command
from hybridftp.server import handle_command, sanitize_command_for_log
from hybridftp.session import Session


class ListHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


class ServerProtocolTests(unittest.TestCase):
    def make_session(self):
        return Session(session_id=1, client_address=("127.0.0.1", 9999), server_root=Path.cwd().resolve())

    def make_logger(self):
        logger = logging.getLogger(f"test.hybridftp.{id(self)}")
        logger.handlers.clear()
        logger.setLevel(logging.INFO)
        handler = ListHandler()
        logger.addHandler(handler)
        logger.propagate = False
        return logger, handler

    def test_sanitize_pass(self):
        self.assertEqual(sanitize_command_for_log(Command("PASS", "cs494")), "PASS ********")

    def test_auth_flow_and_placeholders(self):
        session = self.make_session()
        logger, _ = self.make_logger()
        reply, close = handle_command(session, Command("USER", "student"), logger)
        self.assertEqual(reply.code, 331)
        self.assertFalse(close)
        self.assertEqual(session.pending_username, "student")

        bad = self.make_session()
        reply, _ = handle_command(bad, Command("USER", "nobody"), logger)
        self.assertEqual(reply.code, 530)
        self.assertIsNone(bad.pending_username)

        seq = self.make_session()
        reply, _ = handle_command(seq, Command("PASS", "cs494"), logger)
        self.assertEqual(reply.code, 503)

        reply, _ = handle_command(session, Command("PASS", "wrong"), logger)
        self.assertEqual(reply.code, 530)
        self.assertFalse(session.authenticated)
        self.assertIsNone(session.pending_username)

        reply, _ = handle_command(session, Command("USER", "student"), logger)
        self.assertEqual(reply.code, 331)
        reply, _ = handle_command(session, Command("PASS", "cs494"), logger)
        self.assertEqual(reply.code, 230)
        self.assertTrue(session.authenticated)
        self.assertEqual(session.username, "student")
        self.assertIsNone(session.pending_username)

        preauth = self.make_session()
        reply, _ = handle_command(preauth, Command("LIST", ""), logger)
        self.assertEqual(reply.code, 530)
        reply, _ = handle_command(session, Command("LIST", ""), logger)
        self.assertEqual(reply.code, 502)

    def test_noop_quit_unknown_and_password_logs(self):
        session = self.make_session()
        logger, handler = self.make_logger()
        reply, close = handle_command(session, Command("NOOP", ""), logger)
        self.assertEqual(reply.code, 200)
        self.assertFalse(close)
        reply, close = handle_command(session, Command("QUIT", ""), logger)
        self.assertEqual(reply.code, 221)
        self.assertTrue(close)
        reply, _ = handle_command(session, Command("BOGUS", ""), logger)
        self.assertEqual(reply.code, 500)

        session = self.make_session()
        handle_command(session, Command("USER", "student"), logger)
        handle_command(session, Command("PASS", "cs494"), logger)
        handle_command(session, Command("USER", "student"), logger)
        handle_command(session, Command("PASS", "wrong"), logger)
        logs = "\n".join(handler.messages)
        self.assertIn("PASS ********", logs)
        self.assertNotIn("cs494", logs)
        self.assertNotIn("wrong", logs)


if __name__ == "__main__":
    unittest.main()
