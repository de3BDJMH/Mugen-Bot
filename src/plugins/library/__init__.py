from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata
from nonebot.plugin import on_command
from nonebot.adapters import Message
from nonebot.params import Depends,ArgStr
from nonebot.matcher import Matcher
from nonebot.adapters.onebot.v11 import Bot,MessageSegment,Event,GroupMessageEvent,PrivateMessageEvent
from nonebot.adapters.onebot.v11.event import MessageEvent
from nonebot.plugin import on_message

from .config import Config
from . import command

import pathlib

from ...libraries import command_split
from ...libraries.tools import *
from ...libraries.library.tools import *

__plugin_meta__ = PluginMetadata(
    name="library",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

TAG="library"
MGPLUGIN=MGPlugin(TAG)
def plugin_enabled(event:MessageEvent)->bool:
    if not MGPLUGIN.getPluginState():
        return False
    return MGPLUGIN.getGroupPluginState(event)

DATA_PATH=pathlib.Path(__file__).resolve().parent.parent.parent.parent/"data"/"library"

user_info=jsonLoad(DATA_PATH/"password.json")
client = ZJNUClient(user_info["username"], user_info["password"],DATA_PATH/"cookies.json")

querycommand=on_command("ZJNU图书馆座位查询",aliases={"ZJNULSQ","zjnulsq"},rule=plugin_enabled)

@querycommand.handle()
async def query_handle(matcher:Matcher,cmd:command.Query=Depends(command.Query.get)):
    """负责处理查询"""
    if cmd.region is not None:
        matcher.set_arg("type",cmd.query_type)
        matcher.set_arg("region",cmd.region)
        matcher.set_arg("seat",cmd.seat)

@querycommand.got("region",prompt=f"请输入需要查询的区域（数字）：\n{"\n".join([f"  - {r}: {REGION_LIST[r][1]}{REGION_LIST[r][0]}" for r in REGION_LIST])}")
async def handle_region(matcher: Matcher, region: str = ArgStr("region")):
    """用户提供查询区域"""

    region=region.strip()
    if not region in REGION_LIST:
        await querycommand.finish("不存在该区域，查询已结束")

@querycommand.got("seat",prompt="请输入想查询的座位，输入-1表示查询该区域整体状态")
async def handle_seat(matcher: Matcher, seat: str = ArgStr("seat")):
    """用户提供查询座位"""

    seat=seat.strip()
    if seat=="-1":
        matcher.set_arg("type","all")
    else:
        matcher.set_arg("type","single")

@querycommand.handle()
async def final_query(matcher: Matcher, region: str = ArgStr("region"), seat: str = ArgStr("seat")):
    seats=client.query(region,"1445237")
    query_type=matcher.get_arg("type")
    if query_type=="all":
        states={}#座位状态
        for s in seats:
            if not s["status_name"] in states:
                states[s["status_name"]]=1
            else:
                states[s["status_name"]]+=1
        msg=f"{REGION_LIST[region][0]} 当前状态总览：\n"
        for s in states:
            msg+=f"  - {s}: {states[s]}\n"
        await querycommand.finish(msg[:-1])
    else:
        state=""
        minid=999
        maxid=-1
        if len(seat)<3:#座位号是3位
            seat="0"*(3-len(seat))+seat
        for s in seats:
            if int(s["no"])<minid:
                minid=int(s["no"])
            if int(s["no"])>maxid:
                maxid=int(s["no"])
            if s["no"]==seat:
                state=s["status_name"]
                break
        else:
            await querycommand.finish(f"没有查询到座位 {seat} 的信息，请检查输入是否有误\n座位范围： {minid}~{maxid}")
        if state:
            await querycommand.finish(f"{REGION_LIST[region][0]} 的 {seat} 号座位当前状态为： {state}")
        else:
            await querycommand.finish("没有查询到该座位的信息")
