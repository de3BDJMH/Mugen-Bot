from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata
from nonebot import on_command
from nonebot.adapters import Bot, Event, Message
from nonebot.matcher import Matcher
from nonebot.params import CommandArg
from nonebot.permission import SUPERUSER

from ...libraries.tools import *
from ...services.aether import core
from ...services.aether.manager import aether_manager
from ...services.aether.runtime_settings import load_runtime_settings

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="aether",
    description="雷渊小帮手",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

TAG="aether"
MGPLUGIN=MGPlugin(TAG)

_runtime_settings=load_runtime_settings()
aether = on_command("aether",aliases={"雷渊"},block=True)

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


async def _start_task_plan(matcher: Matcher,bot: Bot,event: Event,raw_choice: str,) -> None:
    parts = raw_choice.split()
    if not parts:
        await matcher.finish(aether_manager.task_plan_menu())

    run_mode = "save"
    # 最后一个词如果是“省票/平衡/赶时间”，就作为整份计划的运行模式。
    if len(parts) >= 2:
        maybe_mode = aether_manager.resolve_task_run_mode(parts[-1])
        if maybe_mode is not None:
            run_mode = maybe_mode
            parts = parts[:-1]

    plan_choice = " ".join(parts).strip()
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
async def handle_aether(matcher: Matcher,bot: Bot,event: Event,args: Message = CommandArg(),) -> None:
    text = args.extract_plain_text().strip()
    if not text:
        await matcher.finish(_help_text())

    # 密码可能包含空格，所以必须在普通 split 逻辑之前单独处理。
    password_prefixes = ("密码 ", "password ", "passwd ", "pwd ")
    lowered = text.lower()

    for prefix in password_prefixes:
        if lowered.startswith(prefix.lower()):
            password = text[len(prefix):]
            _, message = aether_manager.submit_password(password)
            # 回复中绝不包含密码本身。
            await matcher.finish(message)

    if lowered in {"密码", "password", "passwd", "pwd"}:
        await matcher.finish(
            "用法：/aether 密码 <Aether密码>\n"
            "建议私聊 Bot 发送，避免密码留在群聊记录里。"
        )

    parts = text.split()
    action = parts[0].lower()
    if action in {"帮助", "help", "h"}:
        await matcher.finish(_help_text())
    if action in {"预设", "列表", "list", "presets"}:
        await matcher.finish(aether_manager.preset_menu())
    if action in {"状态", "status"}:
        await matcher.finish(aether_manager.status_text())
    if action in {"停止", "stop"}:
        _, message = aether_manager.request_stop()
        await matcher.finish(message)
    if action in {"接受", "accept", "y", "yes"}:
        _, message = aether_manager.submit_layout("accept")
        await matcher.finish(message)
    if action in {"刷新", "refresh", "n", "no"}:
        _, message = aether_manager.submit_layout("refresh")
        await matcher.finish(message)
    if action in {"终止", "abort", "q", "quit"}:
        _, message = aether_manager.submit_layout("abort")
        await matcher.finish(message)
    if action in {"事件", "event"}:
        if len(parts) < 2:
            await matcher.finish("用法：/aether 事件 <选项下标>")
        try:
            choice_index = int(parts[1])
        except ValueError:
            await matcher.finish("事件选项必须是整数下标。")
        _, message = aether_manager.submit_event(choice_index)
        await matcher.finish(message)

    if action in {"恢复", "recover", "resume"}:
        if aether_manager.running:
            await matcher.finish("已有 Aether 任务正在运行。\n"+aether_manager.status_text())
        await _recover_task_plan(matcher,bot,event,)
        return
    if action in {"重试", "retry"}:
        if len(parts) < 2:
            await matcher.finish("用法：/aether 重试 <任务编号>")
        try:
            sequence = int(parts[1].lstrip("#"))
        except ValueError:
            await matcher.finish("任务编号必须是整数，例如：/aether 重试 17")
        _, message = aether_manager.retry_task(sequence)
        await matcher.finish(message)
    if action in {"跳过", "skip"}:
        if len(parts) < 2:
            await matcher.finish("用法：/aether 跳过 <任务编号>")
        try:
            sequence = int(parts[1].lstrip("#"))
        except ValueError:
            await matcher.finish("任务编号必须是整数，例如：/aether 跳过 17")
        _, message = aether_manager.skip_task(sequence)
        await matcher.finish(message)

    if action in {"任务", "task", "计划", "plan"}:
        if aether_manager.running:
            await matcher.finish("已有 Aether 任务正在运行。\n"+aether_manager.status_text())

        if len(parts) >= 2:
            await _start_task_plan(
                matcher,
                bot,
                event,
                " ".join(parts[1:]),
            )
            return

        matcher.state["aether_waiting_task_plan"] = True
        await matcher.pause(aether_manager.task_plan_menu()+"\n\n回复：编号/key [省票|平衡|赶时间]；默认省票；回复 q 取消。")

    if action in {"快速", "fast"}:
        if aether_manager.running:
            await matcher.finish("已有 Aether 任务正在运行。\n"+aether_manager.status_text())

        if len(parts) >= 2:
            await _start_preset(
                matcher,
                bot,
                event,
                " ".join(parts[1:]),
                fast_mode=True,
            )
            return

        matcher.state["aether_waiting_preset"] = True
        matcher.state["aether_fast_mode"] = True
        await matcher.pause(aether_manager.preset_menu()+"\n\n快速模式：回复编号或预设 key；回复 q 取消。")

    if action in {"开始", "start"}:
        if aether_manager.running:
            await matcher.finish("已有 Aether 任务正在运行。\n"+aether_manager.status_text())

        if len(parts) >= 2:
            choice_parts = parts[1:]
            fast_mode = False
            if choice_parts[-1].lower() in {"快速", "fast"}:
                fast_mode = True
                choice_parts = choice_parts[:-1]
            if not choice_parts:
                await matcher.finish("用法：/aether 开始 <编号或预设 key> [快速]")
            await _start_preset(
                matcher,
                bot,
                event,
                " ".join(choice_parts),
                fast_mode=fast_mode,
            )
            return

        matcher.state["aether_waiting_preset"] = True
        matcher.state["aether_fast_mode"] = False
        await matcher.pause(aether_manager.preset_menu()+"\n\n回复编号或预设 key；回复 q 取消。")

    await matcher.finish(_help_text())


@aether.handle()
async def handle_preset_selection(matcher: Matcher,bot: Bot,event: Event,) -> None:
    if matcher.state.get("aether_waiting_task_plan"):
        choice = event.get_plaintext().strip()
        if choice.lower() in {"q", "quit", "取消"}:
            await matcher.finish("已取消启动 Aether 批量任务。")
        await _start_task_plan(matcher,bot,event,choice,)
        return
    if not matcher.state.get("aether_waiting_preset"):
        return
    choice = event.get_plaintext().strip()
    if choice.lower() in {"q", "quit", "取消"}:
        await matcher.finish("已取消启动 Aether。")

    await _start_preset(
        matcher,
        bot,
        event,
        choice,
        fast_mode=bool(matcher.state.get("aether_fast_mode")),
    )

aetheritem = on_command("aetheritem",aliases={"雷渊物品","AEI"},block=True)
@aetheritem.handle()
async def handle_preset_selection(matcher: Matcher,bot: Bot,event: Event,) -> None:
    if not MGPLUGIN.getPluginState():
        return
    if not MGPLUGIN.getGroupPluginState(event):
        return

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
