from nonebot.adapters.onebot.v11 import Message,MessageEvent

from ...command.base import Command,CommandParseError
from ...libraries.tools import *

ROOT_PATH=pathlib.Path(__file__).resolve().parent.parent.parent.parent #/server
DATA_PATH=ROOT_PATH/"data"/"pluginmanage"
CONFIG_PATH=DATA_PATH/"config.json"
KEY="pluginmanage"

class PluginState(Command):
    key=KEY+".state"

class PluginToggle(Command):
    key=KEY+".toggle"
    plugin_name:str
    state:bool|None

    @classmethod
    def parse(cls,event:MessageEvent,arg:Message):
        cmd=cls(event,arg)
        cmd.state=None
        if not cmd.plain_text:
            raise CommandParseError("请提供插件名")
        args=cmd.plain_text.split()
        cmd.plugin_name=args[0]
        if len(args)>1:
            target_state=args[1]
            mgconfig=jsonLoad(CONFIG_PATH)
            if not target_state.lower() in mgconfig["toggle_on_command"]+mgconfig["toggle_off_command"]:
                raise CommandParseError(f"请提供正确的状态，当前可用：\n  开启：{mgconfig["toggle_on_command"]}\n  关闭：{mgconfig["toggle_off_command"]}")
            if target_state.lower() in mgconfig["toggle_on_command"]:
                cmd.state=True
            else:
                cmd.state=False
        return cmd

class PluginListAdd(Command):
    key=KEY+".listadd"
    add_type:str
    plugin_name:str
    groups:list[int]

    @classmethod
    def parse(cls, event, arg):
        cmd=cls(event,arg)
        msg=str(cmd.message)
        msg=msg[msg.find("MG"):]
        cmd.add_type=""
        if msg.startswith(("MGwhitelistadd","MG添加白名单")):
            cmd.add_type="whitelist"
        elif msg.startswith(("MGblacklistadd","MG添加黑名单")):
            cmd.add_type="blacklist"
        else:
            raise CommandParseError("请指定黑白名单（MGwhite/blacklistadd、MG添加白/黑名单）")
        args=cmd.plain_text.split()
        if len(args)<2:
            raise CommandParseError("请提供插件名和群号")
        cmd.plugin_name=args[0]
        try:
            cmd.groups=[int(gid) for gid in args[1:]]
        except ValueError:
            raise CommandParseError("群号需要为整数")
        return cmd

class PluginListDel(Command):
    key=KEY+".listdel"
    del_type:str
    plugin_name:str
    groups:list[int]

    @classmethod
    def parse(cls, event, arg):
        cmd=cls(event,arg)
        msg=str(cmd.message)
        msg=msg[msg.find("MG"):]
        cmd.del_type=""
        if msg.startswith(("MGwhitelistdel","MG删除白名单")):
            cmd.del_type="whitelist"
        elif msg.startswith(("MGblacklistdel","MG删除黑名单")):
            cmd.del_type="blacklist"
        else:
            raise CommandParseError("请指定黑白名单（MGwhite/blacklistdel、MG删除白/黑名单）")
        args=cmd.plain_text.split()
        if len(args)<2:
            raise CommandParseError("请提供插件名和群号")
        cmd.plugin_name=args[0]
        try:
            cmd.groups=[int(gid) for gid in args[1:]]
        except ValueError:
            raise CommandParseError("群号需要为整数")
        return cmd