from dataclasses import dataclass
from typing import List, Dict
import yaml
import logging

logger = logging.getLogger(__name__)

@dataclass
class TrackConfig:
    program: int
    scale: List[int]
    velocity_range: List[int]

    @classmethod
    def from_dict(cls, data: Dict) -> 'TrackConfig':
        return cls(
            program=data.get('program', 0),
            scale=data.get('scale', [0, 4, 7]),  # Default major triad
            velocity_range=data.get('velocity_range', [0, 127])
        )

@dataclass
class Config:
    roi: List[int]
    blur: int
    tracks: Dict[str, Dict]
    
    @classmethod
    def validate(cls, data: Dict) -> 'Config':
        """Validate and create Config from dictionary data"""
        if not isinstance(data, dict):
            raise ValueError("Configuration must be a dictionary")

        # Get global settings with defaults
        global_config = data.get('global', {})
        roi = global_config.get('roi', [0, 0, 1920, 1080])
        blur = global_config.get('blur', 5)

        # Validate ROI
        if not isinstance(roi, list) or len(roi) != 4:
            logger.warning("Invalid ROI format, using default")
            roi = [0, 0, 1920, 1080]

        # Get tracks configuration
        tracks = data.get('tracks', {})
        if not tracks:
            logger.warning("No tracks configuration found, using defaults")
            tracks = {
                "background": {"program": 52},
                "medium": {"program": 74},
                "details": {"program": 127}
            }

        return cls(
            roi=roi,
            blur=blur,
            tracks=tracks
        )

    @classmethod
    def load(cls, path: str) -> 'Config':
        """Load configuration from YAML file"""
        try:
            with open(path, 'r', encoding='utf-8-sig') as f:
                data = yaml.safe_load(f)
            return cls.validate(data)
        except Exception as e:
            logger.error(f"Error loading config: {str(e)}")
            # Return default configuration
            return cls.validate({})

    @classmethod
    def get_preset(cls, name: str) -> Dict:
        """Get predefined configuration preset"""
        presets = {
            "cinematic": {
                "tracks": {
                    "background": {"program": 52, "scale": [0,3,7,10]},
                    "medium": {"program": 74, "scale": [0,2,4,7,9]},
                    "details": {"program": 127}
                }
            },
            "electronic": {
                "tracks": {
                    "background": {"program": 81, "scale": [0,4,7,11]},
                    "medium": {"program": 86, "scale": [0,3,6,9]},
                    "details": {"program": 119}
                }
            }
        }
        return presets.get(name, presets["cinematic"])

    def update(self, preset: Dict) -> None:
        """Update configuration with preset values"""
        if "tracks" in preset:
            for track_name, track_config in preset["tracks"].items():
                if track_name in self.tracks:
                    self.tracks[track_name].update(track_config) 