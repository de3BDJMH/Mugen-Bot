from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata
from nonebot.plugin import on_command
from nonebot.adapters import Message
from nonebot.params import CommandArg,ArgStr
from nonebot.matcher import Matcher
from nonebot.adapters.onebot.v11 import Bot,MessageSegment,Event,GroupMessageEvent,PrivateMessageEvent
from nonebot.adapters.onebot.v11.event import MessageEvent
from nonebot.plugin import on_message

from .config import Config

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

DATA_PATH=pathlib.Path(__file__).resolve().parent.parent.parent.parent/"data"/"library"

user_info=jsonLoad(DATA_PATH/"password.json")
client = ZJNUClient(user_info["username"], user_info["password"],DATA_PATH/"cookies.json")

querycommand=on_command("ZJNU图书馆座位查询",aliases={"ZJNULSQ","zjnulsq"})

@querycommand.handle()
async def query_handle(matcher:Matcher,bot:Bot,event:MessageEvent,args: Message = CommandArg()):
    """负责处理查询"""

    if not MGPLUGIN.getPluginState():
        return
    if not MGPLUGIN.getGroupPluginState(event):
        return
    
    arg=args.extract_plain_text().strip()

    if arg:
        args=arg.split(" ")
        if 0<len(args)<=2:
            matcher.set_arg("type","all")#type表示查询类型，all为该区域状态，single为单个座位
            matcher.set_arg("region",args[0])#查询区域，str
            matcher.set_arg("seat","-1")#-1代表不查询
            if len(args)==2 and args[-1]!="-1":
                matcher.set_arg("type","single")
                matcher.set_arg("seat",args[1])#座位，str
        elif len(args)>2:
            await querycommand.finish("参数过多，只需提供区域和座位即可")

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

