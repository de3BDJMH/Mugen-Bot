from nonebot.adapters.onebot.v11 import Message,MessageEvent
from ...command.base import Command,CommandParseError

class CharacterCounter(Command):
    """字符统计查询"""
    key="charcounter.query"
    action:str
    count:int
    invalid_count:bool
    query_id:str

    @classmethod
    def parse(cls,event:MessageEvent,arg:Message):
        cmd=cls(event,arg)
        tmp=arg.extract_plain_text().split(" ")
        cmd.action=tmp[0]
        cmd.count=20
        cmd.invalid_count=False
        cmd.query_id=tmp[1] if len(tmp)>1 else event.get_user_id()
        if cmd.action=="总字符统计" and len(tmp)>1:
            try:
                cmd.count=int(tmp[1])
            except ValueError:
                cmd.invalid_count=True
        return cmd
