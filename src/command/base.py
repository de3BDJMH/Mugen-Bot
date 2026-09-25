from nonebot.matcher import Matcher
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import MessageEvent,GroupMessageEvent,Message

class CommandParseError(Exception):
    """处理报错用，输入的指令参数不合法"""

class Command:
    key=""#指令关键字

    def __init__(self,event:MessageEvent,arg:Message):#只有指令头这边arg是[""]
        self.event=event
        self.self_id=event.self_id#botQQ号
        self.user_id=event.user_id
        self.message_id=event.message_id
        self.message=event.message#Message类型消息
        self.message_type=event.message_type#消息类型，群组(group)/私聊(private)
        self.plain_text=arg.extract_plain_text().strip()#纯文本消息，字符串
        self.group_id=event.group_id if isinstance(event,GroupMessageEvent) else None

    @classmethod
    def parse(cls,event:MessageEvent,arg:Message):
        """参数解析"""
        return cls(event,arg)

    @classmethod
    async def get(cls,event:MessageEvent,matcher:Matcher,arg:Message=CommandArg()):
        """处理报错"""
        try:
            return cls.parse(event,arg)
        except CommandParseError as e:
            if str(e):#finish("")会报错
                await matcher.finish(str(e))
            else:
                await matcher.finish()
