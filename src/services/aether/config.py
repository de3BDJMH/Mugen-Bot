from __future__ import annotations

import os
from pathlib import Path


AETHER_DATA_DIR=Path(os.getenv("AETHER_DATA_DIR","data/aether"))
AETHER_CONFIG_DIR=AETHER_DATA_DIR/"configs"
