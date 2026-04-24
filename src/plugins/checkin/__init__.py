from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata
from nonebot.plugin import on_command,on_message
from nonebot.adapters import Message
from nonebot.params import CommandArg,Arg,EventMessage
from nonebot.matcher import Matcher
from nonebot.adapters.onebot.v11 import Bot,MessageSegment,Event,GroupMessageEvent,PrivateMessageEvent,MessageEvent
from nonebot import get_bot

import pathlib
import datetime

from ...libraries.tools import *
from ...libraries.checkin import tools

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="checkin",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

TAG="checkin"
MGPLUGIN=MGPlugin(TAG)

DATA_PATH=MGPLUGIN.data_path

checkin=on_command("签到",aliases={"checkin"})
@checkin.handle()
async def handle_function(matcher:Matcher,bot:Bot,event:MessageEvent,args: Message = CommandArg()):

    if not MGPLUGIN.getPluginState():
        return
    if not MGPLUGIN.getGroupPluginState(event):
        return
    
    bot=get_bot()
    user=tools.User(event.user_id)
    now=datetime.datetime.now()
    if not user.nickname:
        nickname=(await bot.get_stranger_info(user_id=event.user_id,no_cache=True))["nickname"]
        user=tools.User(event.user_id,nickname)
    if user.last_check==now.strftime("%Y-%m-%d"):
        await checkin.finish("宝宝你今天已经签过到了哦——")
    result=user.check()
    if result["first"]=="year":
        msg=f"你是 {now.year}年 第 1 个签到的群友！\n"
    elif result["first"]=="month":
        msg=f"你是 {now.month}月 第 1 个签到的群友！\n"
    else:
        msg=f"你是今天第 {result["rank"]} 个签到的群友！\n"
    msg+=f"你已经连续签到 {user.consecutive_check} 天啦~\n"
    if result["thursday"]:
        msg+=f"( +50MB )  今天是周四，Mugen决定送你 50MB ！\n"
    if result["super"] is not None:
        msg+=f"( +{result["super"].display} )  运气不错哇——你获得了 {result["super"].display} ！\n"
    msg+=f"( +{result["basedata"].display} )  签到获得了 {result["basedata"].display} 哦\n"
    if result["rankbonus"]!=1:
        msg+=f"( x{round(result["rankbonus"],2)} )  哇~是第{result['rank']}个签到的欸，Data x{round(result["rankbonus"],2)}\n"
    msg+=f"Data +{result["data"].display}"
    await checkin.finish(msg)

selfinfo=on_command("我的data",aliases={"data"})
@selfinfo.handle()
async def handle_function(matcher:Matcher,bot:Bot,event:MessageEvent,args: Message = CommandArg()):

    if not MGPLUGIN.getPluginState():
        return
    if not MGPLUGIN.getGroupPluginState(event):
        return
    
    user=tools.User(event.user_id)
    if not user.nickname:
        await selfinfo.finish("还没有你的信息呢，签到试试看吧？")
    msg=f"{user.nickname} 的个人信息：\n"
    msg+=f"  - Data: {user.data.display}\n"
    msg+=f"  - 累计签到天数: {user.total_check} 天\n"
    msg+=f"  - 当前连续签到天数: {user.consecutive_check} 天\n"
    msg+=f"  - 最大连续签到天数: {user.max_consecutive_check} 天"
    await selfinfo.finish(msg)
    