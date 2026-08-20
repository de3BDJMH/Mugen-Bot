from nonebot import get_plugin_config,require
from nonebot.plugin import PluginMetadata
from nonebot.plugin import on_command
from nonebot.adapters import Message
from nonebot.params import CommandArg,Arg
from nonebot.matcher import Matcher
from nonebot.adapters.onebot.v11 import Bot,MessageSegment,Event,GroupMessageEvent,PrivateMessageEvent

require("watchice")

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="watchice_gacha",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

gacha=on_command("ccb")#暂时不想做，1刷屏，2指令名字不知道叫什么好
#倒是可以转发消息，但是指令名字呢，抽群友？？？
#而且这边做了抽，那最基本的查也要写，以后再说吧
