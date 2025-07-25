import json
import os
from typing import List, Dict


class PresetManager:
    def __init__(self):
        self.filepath = "presets.json"
        self.presets: List[Dict] = self._load_presets()

    def _get_default_preset(self) -> Dict:
        return {
            "name": "default",
            "isActive": True,
            "CLIP_DURATION_S": os.getenv("CLIP_DURATION_S", "1"),
            "INTER_TRANSITION_S": os.getenv("INTER_TRANSITION_S", "60"),
            "INTRA_TRANSITION_S": os.getenv("INTRA_TRANSITION_S", "60"),
            "CLIPS_PER_FILE": os.getenv("CLIPS_PER_FILE", "1"),
            "INTRA_FILE_MIN_GAP_S": os.getenv("INTRA_FILE_MIN_GAP_S", "5"),
            "INTRA_FILE_MAX_PERCENT": os.getenv("INTRA_FILE_MAX_PERCENT", "80"),
        }

    def _load_presets(self) -> List[Dict]:
        """Attempt to load presets from file. Fallback to default if file is missing or invalid."""
        try:
            with open(self.filepath, "r") as f:
                data = json.load(f)
                if isinstance(data, list) and data:
                    return data
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        return [self._get_default_preset()]

    def refresh_presets(self):
        """Reload presets from the file (e.g., if it was externally modified)."""
        self.presets = self._load_presets()

    def get_presets(self) -> List[Dict]:
        """Return the current list of presets."""
        return self.presets

    def get_active_preset(self) -> Dict:
        """Return the first active preset, or fallback to default if none are active."""
        for preset in self.presets:
            if preset.get("isActive"):
                return preset
        return self._get_default_preset()

    def set_presets(self, new_presets: List[Dict]):
        """Replace current presets and write them to file."""
        self.presets = new_presets
        with open(self.filepath, "w") as f:
            json.dump(self.presets, f, indent=4)
