import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, SecretStr


class ApiConfig(BaseModel):
    """Configuration shared by Mugen's internal business API."""

    mugen_internal_api_key: SecretStr


def load_api_config() -> ApiConfig:
    """Load API-only secrets after NoneBot has finished logging its config."""
    project_root = Path(__file__).resolve().parents[2]
    load_dotenv(project_root / ".env.api", override=False)
    value = os.getenv("MUGEN_INTERNAL_API_KEY", "").strip()
    if not value:
        raise RuntimeError("MUGEN_INTERNAL_API_KEY is required for the internal API.")
    return ApiConfig(mugen_internal_api_key=SecretStr(value))
