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
            "CLIP_DURATION_S": os.getenv("CLIP_DURATION_S", "60"),
            "INTER_TRANSITION_S": os.getenv("INTER_TRANSITION_S", "2"),
            "INTRA_TRANSITION_S": os.getenv("INTRA_TRANSITION_S", "0"),
            "CLIPS_PER_FILE": os.getenv("CLIPS_PER_FILE", "1"),
            "INTRA_FILE_MIN_GAP_S": os.getenv("INTRA_FILE_MIN_GAP_S", "5"),
            "INTRA_FILE_MAX_PERCENT": os.getenv("INTRA_FILE_MAX_PERCENT", "80"),

            "FONT_SIZE": os.getenv("FONT_SIZE", "8"),
            "WIDTH": os.getenv("WIDTH", "1280"),
            "HEIGHT": os.getenv("HEIGHT", "720"),
            "X_CROP_PERCENT": os.getenv("X_CROP_PERCENT", "0"),
            "Y_CROP_PERCENT": os.getenv("Y_CROP_PERCENT", "0"),
            "PREROLL_S": os.getenv("PREROLL_S", "0.5"),
            "POSTROLL_S": os.getenv("POSTROLL_S", "0.5"),

            "EXCLUDE_STARTSWITH_CSV": os.getenv("EXCLUDE_STARTSWITH_CSV", ""),
            "EXCLUDE_CONTAINS_CSV": os.getenv("EXCLUDE_CONTAINS_CSV", ""),
            "EXCLUDE_NOTSTARTSWITH_CSV": os.getenv("EXCLUDE_NOTSTARTSWITH_CSV", ""),
            "EXCLUDE_NOTCONTAINS_CSV": os.getenv("EXCLUDE_NOTCONTAINS_CSV", ""),
            
            "BOOSTED_STARTSWITH_CSV": os.getenv("BOOSTED_STARTSWITH_CSV", ""),
            "BOOSTED_CONTAINS_CSV": os.getenv("BOOSTED_CONTAINS_CSV", ""),
            "BOOSTED_NOTSTARTSWITH_CSV": os.getenv("BOOSTED_NOTSTARTSWITH_CSV", ""),
            "BOOSTED_NOTCONTAINS_CSV": os.getenv("BOOSTED_NOTCONTAINS_CSV", ""),

            "SUPPRESSED_STARTSWITH_CSV": os.getenv("SUPPRESSED_STARTSWITH_CSV", ""),
            "SUPPRESSED_CONTAINS_CSV": os.getenv("SUPPRESSED_CONTAINS_CSV", ""),
            "SUPPRESSED_NOTSTARTSWITH_CSV": os.getenv("SUPPRESSED_NOTSTARTSWITH_CSV", ""),
            "SUPPRESSED_NOTCONTAINS_CSV": os.getenv("SUPPRESSED_NOTCONTAINS_CSV", ""),

            "BOOSTED_FACTOR": os.getenv("BOOSTED_FACTOR", "2"),
            "SUPPRESSED_FACTOR": os.getenv("SUPPRESSED_FACTOR", "2"),
        }

    def _load_presets(self) -> List[Dict]:
        """Attempt to load presets from file. Fallback to default if file is missing or invalid."""
        try:
            with open(self.filepath, "r") as f:
                data = json.load(f)
                if isinstance(data, list) and data:
                    print("successfully loaded presets.json")
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
