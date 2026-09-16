"""
Unit & integration tests for Priority 2: Agentic Nova.
Verifies hardware device grounding, Android bridge, OS platform adapters,
supervisor sleep/wake cycles, downtime tracking, routines, and undo stack.
"""

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from src.action_guards import action_guards
from src.agent import HomeAgent
from src.android_bridge import AndroidBridge
from src.device_inventory import DeviceInventory
from src.platform_adapter import MacOSAdapter, WindowsAdapter, LinuxAdapter
from src.routines import RoutineEngine
from src.supervisor import Supervisor


class TestAgenticNova(unittest.TestCase):

    # -------------------------------------------------------------
    # 1. HARDWARE DEVICE GROUNDING
    # -------------------------------------------------------------
    def test_unconnected_device_refusal(self):
        inv = DeviceInventory.__new__(DeviceInventory)
        inv.devices = {
            "lights": {"name": "Smart Lights", "connected": False},
            "ac": {"name": "Air Conditioner", "connected": False},
        }
        self.assertFalse(inv.is_connected("lights"))
        refusal = inv.get_grounded_refusal("smart lights", "turn on")
        self.assertIn("cannot turn on the smart lights", refusal)
        self.assertIn("don't have smart smart lights hardware connected", refusal)

    def test_connected_device_state(self):
        inv = DeviceInventory.__new__(DeviceInventory)
        inv.devices = {
            "lights": {"name": "Smart Lights", "connected": True},
        }
        self.assertTrue(inv.is_connected("lights"))

    # -------------------------------------------------------------
    # 2. ANDROID BRIDGE (ADB)
    # -------------------------------------------------------------
    def test_android_bridge_phone_status(self):
        bridge = AndroidBridge(adb_path="mock_adb")
        with patch.object(bridge, "is_available", return_value=True), \
             patch.object(bridge, "list_connected_devices", return_value=[
                 {"serial": "emulator-5554", "status": "device", "model": "Pixel 8", "authorized": True}
             ]), \
             patch("subprocess.run") as mock_sub:
            mock_sub.return_value = MagicMock(returncode=0, stdout="level: 85\nstatus: 2\n")
            status = bridge.get_phone_status()

            self.assertTrue(status["connected"])
            self.assertEqual(status["battery_percent"], 85)
            self.assertTrue(status["is_charging"])
            self.assertIn("Pixel 8", status["summary"])

    def test_android_bridge_call_intent(self):
        bridge = AndroidBridge(adb_path="mock_adb")
        with patch.object(bridge, "get_phone_status", return_value={
            "connected": True,
            "authorized": True,
            "device": {"serial": "12345", "model": "Pixel 8"},
        }), patch("subprocess.run") as mock_sub:
            mock_sub.return_value = MagicMock(returncode=0, stdout="")
            res = bridge.initiate_phone_call("555-0199")

            self.assertTrue(res["ok"])
            self.assertEqual(res["phone_number"], "5550199")
            self.assertIn("Calling 5550199", res["message"])

    # -------------------------------------------------------------
    # 3. CROSS-PLATFORM OS ADAPTERS
    # -------------------------------------------------------------
    def test_macos_battery_and_wifi_parsing(self):
        adapter = MacOSAdapter()
        with patch.object(adapter, "run_cmd", side_effect=lambda cmd, **kwargs: (
            "Now drawing from 'Battery Power'\n -InternalBattery-0 (id=123)	78%; discharging; 4:12 remaining"
            if "pmset" in cmd else
            "Current Wi-Fi Network: HomeNetwork_5G"
        )):
            batt = adapter.get_battery_status()
            wifi = adapter.get_wifi_status()

            self.assertTrue(batt["has_battery"])
            self.assertEqual(batt["percent"], 78)
            self.assertFalse(batt["is_charging"])

            self.assertTrue(wifi["connected"])
            self.assertEqual(wifi["ssid"], "HomeNetwork_5G")

    # -------------------------------------------------------------
    # 4. ACTION GUARDS & UNDO STACK
    # -------------------------------------------------------------
    def test_undo_stack_reverses_action(self):
        undone = []
        action_guards.undo_stack.clear()
        action_guards.push_undo("test_action", "create timer", lambda: (undone.append(True), True)[1])

        res = action_guards.pop_and_undo()
        self.assertTrue(res["ok"])
        self.assertIn("Undid: create timer", res["message"])
        self.assertEqual(len(undone), 1)

    def test_empty_undo_stack(self):
        action_guards.undo_stack.clear()
        res = action_guards.pop_and_undo()
        self.assertFalse(res["ok"])
        self.assertIn("nothing to undo", res["message"])

    # -------------------------------------------------------------
    # 5. SUPERVISOR & DOWNTIME TRACKING
    # -------------------------------------------------------------
    def test_supervisor_schedule_sleep_and_return_greeting(self):
        sv = Supervisor()
        with patch("src.system_power.system_power.power_off") as mock_power_off, \
             patch("src.memory.memory.save_state"):
            reply = sv.schedule_sleep_and_return(1800)
            self.assertIn("Shutting down and coming back online in 30.0 minutes", reply)
            mock_power_off.assert_called_once()
            self.assertIsNotNone(sv.sleep_timer)
            sv.cancel_sleep()

        greeting = sv.generate_return_greeting(1800)
        self.assertTrue(any(phrase in greeting for phrase in ("downtime", "back", "rest")))

    # -------------------------------------------------------------
    # 6. ROUTINES & COMPOUND COMMAND EXECUTION
    # -------------------------------------------------------------
    def test_decompose_compound_command(self):
        re_engine = RoutineEngine.__new__(RoutineEngine)
        sub_cmds = re_engine.decompose_compound_command("set a timer for 10 minutes and switch theme to emerald")
        self.assertEqual(sub_cmds, ["set a timer for 10 minutes", "switch theme to emerald"])

        single_cmd = re_engine.decompose_compound_command("what time is it")
        self.assertEqual(single_cmd, ["what time is it"])

    def test_execute_good_morning_routine(self):
        re_engine = RoutineEngine.__new__(RoutineEngine)
        re_engine.routines = RoutineEngine.DEFAULT_ROUTINES
        with patch("src.tools.tools.get_active_reminders_summary", return_value="You have no upcoming reminders scheduled right now."), \
             patch("src.tools.tools.set_ui_theme"):
            res = re_engine.execute_routine("good_morning")
            self.assertIn("Good morning", res)
            self.assertIn("Your schedule is clear today.", res)

    # -------------------------------------------------------------
    # 7. AGENT INTENT ROUTING (PRIORITY 2 COMMANDS)
    # -------------------------------------------------------------
    def test_agent_routes_priority_2_commands(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            hist_file = f.name
        try:
            agent = HomeAgent(history_file=hist_file)

            # Grounded lights refusal
            reply_lights = agent.process_message("turn on the lights")
            self.assertIn("cannot", reply_lights.lower())

            # Wi-Fi check
            with patch("src.tools.tools.get_wifi_info", return_value="Wi-Fi is connected to 'TestSSID'."):
                reply_wifi = agent.process_message("check wifi status")
                self.assertIn("TestSSID", reply_wifi)

            # Sleep command with duration
            with patch("src.tools.tools.schedule_sleep_and_return", return_value="Going to sleep for 20.0 minutes.") as mock_sleep:
                reply_sleep = agent.process_message("turn yourself off and return in 20 minutes")
                self.assertIn("Going to sleep", reply_sleep)
                mock_sleep.assert_called_once_with(1200.0)

            # Follow-up duration: "i said two minutes"
            with patch("src.tools.tools.schedule_sleep_and_return", return_value="Going to sleep for 2 minutes.") as mock_sleep2:
                reply_followup = agent.process_message("i said two minutes")
                self.assertIn("Going to sleep", reply_followup)
                mock_sleep2.assert_called_once_with(120.0)

            # Immediate shutdown command without duration
            with patch("src.system_power.system_power.power_off") as mock_power_off:
                reply_power = agent.process_message("shut down")
                self.assertIn("powering off", reply_power.lower())
                mock_power_off.assert_called_once()

            # Theme command
            with patch("src.tools.tools.set_ui_theme", return_value="Switched theme to Emerald."):
                reply_theme = agent.process_message("switch theme to emerald")
                self.assertIn("Switched theme to Emerald", reply_theme)

            # Phone call command
            with patch("src.tools.tools.make_phone_call", return_value="Calling Mom on your phone."):
                reply_call = agent.process_message("call Mom")
                self.assertIn("Calling Mom", reply_call)

            # 3D Visual Engine command
            with patch("src.tools.tools.set_visual_engine", return_value="Switched dashboard visual engine to 3D Particle Orb.") as mock_engine:
                reply_engine = agent.process_message("change to the 3d visual engine")
                self.assertIn("3D Particle Orb", reply_engine)
                mock_engine.assert_called_once_with("3d")

            # 2D Visual Engine command
            with patch("src.tools.tools.set_visual_engine", return_value="Switched dashboard visual engine to 2D Concentric Core.") as mock_engine2:
                reply_engine2 = agent.process_message("change to 2d visual engine")
                self.assertIn("2D Concentric Core", reply_engine2)
                mock_engine2.assert_called_once_with("2d")

            # Dashboard Tab navigation
            with patch("src.tools.tools.switch_dashboard_tab", return_value="Switched dashboard to Settings.") as mock_tab:
                reply_tab = agent.process_message("show settings tab")
                self.assertIn("Settings", reply_tab)
                mock_tab.assert_called_once_with("settings")

            # Undo command
            with patch("src.tools.tools.undo_last_action", return_value="Undid: setting alarm for 10 minutes."):
                reply_undo = agent.process_message("undo that")
                self.assertIn("Undid", reply_undo)

            # Timed shutdown and return commands
            with patch("src.tools.tools.schedule_sleep_and_return", return_value="Shutting down and coming back online in 5.0 minutes.") as mock_sleep:
                reply_sleep = agent.process_message("shut down and come online in five minutes")
                self.assertIn("Shutting down and coming back online in 5.0 minutes", reply_sleep)
                mock_sleep.assert_called_once_with(300.0)

            with patch("src.tools.tools.schedule_sleep_and_return", return_value="Shutting down and coming back online in 5.0 minutes.") as mock_sleep2:
                reply_sleep2 = agent.process_message("can you show down your system or combat online in five minutes?")
                self.assertIn("Shutting down and coming back online in 5.0 minutes", reply_sleep2)
                mock_sleep2.assert_called_once_with(300.0)

            # Weather and Location query
            with patch("src.tools.tools.get_weather_and_location", return_value="Current location: Lagos, Nigeria (Africa/Lagos). Weather: 28°C, Partly Cloudy.") as mock_weather:
                reply_weather = agent.process_message("what's the weather like?")
                self.assertIn("Lagos, Nigeria", reply_weather)
                mock_weather.assert_called_once()

        finally:
            if os.path.exists(hist_file):
                os.unlink(hist_file)


if __name__ == "__main__":
    unittest.main()
