import os
from pathlib import Path


def path_or_default(default: str, env_var: str) -> Path:
    """Return the path from the environment variable or the default."""
    return Path(os.environ.get(env_var, default))


FASTLED_ROOT = path_or_default("/git/fastled", "ENV_FASTLED_ROOT")

FASTLED_SRC = FASTLED_ROOT / "src"
VOLUME_MAPPED_SRC = path_or_default("/host/fastled/src", "ENV_VOLUME_MAPPED_SRC")
SKETCH_ROOT = path_or_default("/js/src", "ENV_SKETCH_ROOT")
