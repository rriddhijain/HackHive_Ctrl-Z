"""WhatsApp alerts (app/whatsapp.py, D90): idle without keys, filters, cooldown, payload, pacing; never blocks or raises."""
import unittest

from app import whatsapp


class WhatsApp(unittest.TestCase):
    def test_selfcheck(self):
        whatsapp.selfcheck()                      # fake Cloud API endpoint, no internet, no keys


if __name__ == "__main__":
    unittest.main()
