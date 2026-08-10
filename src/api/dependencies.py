import hmac
from typing import Optional

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from .config import load_api_config


API_KEY_HEADER = "X-Mugen-API-Key"
_api_key_header = APIKeyHeader(name=API_KEY_HEADER, auto_error=False)
_config = load_api_config()


async def require_internal_api_key(
    api_key: Optional[str] = Security(_api_key_header),
) -> None:
    """验证来自受信任的 Mugen 服务端服务的请求
       验证内部 API Key，不通过则拒绝请求"""
    expected = _config.mugen_internal_api_key.get_secret_value()
    if not api_key or not hmac.compare_digest(api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal API credentials.",
        )
