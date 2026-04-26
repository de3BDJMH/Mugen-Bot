from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata
from nonebot.plugin import on_command,on_message
from nonebot.adapters import Message
from nonebot.params import CommandArg,Arg,EventMessage
from nonebot.matcher import Matcher
from nonebot.adapters.onebot.v11 import Bot,MessageSegment,Event,GroupMessageEvent,PrivateMessageEvent,MessageEvent
from nonebot import get_bot

import pathlib
import datetime
import math

from ...libraries.tools import *
from ...libraries.checkin import tools

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="rob",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

TAG="rob"
MGPLUGIN=MGPlugin(TAG)

DATA_PATH=MGPLUGIN.data_path
CONFIG_PATH=MGPLUGIN.data_path/"config.json"

rob=on_command("抢劫")
@rob.handle()
async def handle_function(matcher:Matcher,bot:Bot,event:GroupMessageEvent,args: Message = CommandArg()):

    if not MGPLUGIN.getPluginState():
        return
    if not MGPLUGIN.getGroupPluginState(event):
        return
    
    recive=event.get_message()
    robbed_user_id=None
    if not recive:
        return
    for m in recive:
        if m.type=="at":#前车之鉴，只给@一个人
            robbed_user_id=int(m.data["qq"])
            break
    if not robbed_user_id:
        return
    robber=tools.User(event.user_id)
    robbed_user=tools.User(robbed_user_id)
    if not robber.nickname:
        await rob.finish("还没有你的信息呢，签到试试看吧？")
    if robbed_user_id==event.user_id:
        await rob.finish("好孩子不抢自己哦")
    if not robbed_user.nickname:
        await rob.finish("他还什么都没有呢...你好坏...")
    if robbed_user.data.getBytes()==0:
        await rob.finish("他什么都没有呢...你好坏...")
    if robber.data.getBytes()==0:
        await rob.finish("你已经一无所有了...")
    msg=robber.rob(robbed_user_id)
    await rob.send(msg)

robrank=on_command("抢劫排行榜",aliases={"抢劫排行","抢劫排名"})
@robrank.handle()
async def handle_function(matcher:Matcher,bot:Bot,event:GroupMessageEvent,args: Message = CommandArg()):

    if not MGPLUGIN.getPluginState():
        return
    if not MGPLUGIN.getGroupPluginState(event):
        return
    
    robtimes_msg="抢劫总次数排行榜：（总/成功/失败）\n"#抢劫次数排名
    robtimes_ranks={}
    robbedtimes_msg="被抢次数排行榜：\n"#被抢次数排名
    robbedtimes_ranks={}
    rob_gain_data_msg="抢到Data量排行榜：（主动抢到的/其他人送的）\n"#抢到data排名(主动抢到/其他人送)
    rob_gain_data_ranks={}
    rob_give_data_msg="被抢走Data量排行榜：（其他人抢走的/主动送出去的）\n"#失去data排名(其他人抢走/主动送出去)
    rob_give_data_ranks={}
    msgs=[]
    #统计数据
    user_info=jsonLoad(tools.USER_PATH)
    for uid in user_info:
        user=tools.User(int(uid))
        if not uid in robtimes_ranks:
            robtimes_ranks[uid]=[0,0,uid,user.nickname]
        for rob_user in user.rob_info["robbed"]:
            robtimes_ranks[uid][0]+=user.rob_info["robbed"][rob_user]["success_times"]
            robtimes_ranks[uid][1]+=user.rob_info["robbed"][rob_user]["fail_times"]
            if not rob_user in robbedtimes_ranks:
                robbedtimes_ranks[rob_user]=[0,0,rob_user,user_info[rob_user]["nickname"]]
            robbedtimes_ranks[rob_user][0]+=user.rob_info["robbed"][rob_user]["success_times"]
            robbedtimes_ranks[rob_user][1]+=user.rob_info["robbed"][rob_user]["fail_times"]
            #初始化
            if not uid in rob_gain_data_ranks:
                rob_gain_data_ranks[uid]=[tools.Data([0,0],True),tools.Data([0,0],True),uid,user.nickname]
            if not uid in rob_give_data_ranks:
                rob_give_data_ranks[uid]=[tools.Data([0,0],True),tools.Data([0,0],True),uid,user.nickname]
            if not rob_user in rob_gain_data_ranks:
                rob_gain_data_ranks[rob_user]=[tools.Data([0,0],True),tools.Data([0,0],True),rob_user,user_info[rob_user]["nickname"]]
            if not rob_user in rob_give_data_ranks:
                rob_give_data_ranks[rob_user]=[tools.Data([0,0],True),tools.Data([0,0],True),rob_user,user_info[rob_user]["nickname"]]
            #user成功，user的gain[0]+data，robuser的give[0]+data
            success_data=tools.Data([user.rob_info["robbed"][rob_user]["success_data"]["base"],user.rob_info["robbed"][rob_user]["success_data"]["addition"]],user.rob_info["robbed"][rob_user]["success_data"]["zero"])
            rob_gain_data_ranks[uid][0]=tools.plus(rob_gain_data_ranks[uid][0],success_data)
            rob_give_data_ranks[rob_user][0]=tools.plus(rob_give_data_ranks[rob_user][0],success_data)
            #user失败，user的give[1]+data，robuser的gain[1]+data
            fail_data=tools.Data([user.rob_info["robbed"][rob_user]["fail_data"]["base"],user.rob_info["robbed"][rob_user]["fail_data"]["addition"]],user.rob_info["robbed"][rob_user]["fail_data"]["zero"])
            rob_give_data_ranks[uid][1]=tools.plus(rob_give_data_ranks[uid][1],fail_data)
            rob_gain_data_ranks[rob_user][1]=tools.plus(rob_gain_data_ranks[rob_user][1],fail_data)
        del user
    #排序
    robtimes_ranks=sorted(robtimes_ranks.values(),key=lambda x:x[1],reverse=True)
    robtimes_rank=[[i[2],i[3],f"{i[0]+i[1]} ( {i[0]} / {i[1]} ) 次"] for i in robtimes_ranks]
    robbedtimes_ranks=sorted(robbedtimes_ranks.values(),key=lambda x:x[1],reverse=True)
    robbedtimes_rank=[[i[2],i[3],f"{i[0]+i[1]} 次"] for i in robbedtimes_ranks]
    rob_gain_data_ranks=sorted(rob_gain_data_ranks.values(),key=lambda x:(x[0].getBytes()+x[1].getBytes()),reverse=True)
    rob_gain_data_rank=[[i[2],i[3],f"{tools.plus(i[0], i[1]).display} ({i[0].display} / {i[1].display})"] for i in rob_gain_data_ranks]
    rob_give_data_ranks=sorted(rob_give_data_ranks.values(),key=lambda x:(x[0].getBytes()+x[1].getBytes()),reverse=True)
    rob_give_data_rank=[[i[2],i[3],f"{tools.plus(i[0], i[1]).display} ({i[0].display} / {i[1].display})"] for i in rob_give_data_ranks]
    #生成消息
    msg,me=tools.generateRank(robtimes_rank,str(event.user_id))
    robtimes_msg+=msg
    if not me:
        robtimes_msg+=f"\n你还没有抢劫过呢"
    msg,me=tools.generateRank(robbedtimes_rank,str(event.user_id))
    robbedtimes_msg+=msg
    if not me:
        robbedtimes_msg+=f"\n你还没有被抢过呢"
    msg,me=tools.generateRank(rob_gain_data_rank,str(event.user_id))
    rob_gain_data_msg+=msg
    if not me:
        rob_gain_data_msg+=f"\n你还没有抢到过Data呢"
    msg,me=tools.generateRank(rob_give_data_rank,str(event.user_id))
    rob_give_data_msg+=msg
    if not me:
        rob_give_data_msg+=f"\n你还没有失去过Data呢"
    for m in [robtimes_msg,robbedtimes_msg,rob_gain_data_msg,rob_give_data_msg]:
        msgs.append(
            {
                "type": "node",
                "data": {
                    "name": "プラナ",
                    "uin": str(event.self_id),
                    "content": m
                }
            }
        )
    
    await bot.send_group_forward_msg(group_id=event.group_id, messages=msgs)