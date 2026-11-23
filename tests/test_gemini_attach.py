"""Gemini attach-to-existing-Chrome mode regression tests."""
import unittest
from unittest.mock import Mock, patch

from src.browser import _gemini_cdp_endpoint, launch_gemini_context
from src.config import Config


class GeminiAttachTests(unittest.TestCase):
    def test_only_local_cdp_allowed(self):
        cfg = Config({"gemini": {"cdp_url": "http://127.0.0.1:9222"}})
        self.assertEqual(_gemini_cdp_endpoint(cfg), "http://127.0.0.1:9222")
        for endpoint in ("http://example.com:9222", "http://0.0.0.0:9222",
                         "https://127.0.0.1:9222", "http://127.0.0.1:9222/other"):
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                _gemini_cdp_endpoint(Config({"gemini": {"cdp_url": endpoint}}))

    def test_no_debug_connection_does_not_launch_chrome(self):
        pw = Mock()
        pw.chromium.connect_over_cdp.side_effect = OSError("connection refused")
        cfg = Config({"gemini": {"browser_mode": "existing", "cdp_url": "http://127.0.0.1:9222"}})
        with self.assertRaisesRegex(RuntimeError, "No new Chrome was launched"):
            launch_gemini_context(pw, cfg, headless=False)
        pw.chromium.launch_persistent_context.assert_not_called()

    def test_attach_returns_existing_context_without_launch(self):
        pw = Mock()
        browser = Mock()
        context = Mock()
        browser.contexts = [context]
        pw.chromium.connect_over_cdp.return_value = browser
        cfg = Config({"gemini": {"browser_mode": "existing", "cdp_url": "http://127.0.0.1:9222"}})
        result = launch_gemini_context(pw, cfg, headless=False)
        self.assertEqual(result, (context, browser))
        pw.chromium.connect_over_cdp.assert_called_once_with("http://127.0.0.1:9222", timeout=10000)
        pw.chromium.launch_persistent_context.assert_not_called()

    def test_missing_cdp_endpoint_never_launches(self):
        pw = Mock()
        with self.assertRaisesRegex(RuntimeError, "requires gemini.cdp_url"):
            launch_gemini_context(pw, Config({"gemini": {"browser_mode": "existing"}}))
        pw.chromium.launch_persistent_context.assert_not_called()

    @patch("src.browser.ensure_gemini_profile")
    def test_isolated_mode_requires_explicit_opt_in(self, ensure):
        ensure.return_value = ("C:/profile-copy", "Profile 2")
        pw = Mock()
        cfg = Config({"gemini": {"browser_mode": "isolated", "chrome_channel": "chrome"}})
        launch_gemini_context(pw, cfg, headless=False)
        pw.chromium.launch_persistent_context.assert_called_once()


if __name__ == "__main__":
    unittest.main()
