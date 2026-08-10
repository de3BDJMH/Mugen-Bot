from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata
from nonebot import logger, on_command
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import Bot, MessageEvent
from nonebot.matcher import Matcher
from nonebot.params import CommandArg

import re

from .client import (
    WebAuthConfigurationError,
    WebAuthRejectedError,
    WebAuthUnavailableError,
    verify_qq,
)

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="webauth",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

verify=on_command("网站验证",aliases={"网站认证","MGAUTH"},block=True)

CODE_PATTERN=re.compile(r"^[23456789A-HJ-NP-Z]{6}$")

@verify.handle()
async def handle_verify(bot: Bot,event: MessageEvent,matcher: Matcher,args: Message = CommandArg(),):#这边不要接MGPlugin，web需要保证实时在线
    code = args.extract_plain_text().strip().upper()
    if not code:
        await matcher.finish("请在输入网站提供的验证码")
    if not CODE_PATTERN.fullmatch(code):
        await matcher.finish("验证码格式不正确，请检查后重新发送")

    id=str(event.user_id)
    nickname=(event.sender.nickname or f"QQ {event.user_id}").strip()[:40]

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