from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata
from nonebot.plugin import on_command,on_message
from nonebot.adapters import Message
from nonebot.params import CommandArg,Arg,EventMessage
from nonebot.matcher import Matcher
from nonebot.adapters.onebot.v11 import Bot,MessageSegment,Event,GroupMessageEvent,PrivateMessageEvent,MessageEvent
from nonebot import get_bot


import pathlib
import random
import requests

from ...libraries.tools import *

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="chat",
    description="一些随机触发的简单聊天互动功能",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

TAG="chat"
MGPLUGIN=MGPlugin(TAG)

DATA_PATH=MGPLUGIN.data_path

FITBS=['1111', '1111', '1111', '1111', '1111', '1111', '1110', '1111', '1110', '1111', '1110', '1110', '1111', '1110', '1111', '1110', '1110', '1111', '1110', '1110', '1100', '1100', '1110', '1100', '1100', '1110', '1100', '1101', '1101', '1100', '1110', '1100', '1100', '1101', '1100', '1100', '1010', '1100', '1000', '1010', '1000', '1100', '1000', '1000', '1010', '1000', '1001', '1000', '1000', '1001', '1000', '1000']

chat=on_message()
@chat.handle()
async def chats(matcher:Matcher,bot:Bot,event:Event,message: Message = EventMessage()):

    if not MGPLUGIN.getPluginState():
        return
    if not MGPLUGIN.getGroupPluginState(event):
        return
    
    msg=message.extract_plain_text()

    #我喜欢你
    if "我喜欢你"==msg or "咱俩试试？"==msg:
        probabilities=jsonLoad(DATA_PATH/"probability.json")
        probabilities=[(s,probabilities[s]) for s in probabilities]
        p=0
        r=random.random()
        while r>=0:
            r=r-probabilities[p][1]
            p+=1
        await chat.finish(probabilities[p-1][0])

reverse = on_command("反转", block=True)
@reverse.handle()
async def handle_function(matcher:Matcher,bot:Bot,event:Event,args: Message = CommandArg()):

    if not MGPLUGIN.getPluginState():
        return
    if not MGPLUGIN.getGroupPluginState(event):
        return

    TRANSLATE=jsonLoad(DATA_PATH/"reversechar.json")
    arg=args.extract_plain_text()
    msg=""
    for c in arg:
        if c in TRANSLATE:
            msg=TRANSLATE[c]+msg
        else:
            msg=c+msg
    await reverse.finish(msg)

fitbs=on_command("fitbs")
@fitbs.handle()
async def handle_function(matcher:Matcher,bot:Bot,event:MessageEvent,args: Message = CommandArg()):

    if not MGPLUGIN.getPluginState():
        return
    if not MGPLUGIN.getGroupPluginState(event):
        return
    
    arg=args.extract_plain_text()[0]
    txtl=0
    if "0"<=arg<="9" or "a"<=arg<="z" or "A"<=arg<="Z":
        txtl+=2
        return
    else:
        txtl+=5
    msgs=[]
    msg=""
    for l in FITBS:
        tmp=l.replace("00","　　 ")
        tmp=tmp.replace("0","　 ")
        tmp=tmp.replace("1",arg)
        msg+=tmp+"\n"
    msgs.append(
        {
            "type": "node",
            "data": {
                "name": "プラナ",
                "uin": str(event.self_id),
                "content": msg
            }
        }
    )
    bot=get_bot()
    if "message.group" in event.get_event_name():
        await bot.call_api("send_group_forward_msg",group_id=event.group_id,messages=msgs)
    elif "message.private" in event.get_event_name():
        await bot.call_api("send_private_forward_msg",user_id=event.user_id,messages=msgs)

mytest=on_command("Mugen!")
@mytest.handle()
async def mytest_handle(event:MessageEvent):
    url = "http://127.0.0.1:3000/get_group_msg_history"

    payload = json.dumps({
    "group_id": event.group_id,
    "message_seq": 0,
    "count": 1,
    "reverseOrder": False
    })
    headers = {
    'Authorization': 'Bearer ',
    'Content-Type': 'application/json'
    }

    response = requests.request("POST", url, headers=headers, data=payload)
    #await mytest.send(response.text)
    if response.json()["data"]["messages"][0]["message_seq"]%1==0:
        await mytest.send(MessageSegment.reply(event.message_id)+MessageSegment.at((event.user_id))+" ，你发送了本群第"+str(response.json()["data"]["messages"][0]["message_seq"])+"条消息！")
    payload = json.dumps({
    "group_id": 558248216,
    "message_seq": 0,
    "count": 1,
    "reverseOrder": False
    })
    headers = {
    'Authorization': 'Bearer ',
    'Content-Type': 'application/json'
    }

    response = requests.request("POST", url, headers=headers, data=payload)
    #await mytest.send(response.text)
    if response.json()["data"]["messages"][0]["message_seq"]%1==0:
        await mytest.send("APM当前消息条数："+str(response.json()["data"]["messages"][0]["message_seq"]))
    # bot=get_bot()
    # groups=await bot.call_api("get_group_list")
    # with open(r"D:\LLOneBot\guess\guess\plugins\phigros\_groups.json","w",encoding="utf-8") as f:
    #     json.dump(groups,f,indent=4)
    await mytest.finish(MessageSegment.reply(event.message_id)+"de3BDJMH：干什么呀~")
