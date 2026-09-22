from nonebot.adapters.onebot.v11 import Message,MessageEvent
from nonebot.matcher import Matcher
from nonebot.params import EventMessage

from ...command.base import Command,CommandParseError
from ...services.aether.scheduler import resolve_run_mode

KEY="aether"

class Aether(Command):
    """自动探索指令"""
    key=KEY+".aether"
    action:str
    choice:str
    fast_mode:bool
    run_mode:str
    password:str
    sequence:int|None
    choice_index:int|None

    @classmethod
    def parse(cls,event:MessageEvent,arg:Message):
        cmd=cls(event,arg)
        cmd.action="help"
        cmd.choice=""
        cmd.fast_mode=False
        cmd.run_mode="save"
        cmd.password=""
        cmd.sequence=None
        cmd.choice_index=None
        text=cmd.plain_text
        if not text:
            return cmd
        lowered=text.lower()
        # 密码保留内部空格，不参与普通参数拆分。
        for prefix in ("密码 ","password ","passwd ","pwd "):
            if lowered.startswith(prefix):
                cmd.action="password"
                cmd.password=text[len(prefix):]
                return cmd
        if lowered in {"密码","password","passwd","pwd"}:
            raise CommandParseError("用法：/aether 密码 <Aether密码>\n建议私聊 Bot 发送，避免密码留在群聊记录里。")
        parts=text.split()
        action=parts[0].lower()
        aliases={
            "help":{"帮助","help","h"},
            "presets":{"预设","列表","list","presets"},
            "status":{"状态","status"},
            "stop":{"停止","stop"},
            "accept":{"接受","accept","y","yes"},
            "refresh":{"刷新","refresh","n","no"},
            "abort":{"终止","abort","q","quit"},
            "event":{"事件","event"},
            "recover":{"恢复","recover","resume"},
            "retry":{"重试","retry"},
            "skip":{"跳过","skip"},
            "task":{"任务","task","计划","plan"},
            "fast":{"快速","fast"},
            "start":{"开始","start"},
        }
        cmd.action=next((key for key,values in aliases.items() if action in values),"help")
        if cmd.action in {"event","retry","skip"}:
            label={"event":"事件","retry":"重试","skip":"跳过"}[cmd.action]
            if len(parts)<2:
                target="选项下标" if cmd.action=="event" else "任务编号"
                raise CommandParseError(f"用法：/aether {label} <{target}>")
            try:
                number=int(parts[1] if cmd.action=="event" else parts[1].lstrip("#"))
            except ValueError:
                message="事件选项必须是整数下标。" if cmd.action=="event" else f"任务编号必须是整数，例如：/aether {label} 17"
                raise CommandParseError(message)
            if cmd.action=="event":
                cmd.choice_index=number
            else:
                cmd.sequence=number
        elif cmd.action=="task":
            cmd.choice,cmd.run_mode=Selection.parse_task(" ".join(parts[1:]))
        elif cmd.action in {"start","fast"}:
            choices=parts[1:]
            cmd.fast_mode=cmd.action=="fast"
            if cmd.action=="start" and choices and choices[-1].lower() in {"快速","fast"}:
                cmd.fast_mode=True
                choices=choices[:-1]
                if not choices:
                    raise CommandParseError("用法：/aether 开始 <编号或预设 key> [快速]")
            cmd.choice=" ".join(choices)
        return cmd

class Selection(Command):
    """菜单回复使用整条消息，不读取首次命令参数"""
    key=KEY+".selection"
    choice:str
    cancelled:bool
    plan_choice:str
    run_mode:str

    @classmethod
    def parse(cls,event:MessageEvent,arg:Message):
        cmd=cls(event,arg)
        cmd.choice=cmd.plain_text
        cmd.cancelled=cmd.choice.lower() in {"q","quit","取消"}
        cmd.plan_choice,cmd.run_mode=cls.parse_task(cmd.choice)
        return cmd

    @staticmethod
    def parse_task(text:str):
        parts=text.split()
        run_mode="save"
        if len(parts)>=2:
            mode=resolve_run_mode(parts[-1])
            if mode is not None:
                run_mode=mode
                parts=parts[:-1]
        return " ".join(parts),run_mode

    @classmethod
    async def get(cls,event:MessageEvent,matcher:Matcher,arg:Message=EventMessage()):
        return await super().get(event,matcher,arg)

class AetherItem(Command):
    """物品查询指令"""
    key=KEY+".item"

    @classmethod
    def parse(cls,event:MessageEvent,arg:Message):
        return cls(event,arg)
