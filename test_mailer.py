import unittest
from pathlib import Path

from mailer import SmtpSettings, build_message, parse_recipients, suggested_smtp


class MailerTests(unittest.TestCase):
    def test_parse_recipients_deduplicates_and_identifies_invalid_lines(self) -> None:
        recipients, invalid = parse_recipients("alice@example.com\nBAD\nALICE@example.com\nbob@example.net\n")
        self.assertEqual(recipients, ["alice@example.com", "bob@example.net"])
        self.assertEqual(invalid, ["BAD"])

    def test_suggests_known_smtp_configuration(self) -> None:
        self.assertEqual(suggested_smtp("person@qq.com"), SmtpSettings("smtp.qq.com", 465, "SSL"))
        self.assertEqual(suggested_smtp("person@outlook.com"), SmtpSettings("smtp.office365.com", 587, "STARTTLS"))
        self.assertIsNone(suggested_smtp("person@company.example"))

    def test_message_has_exactly_one_visible_recipient(self) -> None:
        message = build_message("sender@example.com", "only@example.com", "Subject", "Body", [])
        self.assertEqual(message["To"], "only@example.com")
        self.assertIsNone(message["Cc"])
        self.assertIsNone(message["Bcc"])


if __name__ == "__main__":
    unittest.main()

