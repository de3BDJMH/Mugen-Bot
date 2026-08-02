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
import requests
import os
import time

from ...libraries.tools import *
from ...libraries.checkin import tools
from ...libraries.checkin import trendPaint
from ...libraries.checkin import infoPaint

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="checkin",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

TAG="checkin"
MGPLUGIN=MGPlugin(TAG)

DATA_PATH=MGPLUGIN.data_path

checkin=on_command("签到",aliases={"checkin"})
@checkin.handle()
async def handle_function(matcher:Matcher,bot:Bot,event:MessageEvent,args: Message = CommandArg()):

    if not MGPLUGIN.getPluginState():
        return
    if not MGPLUGIN.getGroupPluginState(event):
        return
    
    bot=get_bot()
    user=tools.User(event.user_id)
    now=datetime.datetime.now()
    if not user.nickname:
        nickname=(await bot.get_stranger_info(user_id=event.user_id,no_cache=True))["nickname"]
        user=tools.User(event.user_id,nickname)
    if user.last_check==now.strftime("%Y-%m-%d"):
        await checkin.finish("宝宝你今天已经签过到了哦——")
    result=user.check()
    if result["first"]=="year":
        msg=f"你是 {now.year}年 第 1 个签到的群友！\n"
    elif result["first"]=="month":
        msg=f"你是 {now.month}月 第 1 个签到的群友！\n"
    else:
        msg=f"你是今天第 {result["rank"]} 个签到的群友！\n"
    msg+=f"你已经连续签到 {user.consecutive_check} 天啦~\n"
    if result["thursday"]:
        msg+=f"( +50MB )  今天是周四，Mugen决定送你 50MB ！\n"
    if result["super"] is not None:
        msg+=f"( +{result["super"].display} )  运气不错哇——你获得了 {result["super"].display} ！\n"
    msg+=f"( +{result["basedata"].display} )  签到获得了 {result["basedata"].display} 哦\n"
    if result["rankbonus"]!=1:
        msg+=f"( x{round(result["rankbonus"],2)} )  哇~是第{result['rank']}个签到的欸，Data x{round(result["rankbonus"],2)}\n"
    msg+=f"Data +{result["data"].display}"
    for i in result["items"]:
        msg+=f"\n获得了 {i["name"]} x1"
    await checkin.finish(msg)

selfinfo=on_command("我的data",aliases={"/data","/info"})
@selfinfo.handle()
async def handle_function(matcher:Matcher,bot:Bot,event:MessageEvent,args: Message = CommandArg()):

    if not MGPLUGIN.getPluginState():
        return
    if not MGPLUGIN.getGroupPluginState(event):
        return
    
    user=tools.User(event.user_id)
    if not user.nickname:
        await selfinfo.finish("还没有你的信息呢，签到试试看吧？")
    
    user_info=jsonLoad(tools.USER_PATH)
    if args.extract_plain_text().strip()=="text":#请求文字信息
        robtimes_ranks,robbedtimes_ranks,rob_gain_data_ranks,rob_give_data_ranks=user.getRobInfo()

        user=tools.User(event.user_id)
        msg=f"{user.nickname if user.id!=2404164262 else user.data.display} 的个人信息：\n"#无限专属个人信息！
        if user.last_check==datetime.datetime.now().strftime("%Y-%m-%d"):
            msg+=f"  今日已签到\n"
        else:
            msg+=f"  今日未签到\n"
        msg+=f"  - Data: {user.data.display if user.id!=2404164262 else '无限！'}\n"#小彩蛋
        msg+=f"  - 累计签到天数: {user.total_check} 天\n"
        msg+=f"  - 当前连续签到天数: {user.consecutive_check} 天\n"
        msg+=f"  - 最大连续签到天数: {user.max_consecutive_check} 天\n"
        rob_most=["",0]
        for rob_user in user.rob_info["robbed"]:
            times=user.rob_info["robbed"][rob_user]["success_times"]+user.rob_info["robbed"][rob_user]["fail_times"]
            if times>rob_most[1]:
                rob_most=[rob_user,times]
        if rob_most[0]:
            msg+=f"  - 你最喜欢抢谁: {user_info[rob_most[0]]['nickname']}，抢了 {rob_most[1]} 次\n"
        else:
            msg+=f"  - 你还没有抢过别人呢\n"
        robbed_most=["",0]
        for rob_user in user.rob_info["robbed_by"]:
            times=user_info[str(rob_user)]["rob"]["robbed"][str(user.id)]["success_times"]+user_info[str(rob_user)]["rob"]["robbed"][str(user.id)]["fail_times"]
            if times>robbed_most[1]:
                robbed_most=[str(rob_user),times]
        if robbed_most[0]:
            msg+=f"  - 最喜欢抢你的人: {user_info[robbed_most[0]]['nickname']}，被抢了 {robbed_most[1]} 次\n"
        else:
            msg+=f"  - 还没有人抢过你呢\n"
        msg+=f"  - 抢劫总次数: {robtimes_ranks[str(user.id)][0]+robtimes_ranks[str(user.id)][1]}（成功 {robtimes_ranks[str(user.id)][0]} 次，失败 {robtimes_ranks[str(user.id)][1]} 次）\n"
        msg+=f"  - 被抢总次数: {robbedtimes_ranks[str(user.id)][0]+robbedtimes_ranks[str(user.id)][1]} 次\n"
        msg+=f"  - 抢到的Data: {tools.plus(rob_gain_data_ranks[str(user.id)][0],rob_gain_data_ranks[str(user.id)][1]).display}（主动抢到 {rob_gain_data_ranks[str(user.id)][0].display}，被送了 {rob_gain_data_ranks[str(user.id)][1].display}）\n"
        msg+=f"  - 失去的Data: {tools.plus(rob_give_data_ranks[str(user.id)][0],rob_give_data_ranks[str(user.id)][1]).display}（被抢走 {rob_give_data_ranks[str(user.id)][0].display}，主动送出了 {rob_give_data_ranks[str(user.id)][1].display}）\n"
        msgs=[
            {
                "type": "node",
                "data": {
                    "name": "プラナ",
                    "uin": str(event.self_id),
                    "content": msg
                }
            }
        ]
        if "message.group" in event.get_event_name():
            await bot.send_group_forward_msg(group_id=event.group_id, messages=msgs)
        elif "message.private" in event.get_event_name():
            await bot.send_private_forward_msg(user_id=event.user_id, messages=msgs)
    else:
        save_path=tools.DATA_PATH/"out"/f"info_{user.id}.png"
        avatar_path=DATA_PATH/"out"/f"avatar_{user.id}.jpg"
        need_download=False
        if not avatar_path.is_file():
            need_download=True
        else:
            mtime = os.path.getmtime(avatar_path)#文件最后修改时间
            if time.time() - mtime > 86400:#是否超过指定时间，86400是1天
                need_download = True
        if need_download:
            avatar_url=f"https://q1.qlogo.cn/g?b=qq&nk={user.id}&s={100}"
            try:
                response = requests.get(avatar_url)
            except Exception as e:
                print(f"下载头像失败：{e}")
                await selfinfo.finish(f"获取头像失败：{e}")
            with open(avatar_path,"wb") as f:
                f.write(response.content)
        infoPaint.paint(user,save_path)
        await selfinfo.finish(MessageSegment.image(save_path))

send=on_command("赠送",aliases={"send"})
@send.handle()
async def handle_function(matcher:Matcher,bot:Bot,event:MessageEvent,args: Message = CommandArg()):

    if not MGPLUGIN.getPluginState():
        return
    if not MGPLUGIN.getGroupPluginState(event):
        return
    
    recive=event.get_message()
    if len(recive)<3:
        return
    if not (recive[1].type=="at" and recive[2].type=="text"):#send @xxx data
        return
    
    sender=tools.User(event.user_id)
    reciver_id=int(recive[1].data["qq"])
    reciver=tools.User(reciver_id)
    if not sender.nickname:
        await send.finish("还没有你的信息呢，签到试试看吧？")
    if not reciver.nickname:
        nickname=(await bot.get_stranger_info(user_id=reciver_id,no_cache=True))["nickname"]
        reciver=tools.User(reciver_id,nickname)
    send_data_unit=20#默认MB
    send_data=recive[2].data["text"].upper()
    for u in list(tools.DATA_UNIT.keys())[::-1]:#倒序，防止先匹配B
        if tools.DATA_UNIT[u] in send_data:
            send_data_unit=u
            send_data=send_data.replace(tools.DATA_UNIT[u],"")
            break
    try:
        send_data=float(send_data)
        if send_data_unit==0:#B不能小数，稍微严谨一些
            send_data=int(send_data)
    except:
        await send.finish("输入数据有误，需要为整数或小数+单位(B KB MB...)，无单位默认MB")
    if send_data<=0 or (send_data<1 and send_data_unit==0):
        await send.finish("笨蛋！你想干什么？！")
    elif send_data>=1024:
        await send.finish("太大了...不可以哦...")

    send_data=tools.Data([send_data_unit,math.log2(send_data)],False)
    if send_data.getBytes()>sender.data.getBytes():
        await send.finish("你还没有这么多Data哦")
    sender.delData(send_data)
    reciver.addData(send_data)
    sender.updateUserInfo()
    tools.log(sender.id,"send","-",send_data,datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    reciver.updateUserInfo()
    tools.log(reciver.id,"send","+",send_data,datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    await send.finish(f"成功向 {reciver.nickname} 赠送了 {send_data.display}")

checkrank=on_command("签到排行榜",aliases={"签到排名","签到排行"})
@checkrank.handle()
async def handle_function(matcher:Matcher,bot:Bot,event:MessageEvent,args: Message = CommandArg()):

    if not MGPLUGIN.getPluginState():
        return
    if not MGPLUGIN.getGroupPluginState(event):
        return
    
    today=tools.CheckDay(datetime.datetime.now())
    if not today.info:
        await checkrank.finish("今天还没有人签到哦~")
    ranks=[]
    for i in range(len(today.info)):
        user_id=today.info[i][0]
        user=tools.User(user_id)
        ranks.append([user_id,user.nickname,today.info[i][1]])
        del user
    msg,me=tools.generateRank(ranks,event.user_id)
    msg=f"{today.day}签到排行榜：\n{msg}"
    if not me:
        msg+=f"\n你还没有签到哦~\n"
    
    await checkrank.finish(msg[:-1])

datarank=on_command("data排行榜",aliases={"data排名","data排行"})
@datarank.handle()
async def handle_function(matcher:Matcher,bot:Bot,event:MessageEvent,args: Message = CommandArg()):

    if not MGPLUGIN.getPluginState():
        return
    if not MGPLUGIN.getGroupPluginState(event):
        return
    
    users=jsonLoad(tools.USER_PATH)
    ranks=[]
    for user_id in users:
        user=tools.User(int(user_id))
        if user.nickname and user.data.getBytes()>0:
            ranks.append([user.id,user.nickname,user.data.display,user.data.getBytes()])
        del user
    ranks.sort(key=lambda x:x[3],reverse=True)
    ranks=[r[:3] for r in ranks]
    msg,me=tools.generateRank(ranks,event.user_id)
    msg=f"Data排行榜：\n{msg}"
    if not me:
        msg+=f"\n你还没有Data哦~\n"
    
    await datarank.finish(msg[:-1])

datatrend=on_command("data趋势",aliases={"data变化","datatrend","/dt"})
@datatrend.handle()
async def handle_function(matcher:Matcher,bot:Bot,event:MessageEvent,args: Message = CommandArg()):

    if not MGPLUGIN.getPluginState():
        return
    if not MGPLUGIN.getGroupPluginState(event):
        return
    
    user=tools.User(event.user_id)
    if not user.nickname:
        await datatrend.finish("还没有你的信息呢，签到试试看吧？")
    lines=-1
    if arg := args.extract_plain_text().strip():#日志条数，乱输入默认全部
        try:
            lines=int(arg)
            if lines<=0:
                lines=-1
            elif lines<10:#太少不要
                lines=10
        except:
            lines=-1
    logs=user.getLogs(lines)
    if not logs:
        await datatrend.finish("你的Data还没有被动过呢...")
    if len(logs)<10:
        await datatrend.finish("你的Data变化记录还不足10条，请多活跃活跃吧！")
    save_path=tools.OUT_PATH/f"trend_{user.id}.png"
    trendPaint.paint(user,logs,save_path)
    await datatrend.finish(MessageSegment.image(save_path))

nickrefresh=on_command("/更新数据库")
@nickrefresh.handle()
async def handle_function(matcher:Matcher,bot:Bot,event:MessageEvent,args: Message = CommandArg()):
    mgconfig=jsonLoad(ROOT_PATH/"data"/"pluginmanage"/"config.json")
    if not event.user_id in mgconfig["op"]:
        await nickrefresh.finish("权限不足")
    
    await nickrefresh.send("更新中...")
    userinfo=jsonLoad(tools.USER_PATH)
    statistic=[0,0]#更新人数，更改发生变化人数
    for user in userinfo:
        statistic[0]+=1
        print(userinfo[user]["id"])
        nickname=(await bot.get_stranger_info(user_id=user,no_cache=True))["nickname"]
        if userinfo[user]["nickname"]!=nickname:
            statistic[1]+=1
            userinfo[user]["nickname"]=nickname
    jsonDump(tools.USER_PATH,userinfo)
    await nickrefresh.finish(f"更新完毕，本次更新 {statistic[0]} 人，实际更新 {statistic[1]} 人数据")
