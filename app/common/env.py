from __future__ import annotations

import os
from pathlib import Path


def get_env_or_file(name: str, default: str | None = None) -> str | None:
    """Read NAME or NAME_FILE.

    This matches the Docker/Kubernetes secret pattern where the secret value is
    mounted as a file and only the file path is exposed through the environment.
    NAME has priority to keep local development simple.
    """
    value = os.getenv(name)
    if value not in (None, ""):
        return value

    file_name = os.getenv(f"{name}_FILE")
    if file_name:
        return Path(file_name).read_text(encoding="utf-8").strip()

    return default
