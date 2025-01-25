# core/midi_mapper.py
from mido import MidiFile, MidiTrack, Message, MetaMessage
import yaml
import math
from pygame import midi
import threading

class MIDIMapper:
    def __init__(self, config_path="config.yaml", preview_enabled=False):
        try:
            with open(config_path, "r", encoding="utf-8-sig") as f:
                self.config = yaml.safe_load(f) or {}
        except Exception as e:
            raise ValueError(f"Error loading config: {str(e)}")

        # Configuración MIDI
        self.ticks_per_beat = 480
        self.tempo = 500000  # 120 BPM
        self.channel_mapping = {
            "background": 0,
            "medium": 1,
            "details": 2
        }

        # Add default MIDI configuration with more musical options
        self.default_config = {
            "tracks": {
                "background": {
                    "program": 52,  # Pad
                    "base_note": 36,
                    "scale": [0, 3, 7, 10],  # Minor 7th chord
                    "decay": 15000
                },
                "medium": {
                    "program": 74,
                    "scale": [0, 2, 4, 7, 9],  # Pentatonic
                    "velocity_curve": "linear"  # or "exponential"
                },
                "details": {
                    "program": 127,
                    "note_range": [84, 96],
                    "velocity_range": [60, 127]
                }
            }
        }
        
        # Merge default config with user config
        self.config = self._merge_configs(self.default_config, self.config)

        self.preview_enabled = preview_enabled
        if preview_enabled:
            midi.init()
            self.preview_device = midi.Output(midi.get_default_output_device_id())

    def _merge_configs(self, default, user):
        """Deep merge of default and user configurations"""
        result = default.copy()
        for key, value in user.items():
            if isinstance(value, dict) and key in result:
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        return result

    def ms_to_ticks(self, milliseconds):
        """Convierte milisegundos a ticks MIDI"""
        return int((milliseconds * self.ticks_per_beat) / (self.tempo / 1000))

    def create_multitrack_midi(self, analysis_data, output_path):
        """Genera archivo MIDI con 3 pistas independientes"""
        mid = MidiFile(ticks_per_beat=self.ticks_per_beat)
        
        # Pista de metadatos (tempo)
        meta_track = MidiTrack()
        meta_track.append(MetaMessage('set_tempo', tempo=self.tempo))
        mid.tracks.append(meta_track)
        
        # Crear pistas instrumentales
        mid.tracks.append(self._create_background_track(analysis_data.get("background", [])))
        mid.tracks.append(self._create_medium_track(analysis_data.get("medium", [])))
        mid.tracks.append(self._create_details_track(analysis_data.get("details", [])))
        
        mid.save(output_path)

    def _create_background_track(self, data):
        """Pista atmosférica con cambios lentos"""
        track = MidiTrack()
        config = self.config.get("tracks", {}).get("background", {})
        
        program = config.get("program", 52)  # Pad atmosférico
        base_note = config.get("base_note", 36)  # C2
        decay = config.get("decay", 15000)  # 15 segundos
        
        track.append(Message('program_change', program=program, channel=0, time=0))
        
        last_time = 0
        last_hue = 0.0
        
        for event in data:
            delta_ticks = self.ms_to_ticks(event["time"] - last_time)
            
            # Control de modulación
            hue_change = abs(event.get("hue_shift", 0) - last_hue)
            mod_value = min(int(hue_change * 127), 127)
            track.append(Message('control_change', control=1, value=mod_value, time=delta_ticks))
            
            # Nota base con dinámica
            velocity = int(math.sqrt(event.get("value_shift", 0)) * 127)
            track.append(Message('note_on', note=base_note, velocity=velocity, time=0))
            track.append(Message('note_off', note=base_note, time=self.ms_to_ticks(decay)))
            
            last_time = event["time"]
            last_hue = event.get("hue_shift", 0)
            
        return track

    def _create_medium_track(self, data):
        """Pista rítmica principal"""
        track = MidiTrack()
        config = self.config.get("tracks", {}).get("medium", {})
        
        program = config.get("program", 74)  # Flauta
        scale = config.get("scale", [0, 2, 4, 7, 9])  # Escala pentatónica
        base_octave = config.get("base_octave", 4)
        decay = config.get("decay", 500)
        threshold = config.get("intensity_threshold", 1.0)
        
        track.append(Message('program_change', program=program, channel=1, time=0))
        
        last_time = 0
        
        for event in data:
            if event.get("intensity", 0) < threshold:
                continue
                
            delta_ticks = self.ms_to_ticks(event["time"] - last_time)
            note = self._direction_to_note(event.get("direction", 0), scale, base_octave)
            velocity = int(min(event.get("intensity", 0) * 127, 127))
            
            track.append(Message('note_on', note=note, velocity=velocity, time=delta_ticks))
            track.append(Message('note_off', note=note, time=self.ms_to_ticks(decay)))
            
            last_time = event["time"]
            
        return track

    def _create_details_track(self, data):
        """Pista de efectos glitch"""
        track = MidiTrack()
        config = self.config.get("tracks", {}).get("details", {})
        
        program = config.get("program", 127)  # FX
        note_range = config.get("note_range", [84, 96])  # C6 a C7
        group_threshold = config.get("group_threshold", 50)  # 50ms
        
        track.append(Message('program_change', program=program, channel=2, time=0))
        
        current_group = []
        last_time = 0
        
        for event in data:
            if current_group and (event["time"] - current_group[-1]["time"]) > group_threshold:
                self._add_note_cluster(track, current_group, note_range)
                current_group = []
                
            current_group.append(event)
            last_time = event["time"]
        
        if current_group:
            self._add_note_cluster(track, current_group, note_range)
            
        return track

    def _direction_to_note(self, angle, scale, octave):
        """Mapea dirección a notas de escala"""
        angle = angle % 360
        note_index = int((angle / 360) * len(scale))
        return scale[note_index % len(scale)] + (octave * 12)

    def _hue_to_note(self, hue, note_range):
        """Convierte tono a nota MIDI"""
        return int(note_range[0] + (hue / 180) * (note_range[1] - note_range[0]))

    def _add_note_cluster(self, track, events, note_range):
        """Añade grupo de notas staccato"""
        if not events:
            return
            
        # Nota principal (evento más grande)
        main_event = max(events, key=lambda x: x.get("size", 0))
        main_note = self._hue_to_note(main_event.get("hue", 0), note_range)
        delta_ticks = self.ms_to_ticks(main_event["time"] - track[-1].time if track else 0)
        
        # Nota principal
        track.append(Message('note_on', note=main_note, velocity=127, time=delta_ticks))
        track.append(Message('note_off', note=main_note, time=self.ms_to_ticks(50)))
        
        # Notas secundarias
        for event in events:
            if event == main_event:
                continue
                
            note = self._hue_to_note(event.get("hue", 0), note_range)
            track.append(Message('note_on', note=note, velocity=90, time=0))
            track.append(Message('note_off', note=note, time=self.ms_to_ticks(30)))

    def _preview_note(self, channel, note, velocity):
        if self.preview_enabled:
            self.preview_device.note_on(note, velocity, channel)
            threading.Timer(0.1, lambda: self.preview_device.note_off(note, channel)).start()

# Ejemplo de uso rápido
if __name__ == "__main__":
    mapper = MIDIMapper("config.yaml")
    sample_data = {
        "background": [{"time": 0, "hue_shift": 0.15, "value_shift": 0.3}],
        "medium": [{"time": 500, "intensity": 2.5, "direction": 45}],
        "details": [
            {"time": 100, "hue": 90, "size": 50},
            {"time": 120, "hue": 120, "size": 30}
        ]
    }
    mapper.create_multitrack_midi(sample_data, "test_output.mid")