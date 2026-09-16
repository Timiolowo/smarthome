import unittest
from src.terminal_logger import terminal_logger


class TestTerminalLogger(unittest.TestCase):
    def setUp(self):
        terminal_logger.clear()

    def test_log_append_and_categorization(self):
        terminal_logger.append('🎤 [Heard]: "what time is it"')
        terminal_logger.append('🤖 [Nova]: "It is 12:20 PM on Wednesday, September 16."')
        terminal_logger.append('🛑 [System Power]: Assistant Core Powered OFF via Voice Hub.')
        terminal_logger.append('⚡ [System Power]: Assistant Core Powered ON!')
        terminal_logger.append('👉 [Command]: "turn off light"')
        terminal_logger.append('❌ [Error]: Audio stream underflow', level='error')

        logs = terminal_logger.get_logs(limit=10)
        self.assertEqual(len(logs), 6)
        self.assertEqual(logs[0]["type"], "heard")
        self.assertEqual(logs[1]["type"], "assistant")
        self.assertEqual(logs[2]["type"], "power_off")
        self.assertEqual(logs[3]["type"], "power_on")
        self.assertEqual(logs[4]["type"], "command")
        self.assertEqual(logs[5]["type"], "error")

    def test_log_since_id(self):
        terminal_logger.append('Line 1')
        terminal_logger.append('Line 2')
        logs = terminal_logger.get_logs(limit=10)
        last_id = logs[-1]["id"]
        terminal_logger.append('Line 3')
        new_logs = terminal_logger.get_logs(since_id=last_id)
        self.assertEqual(len(new_logs), 1)
        self.assertEqual(new_logs[0]["text"], "Line 3")

    def test_clear_logs(self):
        terminal_logger.append('Sample line')
        self.assertTrue(len(terminal_logger.get_logs()) > 0)
        terminal_logger.clear()
        self.assertEqual(len(terminal_logger.get_logs()), 0)


if __name__ == "__main__":
    unittest.main()
