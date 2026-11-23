"""Scraper hardening tests. Run: python tests/test_scraper.py
No network, no Playwright needed.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.scraper import validate_asin  # noqa: E402


def test_valid_asin_accepted():
    assert validate_asin("B0DEMO1234") == "B0DEMO1234"
    assert validate_asin("b0demo5678") == "B0DEMO5678"  # lowercased + uppercased


def test_invalid_asin_rejected():
    for bad in ("B0SHORT", "B0TOOLONG123", "abc def ghij", "", "B0DEMO!234", "B0DEMO123 "):
        try:
            validate_asin(bad)
            raise AssertionError(f"should have raised ValueError for {bad!r}")
        except ValueError:
            pass


if __name__ == "__main__":
    test_valid_asin_accepted()
    print("[ok] valid ASINs accepted and normalised")
    test_invalid_asin_rejected()
    print("[ok] invalid ASINs rejected with ValueError")
    print("ALL SCRAPER TESTS PASSED")
