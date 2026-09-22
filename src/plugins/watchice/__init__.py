from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata
from nonebot.plugin import on_command
from nonebot.adapters import Message
from nonebot.params import Depends,Arg
from nonebot.matcher import Matcher
from nonebot.adapters.onebot.v11 import Bot,MessageSegment,Event,GroupMessageEvent,PrivateMessageEvent,MessageEvent
from nonebot import get_bot
from nonebot.typing import T_State


import os
import random
import shutil
import json
import datetime
import pathlib

from ...libraries.tools import *
from ...libraries.watchice.paint import distibution as paintdis
from ...services import watchice as services

from .config import Config
from . import command

__plugin_meta__ = PluginMetadata(
    name="watchice",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

TAG="watchice"
MGPLUGIN=MGPlugin(TAG)
def plugin_enabled(event:MessageEvent)->bool:
    if not MGPLUGIN.getPluginState():
        return False
    return MGPLUGIN.getGroupPluginState(event)

watch=on_command("看",block=True,rule=plugin_enabled)
upload=on_command("上传",block=True,rule=plugin_enabled)
addalias=on_command("添加群友别名",block=True,rule=plugin_enabled)
delalias=on_command("删除群友别名",block=True,rule=plugin_enabled)
checkalias=on_command("查看群友别名",block=True,rule=plugin_enabled)
addmember=on_command("添加群友",block=True,rule=plugin_enabled)
delmember=on_command("删除群友",block=True,rule=plugin_enabled)
delimg=on_command("删除",block=True,rule=plugin_enabled)
watchhelp=on_command("看群友帮助",block=True,rule=plugin_enabled)
memberlist=on_command("群友列表",block=True,rule=plugin_enabled)

updatealias=on_command("更新群友别名",block=True,rule=plugin_enabled)
checkque=on_command("查看队列",block=True,rule=plugin_enabled)

checkdistribution=on_command("群友图片分布",block=True,rule=plugin_enabled)

#路径设置
ROOT_PATH=pathlib.Path(__file__).resolve().parent.parent.parent.parent #/server
DATA_PATH=ROOT_PATH/"data"/"watchice"

MEMBER_ALIAS_PATH=DATA_PATH/"member_alias.json"

MEMBER_ALIAS={}
IMG_PATH={}

IMG_ID=DATA_PATH/"img"/"id.json"

def get_member(name):
    for m in MEMBER_ALIAS:
        for a in MEMBER_ALIAS[m]:
            if a.lower()==name.lower():
                return m
    else:
        return ""

def reload_alias():
    global MEMBER_ALIAS
    global IMG_PATH
    with open(MEMBER_ALIAS_PATH,encoding="utf-8") as f:
        MEMBER_ALIAS=json.load(f)

    IMG_PATH={}
    _ORIGIN_PATH=DATA_PATH/"img"
    for m in MEMBER_ALIAS:
        IMG_PATH[m]=_ORIGIN_PATH/m
        try:
            os.mkdir(IMG_PATH[m])
        except:
            continue
reload_alias()

WHITELIST=[558248216,727967933,837222085,791163286,1033530604,640447991,640447991,1021122156]
OPS=[2404164262,2421372100]


@watch.handle()
async def handle_function(matcher:Matcher,bot:Bot,event:GroupMessageEvent,cmd:command.Watch=Depends(command.Watch.get)):
    user_id=event.user_id
    img_id=cmd.image_id
    target=services.get_member_by_alias(cmd.alias)
    #哪个傻逼这么写的，卡死了
    ## 哪个傻逼注释掉的，跑都跑不起来了
    # if target:
    #     image_ids=services.get_all_images(target,user_id)#旧id到新id的映射表
    # else:
    #     return
    # imgs=[services.get_image_content(image_ids[legacy_id],user_id) for legacy_id in image_ids]
    if not target:
        return
    if img_id<=0:#随机
        result=services.get_random_images(user_id,target,count=1)
        if result["count"]==0:
            await watch.finish("Ta还没有图片哦，试试上传一张吧~")
        img=services.get_image_content(result["images"][0]["image_id"],user_id)
        img_path=img["path"]
        upload_time=datetime.datetime.fromisoformat(img["image"]["uploaded_at"]).strftime("%Y.%m.%d %H:%M:%S")
        uploader=img["image"]["uploader_qq"]
        uploader="Unknown" if uploader is None else uploader
        await watch.finish(MessageSegment.image(img_path)+f"\n图片ID: {img["image"]["legacy_id"]}#{img["image"]["image_id"]}\n上传时间: {upload_time}\n    ——by {uploader}")
    else:#指定id
        image_ids=services.get_all_images(target,user_id)
        if not image_ids:
            await watch.finish("Ta还没有图片哦，试试上传一张吧~")
        if max(image_ids.keys())<img_id:
            await watch.finish("还没有这么多图片哦")
        elif not img_id in image_ids:
            await watch.finish("该编号的图片已被删除或不可查看")
        img_id=image_ids[img_id]#转为全局id
        img=services.get_image_content(img_id,user_id)
        img_path=img["path"]
        upload_time=datetime.datetime.fromisoformat(img["image"]["uploaded_at"]).strftime("%Y.%m.%d %H:%M:%S")
        uploader=img["image"]["uploader_qq"]
        uploader="Unknown" if uploader is None else uploader
        await watch.finish(MessageSegment.image(img_path)+f"\n图片ID: {img["image"]["legacy_id"]}#{img["image"]["image_id"]}\n上传时间: {upload_time}\n    ——by {uploader}")

@upload.handle()
async def handle_function(event:GroupMessageEvent,cmd:command.Upload=Depends(command.Upload.get),state:T_State=None):

    arg=cmd.alias
    target=services.get_member_by_alias(arg)
    if not target:
        await upload.finish("还没有这个群友哦")

    state["target"]=target

@upload.got("img",prompt="请发送图片")
async def get_img(event:GroupMessageEvent,img:Message=Arg(),state:T_State=None):

    new=img.get("image")
    if not new:
        await upload.finish("目前只支持上传图片哦")

    bot=get_bot()
    target=state["target"]
    imgfile=new[0].data["file"]
    imgdld=await bot.call_api("get_image",file=imgfile)
    imgdld=pathlib.Path(imgdld["file"])
    image=services.upload_image(target,imgdld,event.user_id)
    await upload.finish(
        f"({target}:{image['legacy_id']}#{image['image_id']})上传成功~"
    )

@addalias.handle()
async def handle_function(matcher:Matcher,bot:Bot,event:GroupMessageEvent,cmd:command.AddAlias=Depends(command.AddAlias.get)):
    arg=cmd.aliases
    target=services.get_member_by_alias(arg[0])
    new_aliases=arg[1:]
    if target:
        alias_set=services.get_alias_set()
        for new_alias in new_aliases:
            for m,ma in alias_set.items():
                if new_alias in ma:
                    await addalias.finish(f"新别名 {new_alias} 已被 {m} 占用了哦，请换一个")
        aliases=services.get_member_aliases(target)
        aliases+=new_aliases
        aliases=list(set(aliases))
        services.set_member_aliases(target,aliases)
        await addalias.finish("添加成功")
    else:
        await addalias.finish("这个别名不存在")

@delalias.handle()
async def handle_function(matcher:Matcher,bot:Bot,event:GroupMessageEvent,cmd:command.DeleteAlias=Depends(command.DeleteAlias.get)):
    arg=cmd.aliases
    target=services.get_member_by_alias(arg[0])
    if target:
        aliases=services.get_member_aliases(target)
        for new_alias in arg[1:]:
            new_alias=new_alias.strip()
            if not new_alias in aliases:
                await delalias.finish(f"需要删除的别名 {new_alias} 不存在")
        for a in aliases.copy():
            if a in arg[1:]:
                aliases.remove(a)
        services.set_member_aliases(target,aliases)
        await delalias.finish("删除成功")
    else:
        await delalias.finish("不存在这个群友")

@checkalias.handle()
async def handle_function(matcher:Matcher,bot:Bot,event:GroupMessageEvent,cmd:command.CheckAlias=Depends(command.CheckAlias.get)):

    arg=cmd.plain_text
    target=services.get_member_by_alias(arg)
    if target:
        await checkalias.finish("，".join(services.get_member_aliases(target)))
    else:
        await checkalias.finish("还没有这个群友哦")

@addmember.handle()
async def handle_function(matcher:Matcher,bot:Bot,event:GroupMessageEvent,cmd:command.AddMember=Depends(command.AddMember.get)):
    arg=cmd.aliases
    target=arg[0]
    aliases=list(dict.fromkeys(arg))
    alias_set=services.get_alias_set()
    for alias in aliases:
        for m,ma in alias_set.items():
            if alias in ma:
                await addmember.finish(f"别名 {alias} 已被 {m} 占用了哦，请换一个")
    services.create_member(target,aliases)
    await addmember.finish("旅行伙伴加入~")

@delmember.handle()
async def handle_function(matcher:Matcher,bot:Bot,event:GroupMessageEvent,cmd:command.DeleteMember=Depends(command.DeleteMember.get)):
    # if not int(event.get_user_id()) in OPS:
    #     await delmember.finish("无权限")    
    #现在权限由services处理
    target=services.get_member_by_alias(cmd.alias)
    if target:
        target_state=services.get_member_state(target)
        if target_state is None or not target_state["enabled"]:
            await delmember.finish("该群友不存在或已被删除")
        result=services.set_member_enabled(event.user_id,target,False)
        if not result:
            await delmember.finish("无权限")
        await delmember.finish("删除成功")
    else:
        await delmember.finish("不存在这个群友")

@delimg.handle()
async def handle_function(matcher:Matcher,bot:Bot,event:GroupMessageEvent,cmd:command.DeleteImage=Depends(command.DeleteImage.get)):
    target=services.get_member_by_alias(cmd.alias)
    id_type=cmd.id_type
    img_id=cmd.image_id
    if target:
        img_ids=services.get_all_images(target,event.user_id)
        if id_type=="single":#局部id转为全局id
            if not img_id in img_ids:
                await delimg.finish("该编号图片不存在或已被删除")
            img_id=img_ids[img_id]
        if not img_id in img_ids.values():
            await delimg.finish("该编号图片不存在或已被删除")
        try:
            result=services.delete_image(event.user_id,img_id)
        except PermissionError:
            await delimg.finish("你只能删除自己上传的图片")
        if not result:
            await delimg.finish("该编号图片不存在或已被删除")
        await delimg.finish("删除成功")
    else:
        await delimg.finish("需要提供别名和图片id，你可以在id前添加#表示使用全局id")

@watchhelp.handle()
async def handle_function(matcher:Matcher,bot:Bot,event:GroupMessageEvent,cmd:command.Help=Depends(command.Help.get)):

    if not event.group_id in WHITELIST:
        return
    await addalias.finish("所有人可用：\n"
                          +"    看图片      “看<群友别名> [id]”\n"
                          +"    添加群友      “添加群友 <群友ID> [别名1] [别名2]...”\n"
                          +"    添加别名      “添加群友别名 <已有别名> <新别名1> [新别名2]...”\n"
                          +"    删除别名      “删除群友别名 <已有别名> <需要删除的别名1> [需要删除的别名2]...”\n"
                          +"    查看别名      “查看群友别名 <已有别名>”\n"
                          +"    上传图片      “上传<群友别名>”\n"
                          +"    删除图片      “删除<群友别名> <图片ID>”\n"
                          +"    群友图片分布      “群友图片分布”\n"
                          +"管理可用：\n"
                          +"    删除图片      “删除<群友别名> <图片ID>”\n"
                          +"    删除群友      “删除群友 <群友别名>”\n"
                          +"\n"
                          +"注：\n"
                          +"    非管理只能删除自己上传上传的图片\n"
                          +"    上传时请注意隐私，所有人可见")

@memberlist.handle()
async def handle_function(matcher:Matcher,bot:Bot,event:GroupMessageEvent,cmd:command.MemberList=Depends(command.MemberList.get)):

    plugin=MGPlugin(TAG)
    if not plugin.getPluginState():
        return
    if not plugin.getGroupPluginState(event):
        return

    members=services.get_members(event.user_id)#
    if not members:
        await checkdistribution.finish("当前没有可查看的群友")
    msgs=[]
    for m in members:
        msgs.append({
                        "type": "node",
                        "data": {
                            "name": "プラナ",
                            "uin": str(event.self_id),
                            "content": f"ID: {m["slug"]}\n别名: {"，".join(m["aliases"])}\n当前图片数量: {m["image_count"]}"
                        }
                    }
                )
    await bot.call_api("send_group_forward_msg",group_id=event.group_id,messages=msgs)

@checkdistribution.handle()
async def handle_function(matcher:Matcher,bot:Bot,event:GroupMessageEvent,cmd:command.Distribution=Depends(command.Distribution.get)):

    members=services.get_members(event.user_id)
    dc={}
    for m in members:
        dc[m["slug"]]=m["image_count"]
    path=DATA_PATH/"out"/"out.png"
    paintdis(dc,services.get_alias_set(),path)
    await checkdistribution.finish(MessageSegment.image(path))
    
