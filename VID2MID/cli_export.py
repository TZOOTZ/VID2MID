# cli_export.py
import argparse
import os
import yaml
from core.motion_detector import MotionDetector
from core.midi_mapper import MIDIMapper
from tqdm import tqdm
import logging
import sys
import cv2
from core.config_manager import Config

def main():
    # Add logging configuration
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    parser = argparse.ArgumentParser(
        description="Video2MIDI Converter",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("input_video", help="Input video file path")
    parser.add_argument("output_midi", help="Output MIDI file path")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--preset", choices=["cinematic", "electronic"], help="Use preset configuration")
    parser.add_argument("--preview", action="store_true", help="Show visual preview")
    parser.add_argument("--midi-preview", action="store_true", help="Enable MIDI preview")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        # Load config with preset if specified
        config = Config.load(args.config)
        if args.preset:
            preset_data = Config.get_preset(args.preset)
            config.update(preset_data)
        
        # Initialize components with preview options
        detector = MotionDetector(
            config_path=args.config, 
            progress_callback=None,  # Optional: could add progress callback here
            show_preview=args.preview
        )
        mapper = MIDIMapper(
            config_path=args.config, 
            preview_enabled=args.midi_preview
        )

        logging.info("Starting video analysis...")
        
        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(args.output_midi), exist_ok=True)

        # Get video info first
        cap = cv2.VideoCapture(args.input_video)
        if not cap.isOpened():
            raise ValueError(f"Could not open video: {args.input_video}")
            
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()

        # Process with proper progress bar
        with tqdm(total=total_frames, desc="Analyzing video", unit="frames") as pbar:
            movements = detector.analyze_video(args.input_video)
            pbar.update(total_frames)  # Update to completion

        logging.info("Generating MIDI...")
        mapper.create_multitrack_midi(movements, args.output_midi)
        
        logging.info(f"Successfully exported MIDI to: {args.output_midi}")

    except Exception as e:
        logging.error(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()