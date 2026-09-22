from nonebot.adapters.onebot.v11 import Message,MessageEvent
from ...command.base import Command,CommandParseError

class Generate(Command):
    """词云查询参数"""
    key="wordcloud.generate"
    days:int
    target_group_id:int

    @classmethod
    def parse(cls,event:MessageEvent,arg:Message):
        cmd=cls(event,arg)
        tmp=cmd.plain_text.split(" ")
        try:
            cmd.days=int(tmp[0])
            cmd.target_group_id=int(tmp[1]) if len(tmp)>1 else event.group_id
        except (ValueError,TypeError):
            raise CommandParseError()
        return cmd

class Update(Command):
    """更新词频参数"""
    key="wordcloud.update"
    days:int

    @classmethod
    def parse(cls,event:MessageEvent,arg:Message):
        cmd=cls(event,arg)
        try:
            cmd.days=int(cmd.plain_text)
        except ValueError:
            raise CommandParseError()
        return cmd
