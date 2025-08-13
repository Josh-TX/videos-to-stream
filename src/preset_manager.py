import json
import os
from typing import List, Dict


class PresetManager:
    def __init__(self):
        self.filepath = "/metadata/presets.json"
        self.presets: List[Dict] = self._load_presets()

    def _get_default_preset(self) -> Dict:
        return {
            "name": "default",
            "isActive": True,
            "CLIP_DURATION_S": os.getenv("CLIP_DURATION_S", "60"),
            "CLIP_DURATION_MAX_PERCENT": os.getenv("CLIP_DURATION_MAX_PERCENT", "100"),
            "CLIP_DURATION_MIN_S": os.getenv("CLIP_DURATION_MIN_S", "5"),
            "INTER_TRANSITION_S": os.getenv("INTER_TRANSITION_S", "2"),
            "INTRA_TRANSITION_S": os.getenv("INTRA_TRANSITION_S", "0"),
            "CLIPS_PER_FILE": os.getenv("CLIPS_PER_FILE", "1"),
            "INTRA_FILE_MIN_GAP_S": os.getenv("INTRA_FILE_MIN_GAP_S", "8"),
            "CLIPS_PER_FILE_MAX_PERCENT": os.getenv("CLIPS_PER_FILE_MAX_PERCENT", "80"),

            "BASE_DIRECTORY": os.getenv("BASE_DIRECTORY", ""),

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

            "FONT_SIZE": os.getenv("FONT_SIZE", "8"),
            "WIDTH": os.getenv("WIDTH", "1280"),
            "HEIGHT": os.getenv("HEIGHT", "720"),
            "FRAME_RATE": os.getenv("FRAME_RATE", "30"),
            "X_CROP_PERCENT": os.getenv("X_CROP_PERCENT", "0"),
            "Y_CROP_PERCENT": os.getenv("Y_CROP_PERCENT", "0"),

            "AUTO_PAUSE_S": os.getenv("AUTO_PAUSE_S", "60"),
            "PREROLL_S": os.getenv("PREROLL_S", "0.5"),
            "POSTROLL_S": os.getenv("POSTROLL_S", "0.5"),
            "FORCE_CLEANUP_S": os.getenv("FORCE_CLEANUP_S", "2"),
            "HLS_SEG_DURATION_S": os.getenv("HLS_SEG_DURATION_S", "4"),
            "HLS_SEG_COUNT": os.getenv("HLS_SEG_COUNT", "8"),
            "HLS_SEG_EXTRACOUNT": os.getenv("HLS_SEG_EXTRACOUNT", "5")
        }
    def _load_presets(self) -> List[Dict]:
        """Attempt to load presets from file. Fallback to default if file is missing or invalid."""
        if not os.path.exists(self.filepath):
            return [self._get_default_preset()]
        try:
            with open(self.filepath, "r") as f:
                data = json.load(f)
                
                # Check if data is a list
                if not isinstance(data, list):
                    print("presets.json is not a list, using default preset")
                    return [self._get_default_preset()]
                
                # Check if list is empty
                if not data:
                    print("presets.json is empty, using default preset")
                    return [self._get_default_preset()]
                
                # Get all required keys from default preset
                default_preset = self._get_default_preset()
                required_keys = set(default_preset.keys())
                
                # Validate and fix each preset in the list
                valid_presets = []
                for i, preset in enumerate(data):
                    if not isinstance(preset, dict):
                        print(f"Preset {i} is not a dictionary, skipping")
                        continue
                    
                    # Check if all required keys are present and add missing ones
                    preset_keys = set(preset.keys())
                    if not required_keys.issubset(preset_keys):
                        missing_keys = required_keys - preset_keys
                        print(f"Preset {i} missing keys: {missing_keys}, filling with defaults")
                        
                        # Add missing keys from default preset
                        for key in missing_keys:
                            preset[key] = default_preset[key]
                    
                    valid_presets.append(preset)
                
                # If no valid presets found, use default
                if not valid_presets:
                    print("No valid presets found in presets.json, using default preset")
                    return [self._get_default_preset()]
                
                print(f"Successfully loaded {len(valid_presets)} valid presets from presets.json")
                return valid_presets
                
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error loading presets.json: {e}, using default preset")
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
