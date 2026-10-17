"""Telegram alerts (app/telegram.py, D91): idle without keys, filters, cooldown, payload, escaping; never blocks or raises."""
import unittest

from app import telegram


class Telegram(unittest.TestCase):
    def test_selfcheck(self):
        telegram.selfcheck()                      # fake Bot API endpoint, no internet, no keys


if __name__ == "__main__":
    unittest.main()
