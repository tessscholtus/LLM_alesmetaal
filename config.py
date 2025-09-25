# config.py — minimal, no pydantic needed
import os
from pathlib import Path
from dotenv import load_dotenv

# Laad .env indien aanwezig
load_dotenv()

class Settings:
    def __init__(self):
        # Paden
        self.PROJECT_ROOT = Path(__file__).resolve().parent
        self.OUTPUT_DIR   = Path(os.getenv("OUTPUT_DIR", "outputs"))
        self.ELTEN_DATA_DIR = Path(os.getenv("ELTEN_DATA_DIR", "data/Elten"))

        # Logging
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

        # Google AI (Gemini)
        self.GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
        self.GEMINI_MODEL   = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")

        # Zorg dat output-map bestaat
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Dit is wat andere modules importeren: from config import settings
settings = Settings()
