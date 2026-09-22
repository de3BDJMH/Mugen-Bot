from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata
from nonebot.plugin import on_command
from nonebot.adapters import Message
from nonebot.params import Depends
from nonebot.matcher import Matcher
from nonebot.adapters.onebot.v11 import Bot,MessageSegment,Event,GroupMessageEvent,PrivateMessageEvent
from nonebot.adapters.onebot.v11.event import MessageEvent
from nonebot.plugin import on_message
from nonebot import get_bot

import pathlib

from ...libraries.tools import *
from ...libraries.pluginmanage.tools import *

from .config import Config
from . import command

__plugin_meta__ = PluginMetadata(
    name="help",
    description="",
    usage="",
    config=Config,
)

###
#help帮助：
#/data下的help.json存放格式如下
#{
#    "plugin": "",//如果是自己的插件，在这里填上插件名，帮助文字会直接从插件的MG.json获取
#    "text": "", //这两个是在没有plugin的情况下会使用
#    "image": [] //这里存放图片地址
#}
###

config = get_plugin_config(Config)

TAG="help"
MGPLUGIN=MGPlugin(TAG)
def plugin_enabled(event:MessageEvent)->bool:
    if not MGPLUGIN.getPluginState():
        return False
    return MGPLUGIN.getGroupPluginState(event)

DATA_PATH=MGPLUGIN.data_path

HELPKEYS={
    "11":["11","phigros"],
    "12":["12","arcaea"],
    "13":["13","maimai"],
    "14":["14","osu"],
    "21":["21","msgc"],
    "22":["22","chc"],
    "23":["23","随机表情"],
    "24":["24","自制表情"],
    "25":["25","看群友"],
    "26":["26","我喜欢你"]
}

help=on_command("help",block=True,rule=plugin_enabled)
@help.handle()
async def handle_function(cmd:command.Help=Depends(command.Help.get)):
    arg=cmd.plain_text
    if arg:
        plugin_name=getPluginName(arg)
        if plugin_name:#先匹配有别名的
            plugin=MGPlugin(plugin_name)
            if plugin.exists() and plugin.config:
                await help.finish(plugin.help)
        else:#插件不存在，可能是不是自己的插件，或者没匹配到别名
            for k in HELPKEYS:
                if arg.lower() in HELPKEYS[k]:
                    with open(DATA_PATH/"help.json",encoding="utf-8") as f:
                        helpmsgs=json.load(f)
                    if helpmsgs[k]["plugin"]:#存在plugin说明是自己的插件
                        plugin=MGPlugin(helpmsgs[k]["plugin"])
                        if plugin.exists() and plugin.config:
                            await help.finish(plugin.help)
                    else:
                        msg=helpmsgs[k]["text"]
                        for img in helpmsgs[k]["image"]:
                            msg+=MessageSegment.image(img)
                        await help.finish(msg)
    else:
        r="帮助文档网站已开放浏览，请前往\nhttps://www.muge.zj.cn/"
        await help.finish(r+MessageSegment.image(DATA_PATH/"img"/"bothelp.png"))
