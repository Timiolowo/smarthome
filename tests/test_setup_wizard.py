import json
import os
import unittest
from urllib.request import urlopen, Request
from urllib.error import HTTPError
import threading

from src.web_server import run_web_server
from src.downloader import downloader, MODEL_SPECS


class TestSetupWizard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Start web server on test port
        cls.port = 5892
        cls.server = run_web_server(host="127.0.0.1", port=cls.port, background=True)
        cls.base_url = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        if cls.server:
            cls.server.shutdown()

    def test_setup_page_served(self):
        url = f"{self.base_url}/setup"
        with urlopen(url) as resp:
            self.assertEqual(resp.status, 200)
            content = resp.read().decode("utf-8")
            self.assertIn("SmartHome AI Assistant", content)
            self.assertIn("Setup Wizard", content)

    def test_setup_status_api(self):
        url = f"{self.base_url}/api/setup/status"
        with urlopen(url) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertIn("models", data)
            self.assertIn("llm_3b", data["models"])
            self.assertIn("stt", data["models"])
            self.assertIn("tts", data["models"])

    def test_download_status_api(self):
        url = f"{self.base_url}/api/models/download-status"
        with urlopen(url) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertIn("state", data)
            self.assertIn("percent", data)

    def test_setup_save_api(self):
        url = f"{self.base_url}/api/setup/save"
        payload = {
            "user_name": "TestUser",
            "assistant_name": "Nova",
            "greeting_text": "Welcome home, TestUser!",
            "ai_mode": "local",
            "bio_notes": "Software engineer test context"
        }
        req = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("ok"))

    def test_is_first_time_setup(self):
        from src.setup_wizard import is_first_time_setup
        # Verify function executes without crashing
        result = is_first_time_setup()
        self.assertIsInstance(result, bool)


if __name__ == "__main__":
    unittest.main()
