"""
Video2MIDI Generator
-------------------
A video analysis tool that generates MIDI music by detecting motion, color changes,
and intensity variations across video frames.

The system uses three-layered analysis:
- Background: Slow atmospheric changes based on global color shifts
- Medium: Main rhythmic elements from motion detection
- Details: Quick staccato notes from intense color bursts
"""

from .motion_detector import MotionDetector
from .midi_mapper import MIDIMapper

__version__ = "1.0.0"
__author__ = "Video2MIDI Team"

__all__ = [
    "MotionDetector",
    "MIDIMapper",
]
