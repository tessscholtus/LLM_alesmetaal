# config.py
import os
from pathlib import Path
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()  # leest .env als die er is

class Settings(BaseModel):
    PROJECT_ROOT: Path = Field(default_factory=lambda: Path(__file__).resolve().parent)
    OUTPUT_DIR: Path = Field(default_factory=lambda: Path(os.getenv("OUTPUT_DIR", "outputs")))

    # Google AI Studio (Gemini)
    GOOGLE_API_KEY: str = Field(default_factory=lambda: os.getenv("GOOGLE_API_KEY", ""))
    GEMINI_MODEL: str = Field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-1.5-pro"))

    # Data-locatie (optioneel, voor later batchen)
    ELTEN_DATA_DIR: Path = Field(default_factory=lambda: Path(os.getenv("ELTEN_DATA_DIR", "data/Elten")))

    LOG_LEVEL: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    def ensure_dirs(self) -> None:
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

settings = Settings()
settings.ensure_dirs()

if not settings.GOOGLE_API_KEY:
    print("[config] Waarschuwing: GOOGLE_API_KEY ontbreekt (zet 'm in .env of export).")
