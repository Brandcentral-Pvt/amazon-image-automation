"""Offline regression tests for ChatGPT image capture and provider selection."""
import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from src.chatgpt_web import ChatGPTWeb, ChatGPTError
from src.config import Config


def make_image(size=(1200, 1600), fmt="JPEG", color=(90, 20, 120)):
    out = io.BytesIO()
    Image.new("RGB", size, color).save(out, format=fmt)
    return out.getvalue()


class ChatGPTImageTests(unittest.TestCase):
    def setUp(self):
        self.driver = ChatGPTWeb(Config({"chatgpt": {"image_check": {
            "min_long_side_px": 1000, "aspect_tolerance": 0.07
        }}}))

    def test_decodable_image_reencoded_as_png(self):
        result = self.driver._validated_image(make_image(), Path("out.png"))
        with Image.open(io.BytesIO(result)) as img:
            self.assertEqual(img.format, "PNG")
            self.assertEqual(img.size, (1200, 1600))

    def test_rejects_corrupt_payload(self):
        with self.assertRaises(ChatGPTError):
            self.driver._validated_image(b"<html>not an image</html>" * 1000, Path("out.png"))

    def test_rejects_landscape(self):
        with self.assertRaises(ChatGPTError):
            self.driver._validated_image(make_image((1600, 900)), Path("out.png"))

    def test_rejects_small_image(self):
        with self.assertRaises(ChatGPTError):
            self.driver._validated_image(make_image((300, 400)), Path("out.png"))

    def test_accepts_studio_panel_ratio(self):
        self.driver._validated_image(make_image((1600, 1920)), Path("out.png"))

    def test_rejects_repeat_and_reference_echo(self):
        raw = make_image()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.driver._save_candidate(raw, root / "first.png")
            with self.assertRaisesRegex(ChatGPTError, "earlier generated slot"):
                self.driver._save_candidate(raw, root / "second.png")
            fresh = ChatGPTWeb(self.driver.cfg)
            fresh._reference_hashes.add(fresh._content_fingerprint(raw))
            with self.assertRaisesRegex(ChatGPTError, "uploaded reference"):
                fresh._save_candidate(raw, root / "echo.png")

    def test_composer_and_upload_fallbacks(self):
        self.assertIn('#prompt-textarea[contenteditable="true"]', self.driver._prompt_candidates())
        self.assertTrue(any('div.ProseMirror' in item for item in self.driver._prompt_candidates()))
        self.assertTrue(any('xpath=' in item for item in self.driver._attach_candidates()))
        self.assertTrue(any('xpath=' in item for item in self.driver._menu_item_candidates()))

    def test_missing_or_duplicate_reference_is_not_marked_valid(self):
        raw = make_image()
        fingerprint = self.driver._content_fingerprint(raw)
        self.driver._reference_hashes.add(fingerprint)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ChatGPTError):
                self.driver._save_candidate(raw, Path(directory) / "bad.png")


if __name__ == "__main__":
    unittest.main()
