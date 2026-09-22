from nonebot.adapters.onebot.v11 import Message,MessageEvent
from ...command.base import Command,CommandParseError

class Rob(Command):
    """抢劫指令"""
    key="rob.rob"
    target_id:int

    @classmethod
    def parse(cls,event:MessageEvent,arg:Message):
        cmd=cls(event,arg)
        for segment in event.get_message():
            if segment.type=="at":
                try:
                    cmd.target_id=int(segment.data["qq"])
                except (ValueError,TypeError):
                    raise CommandParseError()
                if not cmd.target_id:
                    raise CommandParseError()
                return cmd
        raise CommandParseError()

class RobRank(Command):
    """抢劫排行榜"""
    key="rob.rank"
