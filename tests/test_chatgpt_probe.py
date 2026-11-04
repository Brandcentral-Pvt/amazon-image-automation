"""Deterministic tests for the read-only ChatGPT UI probe."""
import unittest
from src.chatgpt_probe import _recommend, _candidate_score, STAGES, JS_INSPECT


class ProbeTest(unittest.TestCase):
    def test_recommends_visible_semantic_selectors(self):
        elements = [
            {"tag": "div", "selector": "#prompt-textarea", "contenteditable": True, "inForm": True, "visible": True},
            {"tag": "button", "selector": 'button[data-testid="composer-plus-btn"]',
             "testid": "composer-plus-btn", "visible": True},
            {"tag": "input", "selector": 'input[type="file"]', "type": "file", "visible": False},
            {"tag": "button", "selector": 'button[aria-label="Send prompt"]',
             "aria": "Send prompt", "visible": True},
            {"tag": "button", "selector": 'button[aria-label="Download"]',
             "aria": "Download", "visible": True},
        ]
        suggestions = _recommend(elements)
        self.assertEqual(suggestions["composer"][0]["selector"], "#prompt-textarea")
        self.assertIn("composer-plus-btn", suggestions["attach_button"][0]["selector"])
        self.assertEqual(suggestions["file_input"][0]["selector"], 'input[type="file"]')
        self.assertIn("Send prompt", suggestions["send_button"][0]["selector"])
        self.assertIn("Download", suggestions["download_button"][0]["selector"])

    def test_absent_candidates_do_not_get_guessed(self):
        result = _recommend([])
        self.assertTrue(all(not items for items in result.values()))

    def test_probe_is_observational(self):
        self.assertGreaterEqual(len(STAGES), 4)
        self.assertNotIn("document.cookie", JS_INSPECT)
        self.assertNotIn("localStorage", JS_INSPECT)
        self.assertNotIn("outerHTML", JS_INSPECT)
        self.assertNotIn("innerHTML", JS_INSPECT)
        self.assertNotIn("fetch(", JS_INSPECT)


if __name__ == "__main__":
    unittest.main()
