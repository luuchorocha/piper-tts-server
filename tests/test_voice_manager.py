from pathlib import Path
import unittest

from src.managers.voices.manager import VoiceManager


class _UnavailableCatalog:
    default_model_id = "en_US-hfc_male-medium"
    default_model_path = Path("/models/en_US-hfc_male-medium.onnx")
    download_dir = Path("/models")
    allow_downloads = True

    def __init__(self) -> None:
        self.requests: list[str] = []

    def ensure_available(self, model_id: str):
        self.requests.append(model_id)
        return None


class VoiceManagerTest(unittest.TestCase):
    def test_requested_voice_not_available_does_not_fall_back_to_default(self):
        catalog = _UnavailableCatalog()
        manager = object.__new__(VoiceManager)
        manager.catalog = catalog

        with self.assertRaisesRegex(ValueError, "Voice not available: en_GB-cory-medium"):
            manager.get("en_GB-cory-medium")

        self.assertEqual(["en_GB-cory-medium"], catalog.requests)


if __name__ == "__main__":
    unittest.main()