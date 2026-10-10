"""scripts/setup_local_webcam_demo.py — Root workspace launcher for webcam demo setup."""
import os
import sys
import runpy

target = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend", "scripts", "setup_local_webcam_demo.py"))
if __name__ == "__main__":
    runpy.run_path(target, run_name="__main__")
