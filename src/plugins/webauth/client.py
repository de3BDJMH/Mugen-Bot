import httpx

from .config import load_config


_config = load_config()


class WebAuthError(Exception):
    """网站验证请求的基础异常。"""


class WebAuthRejectedError(WebAuthError):
    """验证码被网站拒绝。"""


class WebAuthUnavailableError(WebAuthError):
    """网站验证服务暂时不可用。"""


class WebAuthConfigurationError(WebAuthError):
    """Bot 与网站之间的认证配置异常。"""


async def verify_qq(qq_id: str, code: str, nickname: str) -> None:
    """将 QQ 验证信息提交给网站后端。"""

    async with httpx.AsyncClient(
        base_url=_config.mugen_web_internal_url,
        timeout=httpx.Timeout(5.0, connect=2.0),
    ) as client:
        try:
            response = await client.post(
                "/api/internal/auth/qq-verified",
                headers={
                    "X-Mugen-API-Key": _config.mugen_internal_api_key.get_secret_value(),
                    "Accept": "application/json",
                },
                json={
                    "qq_id": qq_id,
                    "code": code,
                    "nickname": nickname,
                },
            )
        except httpx.RequestError as e:
            raise WebAuthUnavailableError("无法连接网站验证服务") from e

    if response.status_code == 200:
        return

    if response.status_code == 409:
        raise WebAuthRejectedError("验证码被网站拒绝")

    if response.status_code == 401:
        raise WebAuthConfigurationError("内部 API Key 验证失败")

    if response.status_code == 422:
        raise WebAuthConfigurationError("提交的数据格式不正确")

    if response.status_code >= 500:
        raise WebAuthUnavailableError("网站验证服务异常")

    raise WebAuthUnavailableError(
        f"网站返回了未预期的状态码：{response.status_code}"
    )