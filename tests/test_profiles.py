import os
import tempfile
import unittest
from pathlib import Path

from threadlens.paths import default_config_dir, default_data_dir
from threadlens.profiles import ProfileConfigError, SourceProfile, load_profiles, save_profiles
from threadlens.store import ThreadStore


class ProfileTests(unittest.TestCase):
    def test_default_paths_use_user_level_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)

            self.assertEqual(
                default_data_dir(home=home, environ={}, platform="linux"),
                home / ".local" / "share" / "threadlens",
            )
            self.assertEqual(
                default_config_dir(home=home, environ={}, platform="linux"),
                home / ".config" / "threadlens",
            )
            self.assertEqual(
                default_data_dir(home=home, environ={}, platform="darwin"),
                home / "Library" / "Application Support" / "threadlens",
            )

    def test_load_profiles_can_report_malformed_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "sources.json"
            config.write_text("{not valid json", encoding="utf-8")

            self.assertEqual(load_profiles(config), {})
            with self.assertRaises(ProfileConfigError) as caught:
                load_profiles(config, strict=True)

        self.assertIn("invalid JSON", str(caught.exception))

    @unittest.skipUnless(os.name == "posix", "POSIX file modes only")
    def test_thread_store_uses_private_file_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "data" / "index.sqlite"
            store = ThreadStore(db)
            store.close()

            self.assertEqual((db.parent.stat().st_mode & 0o777), 0o700)
            self.assertEqual((db.stat().st_mode & 0o777), 0o600)

    @unittest.skipUnless(os.name == "posix", "POSIX file modes only")
    def test_source_config_uses_private_file_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "config" / "sources.json"
            save_profiles({"demo": SourceProfile(name="demo", paths=["/tmp/demo.jsonl"])}, config)

            self.assertEqual((config.parent.stat().st_mode & 0o777), 0o700)
            self.assertEqual((config.stat().st_mode & 0o777), 0o600)


if __name__ == "__main__":
    unittest.main()
