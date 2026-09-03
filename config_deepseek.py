# config_deepseek.py
import os, sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from config_00 import *   # noqa: F401, F403

# Model name — the only real difference
OLLAMA_MODEL = "deepseek-r1:7b"

OLLAMA_OPTIONS = {
    "temperature":    0.1,
    "num_predict":    2048,
    "num_ctx":        4096,
    "num_thread":     10,
    "repeat_penalty": 1.1,
    "top_k":          10,
    "top_p":          0.9,
}