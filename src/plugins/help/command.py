from nonebot.adapters.onebot.v11 import Message,MessageEvent
from ...command.base import Command,CommandParseError

class Help(Command):
    """帮助查询"""
    key="help.help"
