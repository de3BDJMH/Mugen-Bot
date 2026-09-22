from nonebot.adapters.onebot.v11 import Message,MessageEvent
from ...command.base import Command,CommandParseError

class Query(Command):
    """图书馆区域和座位参数"""
    key="library.query"
    region:str|None
    seat:str
    query_type:str

    @classmethod
    def parse(cls,event:MessageEvent,arg:Message):
        cmd=cls(event,arg)
        cmd.region=None
        cmd.seat="-1"
        cmd.query_type="all"
        if cmd.plain_text:
            parts=cmd.plain_text.split(" ")
            if len(parts)>2:
                raise CommandParseError("参数过多，只需提供区域和座位即可")
            cmd.region=parts[0]
            if len(parts)==2 and parts[-1]!="-1":
                cmd.query_type="single"
                cmd.seat=parts[1]
        return cmd
