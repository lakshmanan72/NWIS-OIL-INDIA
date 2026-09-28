from pathlib import Path
import os
from typing import Optional


def resolve_data_file(*parts: str, custom_path: Optional[str] = None) -> Path:
    if custom_path and os.path.exists(custom_path):
        return Path(custom_path)

    if not parts:
        raise ValueError("Must provide at least one filename or path component")

    filename = Path(*parts)
    base_dir = Path(__file__).resolve().parent.parent.parent
    app_dir = Path(__file__).resolve().parent.parent

    candidates = [
        base_dir / "data" / filename,
        base_dir / "data" / "raw" / filename,
        base_dir / "data" / "documents" / filename,
        base_dir / filename,
        app_dir / "data" / filename,
        Path.cwd() / "data" / filename,
        Path.cwd() / "data" / "raw" / filename,
        Path.cwd() / filename,
    ]

    for p in candidates:
        if p.exists() and not p.is_dir():
            return p

    # If file doesn't exist yet (e.g. creating active_alerts.json), return preferred destination
    return base_dir / "data" / filename
