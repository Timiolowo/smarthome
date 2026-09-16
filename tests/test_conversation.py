import contextlib
import io
import runpy
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.config import AppConfig
from src.voice_input import VoiceListener, ListenResult, strip_greeting, is_conversation_exit


class ConversationTests(unittest.TestCase):
    def test_wake_command_keeps_request(self):
        triggers = ['hey', 'hello', 'nova', 'good morning']
        self.assertEqual(strip_greeting('Hey, Nova, set a timer for 5 minutes.', triggers),
                         'set a timer for 5 minutes.')
        self.assertEqual(strip_greeting('Hey, hello.', triggers), '')
        self.assertEqual(strip_greeting('Good morning! What time is it?', triggers), 'What time is it?')

    def test_wake_words_do_not_match_inside_other_words(self):
        listener = VoiceListener.__new__(VoiceListener)
        listener.listen_once = Mock(return_value='something is wrong')
        self.assertIsNone(listener.wait_for_trigger(['hi']))
        listener.listen_once.return_value = 'Hi, Nova.'
        self.assertEqual(listener.wait_for_trigger(['hi']), 'Hi, Nova.')

    def test_stop_alarm_is_not_a_farewell(self):
        self.assertFalse(is_conversation_exit('stop the alarm', ['stop', 'bye']))
        self.assertFalse(is_conversation_exit('do not stop', ['stop']))
        self.assertTrue(is_conversation_exit('Stop.', ['stop']))

    def run_conversation(self, results, wakes):
        listener = Mock()
        listener.wait_for_trigger.side_effect = wakes
        iterator = iter(results)
        def listen(**kwargs):
            result = next(iterator)
            if isinstance(result, BaseException):
                raise result
            listener.last_result = result
            return result.text or None
        listener.listen_once.side_effect = listen
        listener.last_result = ListenResult()
        agent = Mock()
        agent.process_message.return_value = 'Done.'
        memory = Mock()
        memory.load_assistant.return_value = {'name': 'Nova'}
        speak = Mock(return_value=False)
        server = Mock()
        modules = {
            'src.config': SimpleNamespace(load_config=lambda: AppConfig()),
            'src.agent': SimpleNamespace(agent=agent),
            'src.brain': SimpleNamespace(brain=SimpleNamespace(available=False)),
            'src.memory': SimpleNamespace(memory=memory),
            'src.presence': SimpleNamespace(PresenceTracker=Mock()),
            'src.voice_output': SimpleNamespace(speak=speak, stop=Mock()),
            'src.web_server': SimpleNamespace(run_web_server=Mock(return_value=server)),
        }
        with patch.dict('sys.modules', modules), patch('src.voice_input.VoiceListener', return_value=listener):
            main = runpy.run_module('src.main', run_name='conversation_test')
            with contextlib.redirect_stdout(io.StringIO()):
                main['run_assistant'](simulate_presence=True, audio_loop=main['run_assistant_loop'])
        listener.close.assert_called_once()
        server.shutdown.assert_called_once()
        return agent, listener, speak

    def test_standby_routes_wake_command_and_alarm_cancellation(self):
        agent, listener, _ = self.run_conversation(
            [ListenResult(), ListenResult('speech', 'stop the alarm'), KeyboardInterrupt()],
            ['hello', 'hey, set a timer for 5 minutes'])
        self.assertEqual([call.args[0] for call in agent.process_message.call_args_list],
                         ['set a timer for 5 minutes', 'stop the alarm'])
        self.assertEqual(listener.listen_once.call_args.kwargs['timeout'], 30)

    def test_unclear_speech_recovers_without_wake_word_or_tool_execution(self):
        agent, listener, speak = self.run_conversation(
            [ListenResult('unclear'), ListenResult('unclear'),
             ListenResult('speech', 'set a timer for 5 minutes'), KeyboardInterrupt()], ['hello'])
        listener.wait_for_trigger.assert_called_once()
        agent.process_message.assert_called_once_with('set a timer for 5 minutes')
        prompts = [c.args[0] for c in speak.call_args_list if "didn't catch" in c.args[0]]
        self.assertEqual(len(prompts), 1)

    def test_device_failure_keeps_conversation_with_typed_input(self):
        agent, listener, _ = self.run_conversation(
            [ListenResult('error', message='Device disconnected'),
             ListenResult('speech', 'remember that I like tea'), KeyboardInterrupt()], ['hello'])
        self.assertFalse(listener.available)
        listener.wait_for_trigger.assert_called_once()
        agent.process_message.assert_called_once_with('remember that I like tea')


if __name__ == '__main__':
    unittest.main()
