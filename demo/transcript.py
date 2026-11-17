"""Save emulator snapshots as JSON for the screenshot renderer (demo/render.py)."""

import json
from pathlib import Path

from simulator import Emulator

OUT = Path(__file__).resolve().parent / "out"


def save(bot: str, em: Emulator) -> None:
    OUT.mkdir(exist_ok=True)
    (OUT / f"{bot}.json").write_text(json.dumps({"bot": bot, "frames": em.frames}, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
