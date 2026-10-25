from nonebot.adapters.onebot.v11 import Message,MessageEvent
from nonebot.params import CommandArg

from ...command.base import Command,CommandParseError

KEY="gtnhpr"

class Pr(Command):
    key=KEY+"pr"

class Release(Command):
    key=KEY+"release"
    tag:str=""
    log_fields=("tag",)

    @classmethod
    def parse(cls,event:MessageEvent,arg:Message):
        cmd=cls(event,arg)
        #if cmd.plain_text.lower() in ["rc","beta","stable"]:
        #    cmd.tag=cmd.plain_text
        cmd.tag=cmd.plain_text
        return cmd

class Wiki(Command):
    key=KEY+".wiki"
    query:str
    log_fields=("query",)

    @classmethod
    def parse(cls,event:MessageEvent,arg:Message):
        cmd=cls(event,arg)
        cmd.query=cmd.plain_text
        return cmd