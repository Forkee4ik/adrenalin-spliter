# -*- coding: utf-8 -*-
import sys
import os
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from app import ConfigManager, Muxer

app = QApplication(sys.argv)
config = ConfigManager()
muxer = Muxer(config)

old_do_mux = muxer.do_mux
def debug_do_mux(video_path, audio_path):
    print("running do_mux")
    try:
        old_do_mux(video_path, audio_path)
    except Exception as e:
        print("EXCEPTION:", e)
    print("do_mux done")

muxer.do_mux = debug_do_mux

def progress(c, t):
    print(f"queue_progress: {c}/{t}", flush=True)
def file_progress(p):
    print(f"file_progress: {p}%", flush=True)
def finished(p, s, m):
    print(f"finished: {s}, {m}", flush=True)

muxer.queue_progress.connect(progress)
muxer.file_progress.connect(file_progress)
muxer.mux_finished.connect(finished)

# Find the files properly
watch_dir = Path("E:\\запись\\unknown")
video = None
audio = None
for f in watch_dir.iterdir():
    if f.name.endswith(".mp4") and not f.name.endswith("_merged.mp4"):
        video = f
        audio = watch_dir / (f.stem + ".m4a")
        break

if video and audio:
    print(f"Found: {video.name}")
    muxer.enqueue_mux(str(video), str(audio), False)
else:
    print("Files not found!")

import time
for i in range(10):
    time.sleep(0.5)
    app.processEvents()
