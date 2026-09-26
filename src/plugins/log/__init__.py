from nonebot import get_plugin_config,get_driver
from nonebot.plugin import PluginMetadata
from nonebot.message import event_preprocessor,run_preprocessor
from nonebot.adapters.onebot.v11 import MessageEvent,Event, Bot
from nonebot.matcher import Matcher
from nonebot import logger

from ...storage.log.database import init_database
from ...services.log import message as message_service
from ...services.log import command as command_service

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="log",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

#初始化数据库
driver=get_driver()

@driver.on_startup
async def init_log_database():
    init_database()

#消息记录，始于2026-09-19 02:07:38
## 转发消息处理，之前没发现转发消息需要再get一下才能获取内部信息，于2026.9.27 1:05补充
@event_preprocessor
async def record_message(bot:Bot,event:Event):
    if not isinstance(event,MessageEvent):
        return
    try:
        await message_service.add(bot,event)
    except Exception:
        logger.exception("消息日志记录失败")

#bot消息记录，忘记bot自己发的不会被检测了，始于2026.9.27 1:05
NORMAL_SEND_API={#普通消息
    "send_msg",
    "send_group_msg",
    "send_private_msg"
}

FORWARD_SEND_API={#转发消息
    "send_group_forward_msg",
    "send_private_forward_msg"
}

@Bot.on_called_api
async def record_bot_message(bot:Bot,exception:Exception|None,api:str,data:dict,result):
    if exception:
        return

    try:
        if api in NORMAL_SEND_API:
            message_service.add_bot_message(bot,api,data,result)
        elif api in FORWARD_SEND_API:
            #print(data["messages"])
            await message_service.add_bot_forward(bot,api,data,result)
    except Exception:
        logger.exception("Bot消息日志记录失败")