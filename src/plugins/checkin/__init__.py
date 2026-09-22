from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata
from nonebot.plugin import on_command,on_message
from nonebot.adapters import Message
from nonebot.params import CommandArg,Arg,EventMessage,ArgPlainText,Depends
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
from ...services import checkin as checkin_service

from . import command
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
def plugin_enabled(event:MessageEvent)->bool:
    if not MGPLUGIN.getPluginState():
        return False
    return MGPLUGIN.getGroupPluginState(event)

DATA_PATH=MGPLUGIN.data_path

checkin=on_command("签到",aliases={"checkin"},rule=plugin_enabled)
@checkin.handle()
async def handle_function(bot:Bot,cmd:command.Checkin=Depends(command.Checkin.get)):
    bot=get_bot()
    user=tools.User(cmd.user_id)
    now=datetime.datetime.now(ZoneInfo("Asia/Shanghai"))
    if not user.nickname:
        nickname=(await bot.get_stranger_info(user_id=cmd.user_id,no_cache=True))["nickname"]
        user.nickname=nickname
        user.updateUserInfo()
    if user.last_check==now.date():
        await checkin.finish("宝宝你今天已经签过到了哦——")
    rating_before=f"{user.getRating()["rating"]:.2f}"
    voltage_before=tools.getVoltageLevel(float(rating_before))
    result=user.check()
    rating_after=f"{user.getRating()["rating"]:.2f}"
    voltage_after=tools.getVoltageLevel(float(rating_after))
    msg=""
    if rating_before!=rating_after or voltage_before!=voltage_after:
        if voltage_before==voltage_after:
            msg+=f"[ {voltage_after} ]    {rating_before} -> {rating_after}\n"
        elif rating_before==rating_after:
            msg+=f"[ {voltage_before} ] -> [ {voltage_after} ]    {rating_after}\n"
        else:
            msg+=f"[ {voltage_before} ] -> [ {voltage_after} ]    {rating_before} -> {rating_after}\n"
    if result["first"]=="year":
        msg+=f"( x{round(result["rankbonus"],2)} )  你是 {now.year}年 第 1 个签到的群友！\n"
    elif result["first"]=="month":
        msg+=f"( x{round(result["rankbonus"],2)} )  你是 {now.month}月 第 1 个签到的群友！\n"
    else:
        if result["rankbonus"]!=1:
            msg+=f"( x{round(result["rankbonus"],2)} )  "
        msg+=f"你是今天第 {result["rank"]} 个签到的群友！\n"
    msg+=f"( x{round(result["consecutivebonus"],2)} )  你已经连续签到 {user.consecutive_check} 天啦~\n"
    if result["thursday"]:
        msg+=f"( +50MB )  今天是周四，Mugen决定送你 50MB ！\n"
    if result["super"] is not None:
        msg+=f"( +{result["super"].display} )  运气不错哇——你获得了 {result["super"].display} ！\n"
    msg+=f"( +{result["basedata"].display} )  签到获得了 {result["basedata"].display} 哦\n"
    msg+=f"Data +{result["data"].display}"
    for i in result["items"]:
        msg+=f"\n获得了 {i["name"]} x1"
    await checkin.finish(msg)

makeup=on_command("补签",aliases={"makeup","补签"},rule=plugin_enabled)
@makeup.handle()
async def handle_function(matcher:Matcher,cmd:command.MakeUp=Depends(command.MakeUp.get)):

    user=tools.User(cmd.user_id)
    now=datetime.datetime.now(ZoneInfo("Asia/Shanghai"))
    if not user.nickname:
        await makeup.finish("还没有你的信息呢，签到试试看吧？")
    checklogs=checkin_storage.get_checkin_dates(user.id)
    if not checklogs:
        await makeup.finish("没有找到可以补签的日期呢")
    yesterday=now.date()-datetime.timedelta(days=1)
    if checklogs[-1]<yesterday:
        checkdate=datetime.datetime.combine(yesterday,datetime.time(),ZoneInfo("Asia/Shanghai"))
    else:
        for i in range(len(checklogs)-1,0,-1):
            if (checklogs[i]-checklogs[i-1]).days>1:
                checkdate=checklogs[i]-datetime.timedelta(days=1)#补签日期
                checkdate=datetime.datetime.combine(checkdate,datetime.time(),ZoneInfo("Asia/Shanghai"))
                break
        else:
            await makeup.finish("没有找到可以补签的日期呢")
    checkcost=tools.makeup_cost(now,checkdate,user.getRating()["rating"])
    matcher.state["user_id"]=user.id
    matcher.state["checkdate"]=checkdate
    await makeup.send(f"补签 {checkdate.date()} 需要消耗 {checkcost.display}，回复ok确认")

@makeup.got("confirm")
async def _(matcher:Matcher,confirm:str=ArgPlainText()):
    if confirm.lower()!="ok":
        await makeup.finish("已取消")

    user=tools.User(matcher.state["user_id"])
    checkdate=matcher.state["checkdate"]

    result=user.makeup_check(checkdate)
    if not result["success"]:
        await makeup.finish(result["msg"])
    await makeup.finish("完成啦——")

selfinfo=on_command("/data",aliases={"/info"},rule=plugin_enabled)
@selfinfo.handle()
async def handle_function(matcher:Matcher,bot:Bot,cmd:command.SelfInfo=Depends(command.SelfInfo.get)):
    user=tools.User(cmd.user_id)
    if not user.nickname:
        await selfinfo.finish("还没有你的信息呢，签到试试看吧？")
    
    if cmd.plain_text=="text":#请求文字信息
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
                    "uin": str(cmd.self_id),
                    "content": msg
                }
            }
        ]
        if cmd.message_type=="group":
            await bot.send_group_forward_msg(group_id=cmd.group_id, messages=msgs)
        elif cmd.message_type=="private":
            await bot.send_private_forward_msg(user_id=cmd.user_id, messages=msgs)
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

send=on_command("赠送",aliases={"send"},rule=plugin_enabled)
@send.handle()
async def handle_function(bot:Bot,cmd:command.Send=Depends(command.Send.get)):
    sender=tools.User(cmd.user_id)
    reciver=tools.User(cmd.target_id)
    if cmd.user_id==cmd.target_id:#送自己，以前居然没发现这个bug，一直有人尝试抢自己但是没人send自己就很搞笑
        await send.finish(MessageSegment.reply(cmd.message_id)+"？")
    if not sender.nickname:
        await send.finish("还没有你的信息呢，签到试试看吧？")
    if not reciver.nickname:
        nickname=(await bot.get_stranger_info(user_id=cmd.target_id,no_cache=True))["nickname"]
        reciver=tools.User(cmd.target_id,nickname)

    send_data=cmd.send_data
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

checkrank=on_command("签到排行榜",aliases={"签到排名","签到排行"},rule=plugin_enabled)
@checkrank.handle()
async def handle_function(cmd:command.CheckRank=Depends(command.CheckRank.get)):
    today=tools.CheckDay(datetime.datetime.now(ZoneInfo("Asia/Shanghai")))
    if not today.info:
        await checkrank.finish("今天还没有人签到哦~")
    msg,me=today.generateCheckedRank(cmd.user_id)
    msg=f"{today.day}签到排行榜：\n{msg}"
    if not me:
        msg+=f"\n你还没有签到哦~\n"
    
    await checkrank.finish(msg.rstrip("\n"))

datarank=on_command("data排行榜",aliases={"data排名","data排行"},rule=plugin_enabled)
@datarank.handle()
async def handle_function(cmd:command.DataRank=Depends(command.DataRank.get)):
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
    msg,me=tools.generateRank(ranks,cmd.user_id)
    msg=f"Data排行榜：\n{msg}"
    if not me:
        msg+=f"\n你还没有Data哦~\n"
    
    await datarank.finish(msg.rstrip("\n"))

ratingrank=on_command("rating排行榜",aliases={"rating排名","rating排行","rt排行榜","rt排名","rt排行"},rule=plugin_enabled)
@ratingrank.handle()
async def handle_function(cmd:command.RatingRank=Depends(command.RatingRank.get)):
    ranks=[]
    for user in checkin_storage.get_all_user_data():
        rating=checkin_service.get_user_rating(user["user_id"])
        if user["nickname"] and rating:
            ranks.append([
                user["user_id"],
                user["nickname"],
                f"[ {tools.getVoltageLevel(rating['rating'])} ] {rating['rating']:.2f}",
                rating['rating']
            ])
    ranks.sort(key=lambda x:x[3],reverse=True)
    ranks=[r[:3] for r in ranks]
    msg,me=tools.generateRank(ranks,cmd.user_id)
    msg=f"Rating排行榜：\n{msg}"
    if not me:
        msg+=f"\n你还没有数据哦~\n"
    
    await ratingrank.finish(msg.rstrip("\n"))

datatrend=on_command("data趋势",aliases={"data变化","datatrend","/dt"},rule=plugin_enabled)
@datatrend.handle()
async def handle_function(cmd:command.DataTrend=Depends(command.DataTrend.get)):
    user=tools.User(cmd.user_id)
    if not user.nickname:
        await datatrend.finish("还没有你的信息呢，签到试试看吧？")
    lines=cmd.lines
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

# nickrefresh=on_command("/更新数据库")
# @nickrefresh.handle()
# async def handle_function(matcher:Matcher,bot:Bot,event:MessageEvent,args: Message = CommandArg()):
#     mgconfig=jsonLoad(ROOT_PATH/"data"/"pluginmanage"/"config.json")
#     if not event.user_id in mgconfig["op"]:
#         await nickrefresh.finish("权限不足")
    
#     await nickrefresh.send("更新中...")
#     users=checkin_storage.get_all_users()
#     statistic=[0,0]#更新人数，更改发生变化人数
#     for user in users:
#         statistic[0]+=1
#         user_id=user["user_id"]
#         print(user_id)
#         nickname=(await bot.get_stranger_info(user_id=user_id,no_cache=True))["nickname"]
#         if user["nickname"]!=nickname:
#             statistic[1]+=1
#             checkin_storage.update_user_nickname(user_id,nickname)
#     await nickrefresh.finish(f"更新完毕，本次更新 {statistic[0]} 人，实际更新 {statistic[1]} 人数据")
