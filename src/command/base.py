from nonebot.matcher import Matcher
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import MessageEvent,GroupMessageEvent,Message

class CommandParseError(Exception):
    """处理报错用，输入的指令参数不合法"""

class Command:
    key=""#指令关键字

    def __init__(self,event:MessageEvent,arg:Message|None=None):
        self.event=event
        self.user_id=event.user_id
        self.message_id=event.message_id
        self.message_type=event.message_type#消息类型，群组(group)/私聊(private)
        self.group_id=event.group_id if isinstance(event,GroupMessageEvent) else None

    @classmethod
    def parse(cls,event:MessageEvent):
        """参数解析"""
        return cls(event)

    @classmethod
    async def get(cls,event:MessageEvent,matcher:Matcher,arg:Message=CommandArg()):
        """处理报错"""
        try:
            return cls.parse(event,arg)
        except CommandParseError as e:
            await matcher.finish(str(e))
