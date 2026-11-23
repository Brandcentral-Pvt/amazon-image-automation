"""Regression tests for Gemini as the default browser automation provider."""
from pathlib import Path
import unittest
from unittest.mock import patch

from src.config import Config, load_config
from src.browser import launch_gemini_context


class FakeChromium:
    def __init__(self):
        self.calls = []
        self.context = object()

    def launch_persistent_context(self, path, **kwargs):
        self.calls.append((path, kwargs))
        return self.context


class FakePlaywright:
    def __init__(self):
        self.chromium = FakeChromium()


class GeminiProfileTests(unittest.TestCase):
    def test_example_defaults_to_gemini_and_named_chrome_profile(self):
        cfg = load_config(str(Path(__file__).resolve().parent.parent / "config.example.yaml"))
        self.assertEqual(cfg.get("generation.provider"), "gemini")
        self.assertTrue(cfg.get("gemini.use_own_chrome_profile"))
        self.assertEqual(cfg.get("gemini.chrome_profile_name"), "Chirag")
        self.assertEqual(cfg.get("gemini.chrome_channel"), "chrome")

    @patch("src.browser.ensure_gemini_profile")
    def test_uses_resolved_profile_folder_not_display_name(self, ensure):
        ensure.return_value = (Path("C:/isolated-gemini"), "Profile 2")
        cfg = Config({"browser": {"viewport": {"width": 1440, "height": 900}},
                      "gemini": {"chrome_profile_name": "Chirag",
                                 "chrome_channel": "chrome"}})
        pw = FakePlaywright()
        context, browser = launch_gemini_context(pw, cfg, headless=False)
        self.assertIs(context, pw.chromium.context)
        self.assertIsNone(browser)
        path, kwargs = pw.chromium.calls[0]
        self.assertEqual(path, "C:/isolated-gemini")
        self.assertIn("--profile-directory=Profile 2", kwargs["args"])
        self.assertEqual(kwargs["channel"], "chrome")
        self.assertFalse(kwargs["headless"])

    @patch("src.browser.ensure_gemini_profile")
    def test_explicit_executable_is_respected(self, ensure):
        ensure.return_value = (Path("C:/isolated-gemini"), "Profile 4")
        cfg = Config({"gemini": {"chrome_profile_name": "Profile 4",
                                "chrome_executable_path": "C:/Chrome/chrome.exe"}})
        pw = FakePlaywright()
        launch_gemini_context(pw, cfg)
        self.assertEqual(pw.chromium.calls[0][1]["executable_path"], "C:/Chrome/chrome.exe")
        self.assertNotIn("channel", pw.chromium.calls[0][1])

    @patch("src.browser.launch_context")
    @patch("src.browser.ensure_gemini_profile")
    def test_isolated_profile_can_be_disabled(self, ensure, launch):
        ensure.return_value = None
        launch.return_value = ("shared-context", None)
        cfg = Config({"gemini": {"use_own_chrome_profile": False}})
        self.assertEqual(launch_gemini_context(FakePlaywright(), cfg), ("shared-context", None))
        launch.assert_called_once()


if __name__ == "__main__":
    unittest.main()
