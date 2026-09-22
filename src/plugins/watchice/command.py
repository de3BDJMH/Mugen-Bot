from nonebot.adapters.onebot.v11 import Message,MessageEvent
from ...command.base import Command,CommandParseError

KEY="watchice"

class Watch(Command):
    """查看群友图片"""
    key=KEY+".watch"
    alias:str
    image_id:int

    @classmethod
    def parse(cls,event:MessageEvent,arg:Message):
        cmd=cls(event,arg)
        cmd.alias=cmd.plain_text
        cmd.image_id=-1#legacy_id
        if " " in cmd.alias:
            try:
                cmd.image_id=int(cmd.alias.split()[1].strip())
                cmd.alias=cmd.alias.split()[0].strip()
                if not cmd.alias:
                    raise CommandParseError()
            except (ValueError,IndexError):
                pass
        return cmd

class Upload(Command):
    """上传图片"""
    key=KEY+".upload"
    alias:str

    @classmethod
    def parse(cls,event:MessageEvent,arg:Message):
        cmd=cls(event,arg)
        cmd.alias=arg.extract_plain_text()
        return cmd

class AddAlias(Command):
    """添加群友别名"""
    key=KEY+".add_alias"
    aliases:list[str]

    @classmethod
    def parse(cls,event:MessageEvent,arg:Message):
        cmd=cls(event,arg)
        cmd.aliases=cmd.plain_text.split()
        if len(cmd.aliases)<2:
            raise CommandParseError("请提供原有别名和新增别名")
        return cmd

class DeleteAlias(AddAlias):
    """删除群友别名"""
    key=KEY+".delete_alias"
    aliases:list[str]

    @classmethod
    def parse(cls,event:MessageEvent,arg:Message):
        cmd=cls(event,arg)
        cmd.aliases=cmd.plain_text.split()
        if len(cmd.aliases)<2:
            raise CommandParseError("请提供原有别名和需要删的别名")
        return cmd

class CheckAlias(Command):
    """查看群友别名"""
    key=KEY+".check_alias"

class AddMember(Command):
    """添加群友"""
    key=KEY+".add_member"
    aliases:list[str]

    @classmethod
    def parse(cls,event:MessageEvent,arg:Message):
        cmd=cls(event,arg)
        cmd.aliases=cmd.plain_text.split()
        if not cmd.aliases:
            raise CommandParseError("需要提供群友名称，可在后面用空格分隔多个别名")
        for c in cmd.aliases[0]:
            if (not "a"<=c<="z") and (not "0"<=c<="9"):
                raise CommandParseError("需要全为小写字母或数字（尽可能有辨识性），可在别名内添加中文别名，所有别名都不可以包含空格")
        return cmd

class DeleteMember(Command):
    """删除群友"""
    key=KEY+".delete_member"
    alias:str

    @classmethod
    def parse(cls,event:MessageEvent,arg:Message):
        cmd=cls(event,arg)
        tmp=cmd.plain_text.split()
        if not tmp:
            raise CommandParseError("需要提供群友别名")
        cmd.alias=tmp[0]
        return cmd

class DeleteImage(Command):
    """删除图片"""
    key=KEY+".delete_image"
    alias:str
    image_id:int
    id_type:str

    @classmethod
    def parse(cls,event:MessageEvent,arg:Message):
        cmd=cls(event,arg)
        parts=cmd.plain_text.split()
        message="需要提供别名和图片id，你可以在id前添加#表示使用全局id"
        if len(parts)<2:
            raise CommandParseError(message)
        cmd.alias=parts[0]
        text=parts[1].strip()
        cmd.id_type="global" if text.startswith("#") else "single"
        try:
            cmd.image_id=int(text[1:] if cmd.id_type=="global" else text)
        except ValueError:
            raise CommandParseError(message)
        return cmd

class Help(Command):
    """看群友帮助"""
    key=KEY+".help"

class MemberList(Command):
    """群友列表"""
    key=KEY+".member_list"

class Distribution(Command):
    """图片分布"""
    key=KEY+".distribution"
