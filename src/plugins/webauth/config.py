from pydantic import BaseModel, SecretStr
from dotenv import load_dotenv

import os
from pathlib import Path

class Config(BaseModel):
    """Plugin Config Here"""
    """网站 QQ 验证插件配置。"""

    mugen_internal_api_key: SecretStr
    mugen_web_internal_url: str

def load_config() -> Config:
    """从项目根目录的 .env.api 加载网站验证所需配置。"""

    project_root = Path(__file__).resolve().parents[3]
    load_dotenv(project_root / ".env.api", override=False)

    api_key = os.getenv("MUGEN_INTERNAL_API_KEY", "").strip()#鉴权密钥
    web_url = os.getenv("MUGEN_WEB_INTERNAL_URL", "").strip().rstrip("/")#web地址

    if not api_key:
        raise RuntimeError("缺少 MUGEN_INTERNAL_API_KEY 配置。")

    if not web_url:
        raise RuntimeError("缺少 MUGEN_WEB_INTERNAL_URL 配置。")

    return Config(
        mugen_internal_api_key=SecretStr(api_key),
        mugen_web_internal_url=web_url,
    )