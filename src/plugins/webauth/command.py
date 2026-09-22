from nonebot.adapters.onebot.v11 import Message,MessageEvent
from ...command.base import Command,CommandParseError

import re

CODE_PATTERN=re.compile(r"^[23456789A-HJ-NP-Z]{6}$")

class Verify(Command):
    """网站验证码"""
    key="webauth.verify"
    code:str

    @classmethod
    def parse(cls,event:MessageEvent,arg:Message):
        cmd=cls(event,arg)
        cmd.code=cmd.plain_text.upper()
        if not cmd.code:
            raise CommandParseError("请在输入网站提供的验证码")
        if not CODE_PATTERN.fullmatch(cmd.code):
            raise CommandParseError("验证码格式不正确，请检查后重新发送")
        return cmd
