from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata
from nonebot.plugin import on_command
from nonebot.adapters import Message
from nonebot.params import CommandArg,EventPlainText
from nonebot.matcher import Matcher
from nonebot.adapters.onebot.v11 import Bot,MessageSegment,Event,GroupMessageEvent,PrivateMessageEvent
from nonebot.adapters.onebot.v11.event import MessageEvent
from nonebot.plugin import on_message

import pathlib
import json

from ...libraries.tools import *
from ...libraries.pluginmanage.tools import *
from ...libraries.finaltest.test import *

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="finaltest",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

TAG="finaltest"
MGPLUGIN=MGPlugin(TAG)

#路径设置
ROOT_PATH=pathlib.Path(__file__).resolve().parent.parent.parent.parent #/server
DATA_PATH=ROOT_PATH/"data"/TAG

test=on_command("期末刷题")
@test.handle()
async def choose(matcher:Matcher,bot:Bot,event:MessageEvent,args: Message = CommandArg()):
    if not MGPLUGIN.getPluginState():
        return
    if not MGPLUGIN.getGroupPluginState(event):
        return
    arg=args.extract_plain_text().strip()
    if not arg:
        selections=listall()
        msg="请提供想要刷题的题集名称，当前可用：\n"
        for s in selections:
            msg+=f"  - {s}\n"
        await test.finish(msg)
    if arg=="继续":
        TEST:Test=config.TESTS[getGroupID(event)]
        question=TEST.choose()
        await test.pause(question["question"]+f"\n当前成绩： {TEST.state[0]} 次正确 / {TEST.state[1]} 次错误\n剩余 {len(TEST.test)} 题")
    if getGroupID(event) in config.TESTS:
        if config.TESTS[getGroupID(event)]:
            await test.finish("你有正在进行的测试")
    TEST=Test(arg)
    if not TEST.available:
        selections=listall()
        msg="提供题集名称不存在，当前可用：\n"
        for s in selections:
            msg+=f"  - {s}\n"
        await test.finish(msg)
    config.TESTS[getGroupID(event)]=TEST
    question=TEST.choose()
    await test.pause(question["question"]+f"\n当前成绩： {TEST.state[0]} 次正确 / {TEST.state[1]} 次错误\n剩余 {len(TEST.test)} 题")

@test.handle()
async def answer(matcher:Matcher,bot:Bot,event:MessageEvent,msg_text: str = EventPlainText()):
    TEST:Test=config.TESTS[getGroupID(event)]
    if not getGroupID(event) in config.TESTS:
        await test.finish("题库不存在")
    if not TEST.available:
        await test.finish("测试已结束")
    arg=msg_text.strip()
    if arg in ["退出","stop","quit"]:
        del config.TESTS[getGroupID(event)]
        await test.finish("测试已停止")
    if TEST.verify(arg):
        await test.send("回答正确")
    else:
        await test.send(f"回答错误，正确答案：{TEST.now["answer"]}")
    question=TEST.choose()
    await test.reject(question["question"]+f"\n当前成绩： {TEST.state[0]} 次正确 / {TEST.state[1]} 次错误\n剩余 {len(TEST.test)} 题")
