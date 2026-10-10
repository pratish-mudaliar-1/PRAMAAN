"""scripts/webcam_edge_agent.py — Root workspace launcher for webcam edge agent."""
import os
import sys
import runpy

target = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend", "scripts", "webcam_edge_agent.py"))
if __name__ == "__main__":
    runpy.run_path(target, run_name="__main__")
