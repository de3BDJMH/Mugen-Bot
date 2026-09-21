from nonebot import get_plugin_config,get_driver
from nonebot.plugin import PluginMetadata
from nonebot.message import event_preprocessor,run_preprocessor
from nonebot.adapters import Event
from nonebot.adapters.onebot.v11 import MessageEvent
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
@event_preprocessor
async def record_message(event:Event):
    if not isinstance(event,MessageEvent):
        return
    try:
        message_service.add(event)
    except Exception:
        logger.exception("消息日志记录失败")

#指令记录
@run_preprocessor
async def record_command(event:MessageEvent,matcher:Matcher):
    command_key=command_service.COMMAND_REGISTRY.get(type(matcher))
    if command_key is None:
        return
    try:
        command_service.add(event,command_key,[])
    except Exception:
        logger.exception("指令日志记录失败")