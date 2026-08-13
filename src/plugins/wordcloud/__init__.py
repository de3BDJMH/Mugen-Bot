from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata
from nonebot.plugin import on_command
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot.matcher import Matcher
from nonebot.adapters.onebot.v11 import Bot,MessageSegment,Event,GroupMessageEvent,PrivateMessageEvent
from nonebot.adapters.onebot.v11.event import MessageEvent
from nonebot.plugin import on_message
from nonebot import get_bot

from nonebot import require
require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler
from .config import Config

import pathlib
import datetime
from collections import Counter
import asyncio
import pytz
import jieba

from ...libraries.tools import *
from ...libraries.wordcloud import wc

__plugin_meta__ = PluginMetadata(
    name="WordCloud",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

TAG="wordcloud"
MGPLUGIN=MGPlugin(TAG)

DATA_PATH=MGPLUGIN.data_path

SAVEPATH=DATA_PATH/"output"

def isbot(user_id:int)->bool:
    for id in wc.BAN:
        if type(id)==tuple:
            if id[0]<=user_id<=id[1]:
                return True
        elif id==user_id:
            return True
    return False

wcGnerate=on_command("词云",block=True)
@wcGnerate.handle()
async def _(matcher:Matcher,bot:Bot,event:GroupMessageEvent,args: Message = CommandArg()):

    if not MGPLUGIN.getPluginState():
        return
    if not MGPLUGIN.getGroupPluginState(event):
        return
    
    arg=args.extract_plain_text().strip().split(" ")
    if not arg:
        return
    try:
        days=int(arg[0])
    except:
        return
    if len(arg)>1:
        group_id=int(arg[1])
    else:
        group_id=event.group_id
    group=wc.Group(group_id)
    today=datetime.date.today()
    data=Counter()
    members=await bot.get_group_member_list(group_id=group_id)
    users=[]
    for mem in members:
        if not isbot(mem["user_id"]):
            users.append(mem["user_id"])
    for n in range(days):
        date=today-datetime.timedelta(days=n)
        for id in users:
            tmp=group.get_user_data(id,(date.year,date.month,date.day))
            if tmp:
                data.update(tmp)
    #不定时更新就不需要这个了
    # #加入当天数据
    # if datetime.datetime.now().hour<4:
    #     today=today-datetime.timedelta(days=1)
    #     timestamp=int(datetime.datetime(today.year,today.month,today.day,0,0,0).timestamp())#4点更新，0-4的时候前一天还没更新，需要获取一遍
    # else:
    #     timestamp=int(datetime.datetime(today.year,today.month,today.day,0,0,0).timestamp())
    # messages=group.get_msg(timestamp)
    # msgs=[]
    # for msg in messages:
    #     if isbot(msg["user_id"]):
    #         continue
    #     for m in msg["message"]:
    #         if m["type"]=="text":
    #             msgs.append(m["data"]["text"])
    # text="".join(msgs)
    # words=Counter(jieba.lcut(text))
    # data.update(words)
    path=SAVEPATH/f"{group_id}.png"
    if "\n" in data:#有换行会无法运行
        del data["\n"]
    path=wc.generate(data,path)
    await wcGnerate.finish(MessageSegment.image(path))

wcUpdate=on_command("更新词频",block=True)
@wcUpdate.handle()
async def _(matcher:Matcher,bot:Bot,event:GroupMessageEvent,args: Message = CommandArg()):

    if not MGPLUGIN.getPluginState():
        return
    if not MGPLUGIN.getGroupPluginState(event):
        return
    
    if event.user_id!=2404164262:
        return
    arg=args.extract_plain_text().strip()
    if not arg:
        return
    try:
        days=int(arg)
    except:
        return
    today=datetime.datetime.now()
    end=int(datetime.datetime(today.year,today.month,today.day,0,0,0).timestamp())
    tasks=[]
    for d in range(1,days+1):
        start=(today-datetime.timedelta(d)).timestamp()
        group_list=await bot.get_group_list()

        sem = asyncio.Semaphore(10)
        async def process_group(group_id, start, end):
            async with sem:
                group = wc.Group(group_id)
                await asyncio.to_thread(group.save_words, start, end)
                del group
        tasks=[]
        for g in group_list:
            tasks.append(process_group(g["group_id"], start, end))
            # group=wc.Group(g["group_id"])
            # print(f"当前正在处理群聊：{group.group_id}\n结束时间戳：{start}")
            # task=asyncio.to_thread(group.save_words, start, end)
            # tasks.append(task)
            # #group.save_words(start,end)
            # del group
        await asyncio.gather(*tasks)
        end=start
    #results=await asyncio.gather(*tasks, return_exceptions=True)
    await wcUpdate.send(f"词频更新完成！")

#将每日定时更新改为随时更新
"""tz = pytz.timezone('Asia/Shanghai')
@scheduler.scheduled_job('cron', hour=4, minute=0, timezone=tz)
async def update_words():
    bot=get_bot()
    await bot.call_api("send_group_msg",message="开始更新词频",group_id=640447991)
    today=datetime.datetime.now()
    end=int(datetime.datetime(today.year,today.month,today.day,0,0,0).timestamp())
    tasks=[]
    start=(today-datetime.timedelta(days=1)).timestamp()
    group_list=await bot.get_group_list()
    for g in group_list:
        group=wc.Group(g["group_id"])
        print(f"当前正在处理群聊：{group.group_id}\n结束时间戳：{start}")
        task=asyncio.to_thread(group.save_words, start, end)
        tasks.append(task)
    results=await asyncio.gather(*tasks, return_exceptions=True)
    await bot.call_api("send_group_msg",message="词频更新完成！",group_id=640447991)"""

wcHandle=on_message()
@wcHandle.handle()
async def wch(matcher:Matcher,bot:Bot,event:GroupMessageEvent):
    msg=event.get_message().extract_plain_text().strip()
    if not msg:
        return
    group_id=event.group_id
    group=wc.Group(group_id)
    group.save_msg_words(msg,event.user_id)

TARGET_USER = 2404164262
MESSAGE = "无限，该续座啦～"

# 定时任务
@scheduler.scheduled_job(
    "cron",
    hour=18,
    minute="0,5,10",
    id="daily_private_msg"
)
async def daily_task():
    bot=get_bot()
    await bot.send_private_msg(
        user_id=TARGET_USER,
        message=MESSAGE
    )