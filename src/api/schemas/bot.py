from pydantic import BaseModel, Field

class LoginInfo(BaseModel):
    user_id: int = Field(description="当前登录的 QQ 账号")
    nickname: str = Field(description="当前登录账号的昵称")


class BotStatusResponse(BaseModel):
    online: bool = Field(description="Bot 当前是否在线")
    self_id: str = Field(description="Bot 的 QQ 账号")
    uptime: int = Field(
        description="Mugen 本次启动后的运行时长，单位为秒",
        ge=0,
    )
    login_info: LoginInfo
    version: dict = Field(description="OneBot 的版本信息")