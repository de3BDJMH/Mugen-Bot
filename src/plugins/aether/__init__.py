from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata
from nonebot import on_command
from nonebot.adapters import Bot, Event
from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.matcher import Matcher
from nonebot.params import Depends
from nonebot.permission import SUPERUSER

from ...libraries.tools import *
from ...services.aether import core
from ...services.aether.manager import aether_manager
from ...services.aether.runtime_settings import load_runtime_settings

from .config import Config
from . import command

__plugin_meta__ = PluginMetadata(
    name="aether",
    description="雷渊小帮手",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

TAG="aether"
MGPLUGIN=MGPlugin(TAG)

def plugin_enabled(event:MessageEvent)->bool:
    if not MGPLUGIN.getPluginState():
        return False
    return MGPLUGIN.getGroupPluginState(event)

_runtime_settings=load_runtime_settings()
aether = on_command("aether",aliases={"雷渊"},block=True,rule=plugin_enabled)

def _help_text() -> str:
    return (
        "Aether 自动打本\n"
        "/aether 开始       选择一个预设并启动\n"
        "/aether 开始 <编号/key> [快速]\n"
        "/aether 快速 <编号/key>\n"
        "/aether 任务       查看批量任务计划\n"
        "/aether 任务 <编号/key> [省票|平衡|赶时间]\n"
        "/aether 恢复       恢复上次中断的批量任务\n"
        "/aether 重试 <n>   重试不确定/失败任务\n"
        "/aether 跳过 <n>   跳过不确定任务\n"
        "/aether 预设       查看预设列表\n"
        "/aether 状态       查看单任务/批量任务进度\n"
        "/aether 接受       接受当前布局（单任务）\n"
        "/aether 刷新       刷新当前布局（单任务）\n"
        "/aether 事件 <n>   处理未知事件（单任务）\n"
        "/aether 密码 <pwd> 旧登录兼容（建议私聊）\n"
        "/aether 停止       停止单任务或批量任务"
    )



async def _make_notifier(bot: Bot, event: Event, message: str) -> None:
    await bot.send(event, message)


async def _start_preset(matcher: Matcher,
    bot: Bot,
    event: Event,
    raw_choice: str,
    *,
    fast_mode: bool = False,
) -> None:
    preset_key = aether_manager.resolve_preset(raw_choice)
    if preset_key is None:
        await matcher.finish("没有找到这个预设。\n\n"+aether_manager.preset_menu())
    async def notifier(message: str) -> None:
        await _make_notifier(bot, event, message)
    ok, message = await aether_manager.start(
        preset_key,
        notifier,
        fast_mode=fast_mode,
    )
    await matcher.finish(message)


async def _start_task_plan(matcher:Matcher,bot:Bot,event:Event,plan_choice:str,*,run_mode:str="save")->None:
    if not plan_choice:
        await matcher.finish(aether_manager.task_plan_menu())
    plan_key = aether_manager.resolve_task_plan(plan_choice)
    if plan_key is None:
        await matcher.finish("没有找到这个批量任务计划。\n\n"+aether_manager.task_plan_menu())

    async def notifier(message: str) -> None:
        await _make_notifier(bot, event, message)
    ok, message = await aether_manager.start_task_plan(
        plan_key,
        notifier,
        run_mode=run_mode,
    )
    await matcher.finish(message)


async def _recover_task_plan(matcher: Matcher,bot: Bot,event: Event,) -> None:
    async def notifier(message: str) -> None:
        await _make_notifier(bot, event, message)
    ok, message = await aether_manager.recover_task_plan(notifier)
    await matcher.finish(message)


@aether.handle()
async def handle_aether(matcher:Matcher,bot:Bot,cmd:command.Aether=Depends(command.Aether.get))->None:
    action=cmd.action
    if action=="password":
        _,message=aether_manager.submit_password(cmd.password)
        await matcher.finish(message)
    if action=="help":
        await matcher.finish(_help_text())
    if action=="presets":
        await matcher.finish(aether_manager.preset_menu())
    if action=="status":
        await matcher.finish(aether_manager.status_text())
    if action=="stop":
        _,message=aether_manager.request_stop()
        await matcher.finish(message)
    if action in {"accept","refresh","abort"}:
        _,message=aether_manager.submit_layout(action)
        await matcher.finish(message)
    if action=="event":
        _,message=aether_manager.submit_event(cmd.choice_index)
        await matcher.finish(message)
    if action=="retry":
        _,message=aether_manager.retry_task(cmd.sequence)
        await matcher.finish(message)
    if action=="skip":
        _,message=aether_manager.skip_task(cmd.sequence)
        await matcher.finish(message)
    if action in {"recover","task","fast","start"}:
        if aether_manager.running:
            await matcher.finish("已有 Aether 任务正在运行。\n"+aether_manager.status_text())
    if action=="recover":
        await _recover_task_plan(matcher,bot,cmd.event)
        return
    if action=="task":
        if cmd.choice:
            await _start_task_plan(matcher,bot,cmd.event,cmd.choice,run_mode=cmd.run_mode)
            return
        matcher.state["aether_waiting_task_plan"]=True
        await matcher.pause(aether_manager.task_plan_menu()+"\n\n回复：编号/key [省票|平衡|赶时间]；默认省票；回复 q 取消。")
    if action in {"fast","start"}:
        if cmd.choice:
            await _start_preset(matcher,bot,cmd.event,cmd.choice,fast_mode=cmd.fast_mode)
            return
        matcher.state["aether_waiting_preset"]=True
        matcher.state["aether_fast_mode"]=cmd.fast_mode
        prompt="快速模式：回复编号或预设 key；回复 q 取消。" if cmd.fast_mode else "回复编号或预设 key；回复 q 取消。"
        await matcher.pause(aether_manager.preset_menu()+"\n\n"+prompt)
    await matcher.finish(_help_text())


@aether.handle()
async def handle_preset_selection(matcher:Matcher,bot:Bot,cmd:command.Selection=Depends(command.Selection.get))->None:
    if matcher.state.get("aether_waiting_task_plan"):
        if cmd.cancelled:
            await matcher.finish("已取消启动 Aether 批量任务。")
        await _start_task_plan(matcher,bot,cmd.event,cmd.plan_choice,run_mode=cmd.run_mode)
        return
    if not matcher.state.get("aether_waiting_preset"):
        return
    if cmd.cancelled:
        await matcher.finish("已取消启动 Aether。")
    await _start_preset(matcher,bot,cmd.event,cmd.choice,fast_mode=bool(matcher.state.get("aether_fast_mode")))

aetheritem = on_command("aetheritem",aliases={"雷渊物品","AEI"},block=True,rule=plugin_enabled)
@aetheritem.handle()
async def handle_aether_item(matcher:Matcher,bot:Bot,cmd:command.AetherItem=Depends(command.AetherItem.get))->None:
    account=core.Account("de3BDJMH","20050530BKR")
    user=core.AetherClient(account)
    if not user.try_cookie_login():
        user.login_with_password("20050530BKR")
    response=user.session.get(user._url("status"), timeout=5)
    equipments:list[dict]=response.json()["data"]["backpack"]["equipment"]
    equipment_value={}
    equipment_set={}
    with open(MGPLUGIN.data_path/"equipment_value.json",encoding="utf-8") as f:
        equipment_value=json.load(f)
    for ep in equipments:
        ep_id=ep["item_id"]
        if not ep_id in equipment_value:
            response=user.session.post(user._url("refine_info"),json={"uuid":ep["uuid"]})
            if response.json()["code"]==400:
                continue
            response=response.json()["data"]["fields"]
            equipment_value[ep_id]={v["field"]:[v["base"],v["high"],v["low"]] for v in response}
        if not ep_id in equipment_set:
            equipment_set[ep_id]=[]
        equipment_set[ep_id].append(ep["override_stats"])
    with open(MGPLUGIN.data_path/"equipment_value.json","w",encoding="utf-8") as f:
        json.dump(equipment_value,f,indent=4)
    best={}
    for ep_type in equipment_set:
        eps=equipment_set[ep_type]
        for ep in eps:
            try:
                avg=sum([(ep[field]-equipment_value[ep_type][field][0])/(equipment_value[ep_type][field][1]-equipment_value[ep_type][field][2]) for field in ep])/len(ep)
                if not ep_type in best:
                    best[ep_type]=[ep,avg]
                else:
                    if avg>best[ep_type][1]:
                        best[ep_type]=[ep,avg,eps[ep]]
            except:
                continue
    await aetheritem.finish("\n".join([f"{ep_type}: {best[ep_type]}" for ep_type in best]))
    ...
