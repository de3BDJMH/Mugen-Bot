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
from zoneinfo import ZoneInfo

from ...libraries.tools import *
from ...libraries.checkin import tools
from ...libraries.checkin import trendPaint
from ...libraries.checkin import infoPaint
from ...storage import checkin as checkin_storage

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
    now=datetime.datetime.now(ZoneInfo("Asia/Shanghai"))
    if not user.nickname:
        nickname=(await bot.get_stranger_info(user_id=event.user_id,no_cache=True))["nickname"]
        user.nickname=nickname
        user.updateUserInfo()
    if user.last_check==now.date():
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
    
    if args.extract_plain_text().strip()=="text":#请求文字信息
        robtimes_ranks,robbedtimes_ranks,rob_gain_data_ranks,rob_give_data_ranks=user.getRobInfo()

        rob_times=robtimes_ranks.get(user.id,[0,0,user.id,user.nickname])#防止缺少键，有些用户的数据不是全都完整的
        robbed_times=robbedtimes_ranks.get(user.id,[0,0,user.id,user.nickname])
        rob_gain=rob_gain_data_ranks.get(user.id,[tools.Data([0,0],zero=True),tools.Data([0,0],zero=True),user.id,user.nickname])
        rob_give=rob_give_data_ranks.get(user.id,[tools.Data([0,0],zero=True),tools.Data([0,0],zero=True),user.id,user.nickname])

        msg=f"{user.nickname if user.id!=2404164262 else user.data.display} 的个人信息：\n"#无限专属个人信息！
        if user.last_check==datetime.datetime.now(ZoneInfo("Asia/Shanghai")).date():
            msg+=f"  今日已签到\n"
        else:
            msg+=f"  今日未签到\n"
        msg+=f"  - Data: {user.data.display if user.id!=2404164262 else '无限！'}\n"#小彩蛋
        msg+=f"  - 累计签到天数: {user.total_check} 天\n"
        msg+=f"  - 当前连续签到天数: {user.consecutive_check} 天\n"
        msg+=f"  - 最大连续签到天数: {user.max_consecutive_check} 天\n"
        rob_most=[None,0]
        for rob_user in user.robbed:
            times=user.robbed[rob_user]["success_times"]+user.robbed[rob_user]["fail_times"]
            if times>rob_most[1]:
                rob_most=[rob_user,times]
        if rob_most[0] is not None:
            rob_user_info=checkin_storage.get_user(rob_most[0])
            msg+=f"  - 你最喜欢抢谁: {rob_user_info['nickname']}，抢了 {rob_most[1]} 次\n"
        else:
            msg+=f"  - 你还没有抢过别人呢\n"
        robbed_most=[None,0]
        for record in checkin_storage.get_rob_records_by_target(user.id):
            times=record["success_times"]+record["fail_times"]
            if times>robbed_most[1]:
                robbed_most=[record,times]
        if robbed_most[0] is not None:
            msg+=f"  - 最喜欢抢你的人: {robbed_most[0]['nickname']}，被抢了 {robbed_most[1]} 次\n"
        else:
            msg+=f"  - 还没有人抢过你呢\n"
        msg+=f"  - 抢劫总次数: {rob_times[0]+rob_times[1]}（成功 {rob_times[0]} 次，失败 {rob_times[1]} 次）\n"
        msg+=f"  - 被抢总次数: {robbed_times[0]+robbed_times[1]} 次\n"
        msg+=f"  - 抢到的Data: {tools.plus(rob_gain[0],rob_gain[1]).display}（主动抢到 {rob_gain[0].display}，被送了 {rob_gain[1].display}）\n"
        msg+=f"  - 失去的Data: {tools.plus(rob_give[0],rob_give[1]).display}（被抢走 {rob_give[0].display}，主动送出了 {rob_give[1].display}）\n"
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
    now=datetime.datetime.now(ZoneInfo("Asia/Shanghai"))
    tools.log(user_id=sender.id,operation="send",change_type="-",related_user_id=reciver.id,data=send_data,created_at=now)
    reciver.updateUserInfo()
    tools.log(user_id=reciver.id,operation="send",change_type="+",related_user_id=sender.id,data=send_data,created_at=now)

    await send.finish(f"成功向 {reciver.nickname} 赠送了 {send_data.display}")

checkrank=on_command("签到排行榜",aliases={"签到排名","签到排行"})
@checkrank.handle()
async def handle_function(matcher:Matcher,bot:Bot,event:MessageEvent,args: Message = CommandArg()):

    if not MGPLUGIN.getPluginState():
        return
    if not MGPLUGIN.getGroupPluginState(event):
        return
    
    today=tools.CheckDay(datetime.datetime.now(ZoneInfo("Asia/Shanghai")))
    if not today.info:
        await checkrank.finish("今天还没有人签到哦~")
    msg,me=today.generateCheckedRank(event.user_id)
    msg=f"{today.day}签到排行榜：\n{msg}"
    if not me:
        msg+=f"\n你还没有签到哦~\n"
    
    await checkrank.finish(msg.rstrip("\n"))

datarank=on_command("data排行榜",aliases={"data排名","data排行"})
@datarank.handle()
async def handle_function(matcher:Matcher,bot:Bot,event:MessageEvent,args: Message = CommandArg()):

    if not MGPLUGIN.getPluginState():
        return
    if not MGPLUGIN.getGroupPluginState(event):
        return
    
    ranks=[]
    for user in checkin_storage.get_all_user_data():
        data=tools.Data([user["base"],user["addition"]],user["zero"])
        if user["nickname"] and data.getBytes()>0:
            ranks.append([
                user["user_id"],
                user["nickname"],
                data.display,
                data.getBytes()
            ])
    ranks.sort(key=lambda x:x[3],reverse=True)
    ranks=[r[:3] for r in ranks]
    msg,me=tools.generateRank(ranks,event.user_id)
    msg=f"Data排行榜：\n{msg}"
    if not me:
        msg+=f"\n你还没有Data哦~\n"
    
    await datarank.finish(msg.rstrip("\n"))

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
    lines=100
    if arg := args.extract_plain_text().strip():#日志条数，乱输入默认100
        try:
            lines=int(arg)
            if lines<=0:
                lines=-1
            elif lines<10:#太少不要
                lines=10
        except:
            lines=-100
    logs=user.getLogs(lines)
    for log in logs.copy():
        if not "data" in log:
            logs.remove(log)
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
    users=checkin_storage.get_all_users()
    statistic=[0,0]#更新人数，更改发生变化人数
    for user in users:
        statistic[0]+=1
        user_id=user["user_id"]
        print(user_id)
        nickname=(await bot.get_stranger_info(user_id=user_id,no_cache=True))["nickname"]
        if user["nickname"]!=nickname:
            statistic[1]+=1
            checkin_storage.update_user_nickname(user_id,nickname)
    await nickrefresh.finish(f"更新完毕，本次更新 {statistic[0]} 人，实际更新 {statistic[1]} 人数据")
