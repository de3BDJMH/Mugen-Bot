from nonebot import get_plugin_config,get_driver,require,get_bot
from nonebot.plugin import PluginMetadata
from nonebot.adapters.onebot.v11 import Bot,MessageSegment,Event,GroupMessageEvent,PrivateMessageEvent,MessageEvent
from nonebot.plugin import on_command,on_message
from nonebot.params import CommandArg,Arg,EventMessage,ArgPlainText,Depends
from nonebot.matcher import Matcher

require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler

import datetime

from ...libraries.tools import *
from ...services import gtnhpr as gtnhpr_service
from ...storage.gtnhpr import gtnhpr as gtnhpr_storage
from ...storage.gtnhpr import release as release_storage
from ...render.gtnhpr import render as gtnhpr_render
from ...render.gtnhpr import release_render as gtnhpr_release_render
#from ...render.gtnhpr import wiki as wiki_render
from . import command

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="gtnhpr",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

#初始化数据库
driver=get_driver()

@driver.on_startup
async def init_log_database():
    conn=gtnhpr_storage.connect()
    try:
        gtnhpr_storage.init(conn)
        release_storage.init(conn)
        conn.commit()
    finally:
        conn.close()

TAG="gtnhpr"
MGPLUGIN=MGPlugin(TAG)
def plugin_enabled(event:MessageEvent)->bool:
    if not MGPLUGIN.getPluginState():
        return False
    return MGPLUGIN.getGroupPluginState(event)

testpr=on_command("/gtnhpr",rule=plugin_enabled)
@testpr.handle()
async def handle(event:MessageEvent,cmd:command.Pr=Depends(command.Pr.get)):
    records=gtnhpr_service.get_last_sent_pr(10)
    msgs=[{
            "type": "node",
            "data": {
                "name": f"PR",
                "uin": str(cmd.self_id),
                "content": MessageSegment.image(image)
            }
        }
        for url,image in records
    ]
    bot=get_bot()
    await bot.call_api("send_group_forward_msg",group_id=cmd.group_id,messages=msgs)

testrelease=on_command("/gtnhrelease",rule=plugin_enabled)
@testrelease.handle()
async def handle(event:MessageEvent,cmd:command.Release=Depends(command.Release.get)):
    tag=cmd.tag
    release=await gtnhpr_service.find_release(tag)
    if not release:
        await testrelease.finish("找不到对应的Release")

    print(f"正在分析Release：{release['tag_name']}")
    analysis=await gtnhpr_service.analyze_release(release)
    image=await gtnhpr_release_render.render_release_card(release,**analysis)

    await testrelease.finish(MessageSegment.image(image))

MAX_PR=20
PRGROUPS=[834865834]
@scheduler.scheduled_job("interval",minutes=120,max_instances=1,id="gtnhpr")#自动推送
async def check_pr():
    prs=await gtnhpr_service.get_merged_prs()
    prs=[pr for pr in prs if not gtnhpr_service.has_sent_pr(pr["id"])]
    print(f"GitHub 查询到 {len(prs)} 条 PR")
    prs.sort(key=lambda pr:pr["closed_at"] or "")
    print(f"其中 {len(prs)} 条尚未推送")

    bot=get_bot()
    msgs=[]
    prid=[]
    for pr in prs[:MAX_PR]:
        if gtnhpr_service.has_sent_pr(pr["id"]):
            continue
        analysis=await gtnhpr_service.analyze_pr(pr)
        image=await gtnhpr_render.render_pr_card(pr,analysis)
        msgs.append({
                    "type": "node",
                    "data": {
                        "name": f"PR #{pr['number']}",
                        "uin": str(bot.self_id),
                        "content": MessageSegment.image(image)
                    }
                })
        # for g in PRGROUPS:
        #     await bot.send_group_msg(group_id=g,message=MessageSegment.image(image))
        prid.append(pr["id"])
    if msgs:
        for g in PRGROUPS:
            await bot.call_api("send_group_forward_msg",group_id=g,messages=msgs)
        for pr in prid:
            gtnhpr_service.save_sent_pr(pr,image)
    

RELEASEGROUP=[834865834,558248216]
@scheduler.scheduled_job("interval",minutes=10,id="gtnh_release_push",max_instances=1,coalesce=True)
async def push_gtnh_release():
    bot=get_bot()
    release=await gtnhpr_service.get_new_release()
    if not release:
        return
    analysis=await gtnhpr_service.analyze_release(release)
    image=await gtnhpr_release_render.render_release_card(release,**analysis)
    for group_id in RELEASEGROUP:
        await bot.send_group_msg(group_id=group_id,message=MessageSegment.image(image))
    gtnhpr_service.record_sent(release["id"])

#灰机条款禁止自动爬取，不做了
# gtnhwiki=on_command("/gtnhwiki",rule=plugin_enabled)
# @gtnhwiki.handle()
# async def handle(cmd:command.Wiki=Depends(command.Wiki.get)):
#     query=cmd.query
#     image=await wiki_render.screenshot_page(query)
#     await gtnhwiki.finish(MessageSegment.image(image))