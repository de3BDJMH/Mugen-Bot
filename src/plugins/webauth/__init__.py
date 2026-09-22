from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata
from nonebot import logger, on_command
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import Bot, MessageEvent
from nonebot.matcher import Matcher
from nonebot.params import Depends

import re

from .client import (
    WebAuthConfigurationError,
    WebAuthRejectedError,
    WebAuthUnavailableError,
    verify_qq,
)

from .config import Config
from . import command

__plugin_meta__ = PluginMetadata(
    name="webauth",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

verify=on_command("网站验证",aliases={"网站认证","MGAUTH"},block=True)

CODE_PATTERN=command.CODE_PATTERN

@verify.handle()
async def handle_verify(matcher: Matcher,cmd:command.Verify=Depends(command.Verify.get),):#这边不要接MGPlugin，web需要保证实时在线
    code=cmd.code

    id=str(cmd.user_id)
    nickname=(cmd.event.sender.nickname or f"QQ {cmd.user_id}").strip()[:40]

    try:
        await verify_qq(qq_id=id,code=code,nickname=nickname,)
    except WebAuthRejectedError:
        await matcher.finish(
            "验证失败。验证码可能已过期、已使用，"
            "或者网页填写的 QQ 与当前账号不一致\n\n"
            "请回到网站重新获取验证码"
        )
    except WebAuthConfigurationError:
        logger.error("Web authentication service configuration error.")
        await matcher.finish(
            "网站验证服务配置异常，请联系管理员"
        )
    except WebAuthUnavailableError:
        logger.warning("Web authentication service is temporarily unavailable.")
        await matcher.finish(
            "暂时无法连接网站验证服务，请稍后再试"
        )
    logger.info(f"Web authentication succeeded for QQ {id}.")
    await matcher.finish(
        "验证成功，请回到网站继续操作"
    )