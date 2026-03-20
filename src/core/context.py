import argparse
import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import List

from src.managers.voices.manager import VoiceManager


@dataclass(frozen=True)
class AppContext:
    args: argparse.Namespace
    data_dirs: List[Path]
    voice_manager: VoiceManager
    synthesis_semaphore: asyncio.Semaphore
