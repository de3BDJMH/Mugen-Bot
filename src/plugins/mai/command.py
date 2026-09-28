from nonebot.adapters.onebot.v11 import Message,MessageEvent
from nonebot.params import CommandArg,EventMessage
from nonebot.matcher import Matcher

import json

from ...libraries.tools import getGroupID,ROOT_PATH
from ...command.base import Command,CommandParseError
from .parser import parse

KEY="mai"
PROGRESS_COMMANDS=[
    "霸者进度","舞极进度","舞将进度","舞神进度","舞舞舞进度","舞系列进度",
    "DX霸者进度","DX舞极进度","DX舞将进度","DX舞神进度","DX舞舞舞进度","DX舞系列进度"
]

DATA_PATH=ROOT_PATH/"data"/"mai"
GUESS_STATE_PATH=DATA_PATH/"guess"/"state.json"#开字母状态路径
def is_guess_running(event:MessageEvent)->bool:
    """判断该群是否正在猜歌"""
    gid=getGroupID(event)
    with open(GUESS_STATE_PATH,encoding="utf-8") as f:
        state=json.load(f)
    return gid in state and state[gid]["start"]

class Mai(Command):
    key=KEY
    args:list[str]

    @classmethod
    def parse(cls,event:MessageEvent,arg:Message):
        cmd=cls(event,arg)
        args=parse(event)

        if args is None:
            if is_guess_running(event):
                return MaiGuess.parse_session(event,arg)
            raise CommandParseError()
        if not args:
            cmd.key=KEY+".help"
            cmd.args=[]
            return cmd
        
        if args[0]=="guess":
            return MaiGuess.parse_args(event,arg,args)
        if args[0] in PROGRESS_COMMANDS:
            return MaiProgress.parse_args(event,arg,args)
        
        raise CommandParseError()
    
    @classmethod
    async def get(cls,event:MessageEvent,matcher:Matcher,arg:Message=EventMessage()):
        return await super().get(event,matcher,arg)

class MaiProgress(Mai):
    """进度类功能"""
    key=KEY+".progress"
    query_type:str#查询类型
    dx:bool#是否为DX
    target:int#查询目标qq

    @classmethod
    def parse_args(cls,event:MessageEvent,arg:Message,args:list[str]):
        cmd=cls(event,arg)
        cmd.dx=False
        if "DX" in args[0]:
            cmd.dx=True
        cmd.query_type=args[0][:-2].removeprefix("DX")
        cmd.target=cmd.user_id
        if len(args)>1:
            try:
                cmd.target=int(args[1])
            except:
                cmd.target=cmd.user_id
        cmd.args=args
        return cmd

class MaiGuess(Mai):
    """猜歌"""
    key=KEY+".guess"
    args:list[str]
    need_reply:bool

    @classmethod
    def parse_args(cls,event:MessageEvent,arg:Message,args:list[str]):
        cmd=cls(event,arg)
        cmd.args=args
        cmd.need_reply=True
        return cmd

    @classmethod
    def parse_session(cls,event:MessageEvent,arg:Message):
        cmd=cls(event,arg)
        message=arg.extract_plain_text().strip()
        if not message:
            raise CommandParseError()

        if message.startswith("开") and len(message)==2:
            cmd.args=["guess","开",message[1]]
            cmd.need_reply=True
        else:
            cmd.args=["guess","答",message]
            cmd.need_reply=False
        return cmd
