from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from kau_can_bot.branding import prepare_branding_assets


class BrandingTests(unittest.TestCase):
    def test_logo_is_copied_from_desktop_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as root_dir, tempfile.TemporaryDirectory() as desktop_dir:
            desktop_logo = Path(desktop_dir) / "KAU_LOGO.png"
            desktop_logo.write_bytes(b"fake-logo")

            state = prepare_branding_assets(Path(root_dir), Path(desktop_dir))

            self.assertEqual(state.logo_url, "/static/assets/kau_logo.png")
            self.assertTrue((Path(root_dir) / "static/assets/kau_logo.png").exists())

    def test_missing_logo_keeps_safe_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as root_dir, tempfile.TemporaryDirectory() as desktop_dir:
            state = prepare_branding_assets(Path(root_dir), Path(desktop_dir))

            self.assertIsNone(state.logo_url)
            self.assertIsNone(state.logo_path)


if __name__ == "__main__":
    unittest.main()
