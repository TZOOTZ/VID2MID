import tkinter as tk
from tkinter import ttk, filedialog
import threading

class Video2MIDIGui:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Video2MIDI Converter")
        
        # Create widgets
        self.input_path = tk.StringVar()
        self.output_path = tk.StringVar()
        
        ttk.Label(self.root, text="Input Video:").pack()
        ttk.Entry(self.root, textvariable=self.input_path).pack()
        ttk.Button(self.root, text="Browse", command=self.browse_input).pack()
        
        ttk.Label(self.root, text="Output MIDI:").pack()
        ttk.Entry(self.root, textvariable=self.output_path).pack()
        ttk.Button(self.root, text="Browse", command=self.browse_output).pack()
        
        self.progress = ttk.Progressbar(self.root, mode='determinate')
        self.progress.pack()
        
        ttk.Button(self.root, text="Convert", command=self.start_conversion).pack()
        
    def browse_input(self):
        path = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4")])
        self.input_path.set(path)
        
    def start_conversion(self):
        threading.Thread(target=self.convert).start() 