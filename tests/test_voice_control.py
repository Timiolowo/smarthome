import threading
import unittest
from unittest.mock import patch

from src.system_power import SystemPowerManager
from src.voice_input import ListenResult, VoiceListener


class VoiceControlTests(unittest.TestCase):
    def test_terminal_voice_modes_are_reported(self):
        manager = SystemPowerManager()
        manager.mark_voice_loop_started()

        def apply(mode):
            acknowledgement = threading.Timer(.01, manager.acknowledge_voice_mode, args=(mode,))
            acknowledgement.start()
            result = manager.set_voice_mode(mode, timeout=1)
            acknowledgement.join()
            return result

        with patch('src.system_power.audio_runtime.publish'), \
             patch('src.system_power.memory.update_assistant_runtime'):
            self.assertEqual(apply('live')['voice_mode'], 'live')
            self.assertEqual(manager.status()['voice_mode'], 'live')
            self.assertEqual(apply('wake')['voice_mode'], 'wake')
            self.assertEqual(apply('off')['voice_mode'], 'off')

    def test_voice_control_rejects_commands_when_backend_is_not_running(self):
        manager = SystemPowerManager()
        result = manager.set_voice_mode('live')
        self.assertFalse(result['ok'])
        self.assertIn('not running', result['error'])

    def test_invalid_voice_mode_is_rejected(self):
        manager = SystemPowerManager()
        result = manager.set_voice_mode('browser')
        self.assertFalse(result['ok'])
        self.assertEqual(manager.voice_mode(), 'wake')

    def test_listener_honors_backend_control_event(self):
        listener = VoiceListener.__new__(VoiceListener)
        listener.last_result = ListenResult()
        event = threading.Event()
        event.set()
        self.assertIsNone(listener.listen_once(cancel_event=event))
        self.assertEqual(listener.last_result.status, 'cancelled')


if __name__ == '__main__':
    unittest.main()
