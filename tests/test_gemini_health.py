"""Gemini web driver health check tests. Run: python tests/test_gemini_health.py
No network, no Playwright needed.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import Config  # noqa: E402
from src.gemini_web import GeminiWeb  # noqa: E402


class MockLocator:
    def __init__(self, visible: bool, present: bool = True):
        self._visible = visible
        self._present = present

    def count(self):
        return 1 if self._present else 0

    @property
    def first(self):
        return self

    def is_visible(self, timeout=1000):
        return self._visible


class MockPage:
    def __init__(self, visible_map=None):
        # selector substring -> whether it's visible on the page
        self.visible_map = dict(visible_map or {})
        self.url = "https://gemini.google.com/app"

    def locator(self, sel):
        visible = any(sub in sel for sub, vis in self.visible_map.items() if vis)
        present = any(sub in sel for sub in self.visible_map)
        return MockLocator(visible=visible, present=present)


def make_gem(cfg_overrides=None, visible_map=None):
    base = {
        "amazon": {"domain": "amazon.in"},
        "output": {"root": "output"},
        "gemini": {
            "url": "https://gemini.google.com/app",
            "selectors": {
                "prompt_box": 'div[contenteditable="true"][role="textbox"]',
                "send_button": 'button[aria-label*="Send"]',
                "file_input": 'input[type="file"]',
                "generated_image": "model-response img",
            },
        },
    }
    if cfg_overrides:
        for k, v in cfg_overrides.items():
            base[k] = v
    cfg = Config(base)
    page = MockPage(visible_map)
    gem = GeminiWeb.__new__(GeminiWeb)
    gem.cfg = cfg
    gem.page = page
    return gem


def test_health_check_all_selectors_present():
    gem = make_gem(
        visible_map={
            'div[contenteditable="true"][role="textbox"]': True,
            'button[aria-label*="Send"]': True,
            'input[type="file"]': True,
        }
    )
    result = gem.health_check()
    assert result["healthy"] is True, result
    assert result["missing"] == [], result
    assert "prompt_box" in result["checked"]


def test_health_check_missing_send_button():
    gem = make_gem(
        visible_map={
            'div[contenteditable="true"][role="textbox"]': True,
            # send_button deliberately absent
            'input[type="file"]': True,
        }
    )
    result = gem.health_check()
    assert result["healthy"] is False, result
    assert "send_button" in result["missing"], result


def test_health_check_prompt_box_not_visible():
    gem = make_gem(
        visible_map={
            'div[contenteditable="true"][role="textbox"]': False,  # present but hidden
            'button[aria-label*="Send"]': True,
            'input[type="file"]': True,
        }
    )
    result = gem.health_check()
    assert result["healthy"] is False, result
    assert "prompt_box" in result["missing"], result


def test_health_check_file_input_hidden_ok():
    # file_input doesn't need to be visible - just present in DOM
    gem = make_gem(
        visible_map={
            'div[contenteditable="true"][role="textbox"]': True,
            'button[aria-label*="Send"]': True,
            'input[type="file"]': False,  # hidden input - still counts as present
        }
    )
    result = gem.health_check()
    assert result["healthy"] is True, result


def test_health_check_selector_not_configured():
    cfg_overrides = {
        "gemini": {
            "url": "https://gemini.google.com/app",
            "selectors": {},  # no selectors configured at all
        }
    }
    gem = make_gem(cfg_overrides=cfg_overrides)
    result = gem.health_check()
    assert result["healthy"] is False, result
    assert "prompt_box" in result["missing"]
    assert "send_button" in result["missing"]
    assert "file_input" in result["missing"]


if __name__ == "__main__":
    test_health_check_all_selectors_present()
    print("[ok] health_check: all selectors present -> healthy")
    test_health_check_missing_send_button()
    print("[ok] health_check: missing send_button -> unhealthy")
    test_health_check_prompt_box_not_visible()
    print("[ok] health_check: prompt_box hidden -> unhealthy")
    test_health_check_file_input_hidden_ok()
    print("[ok] health_check: hidden file_input still OK (present in DOM)")
    test_health_check_selector_not_configured()
    print("[ok] health_check: no selectors configured -> unhealthy")
    print("ALL GEMINI HEALTH TESTS PASSED")
