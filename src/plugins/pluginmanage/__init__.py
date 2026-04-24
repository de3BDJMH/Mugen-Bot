from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata
from nonebot.plugin import on_command
from nonebot.adapters import Message
from nonebot.params import CommandArg,Arg,EventMessage
from nonebot.matcher import Matcher
from nonebot.adapters.onebot.v11 import Bot,MessageSegment,Event,GroupMessageEvent,PrivateMessageEvent
from nonebot import get_bot
from nonebot.typing import T_State


import pathlib
import json

from ...libraries.tools import *
from ...libraries.pluginmanage.tools import *

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="PluginManage",
    description="所有自定义功能的管理插件，控制开关用",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

###
#用法/统一规则：
#每个插件下都需要添加一个控制开关的文件，命名为MG.json吧，放/data下
#每个文件内容都参考以下内容：
#{
#    "display_name": "输出展示时的名字，留空默认插件名字",
#    "help": {
#        "text": "",//帮助文字
#        "image": [] //帮助图片            
#    },
#    "state":true, //true为开启,false为关闭
#    "filter_mode": "whitelist"/"blacklist", //选择使用白名单还是黑名单
#    "whitelist": [群组id], //这两个配置项选择哪个由filter_mode控制
#    "blacklist": [群组id]
#}
#最后，一定记得去plugin_alias.json添加插件别名，不然管理很麻烦
#请为每个插件的.handle()函数最前面添加以下代码以适配该插件：
"""
    plugin=MGPlugin(TAG)
    if not plugin.getPluginState():
        return
    if not plugin.getGroupPluginState(event):
        return
"""
#或（在最前面TAG下加上 MGPLUGIN=MGPlugin(TAG) ）
"""
    if not MGPLUGIN.getPluginState():
        return
    if not MGPLUGIN.getGroupPluginState(event):
        return
"""
###

TAG="pluginmanage"
MGPLUGIN=MGPlugin(TAG)

#路径设置
ROOT_PATH=pathlib.Path(__file__).resolve().parent.parent.parent.parent #/server
DATA_PATH=ROOT_PATH/"data"/"pluginmanage"

PLUGIN_ALIAS_PATH=DATA_PATH/"plugin_alias.json"
CONFIG_PATH=DATA_PATH/"config.json"

showstate=on_command("MG插件状态",aliases={"MGstate"})
@showstate.handle()
async def show(matcher:Matcher,bot:Bot,event:GroupMessageEvent,args: Message = CommandArg()):
    arg=args.extract_plain_text()
    if not arg:#空参数，返回所有插件状态
        unknown=[]
        msg="所有插件状态：\n"
        for plugin in [f for f in (ROOT_PATH/"data").iterdir() if not f.is_file()]:#路径下全部文件夹
            configfile=plugin/"MG.json"
            if configfile.exists():
                tmp="  - "
                with open(configfile,encoding="utf-8") as f:
                    pluginconfig=json.load(f)
                if pluginconfig["display_name"]:
                    tmp+=f"{pluginconfig["display_name"]}: "
                else:
                    tmp+=f"{plugin.name}: "
                tmp+=f"{"ON" if pluginconfig["state"] else "OFF"}"
                msg+=tmp+"\n"
            else:
                unknown.append(plugin.name)
        if unknown:
            msg+="未知状态插件：\n"
            for p in unknown:
                msg+=f"  - {p}\n"
        await showstate.finish(msg[:-1])
    else:
        with open(PLUGIN_ALIAS_PATH,encoding="utf-8") as f:
            plugin_alias=json.load(f)
        fit=""
        for pa in plugin_alias:
            if arg in plugin_alias[pa]:
                fit=pa
                break
        if fit:
            plugin_path=ROOT_PATH/"data"/pa
            if (plugin_path/"MG.json").exists():
                msg=""
                pluginconfig=jsonLoad(plugin_path/"MG.json")
                msg=f"{getPluginDisplayName(pa)} 状态: \n"
                msg+=f"  - 是否启用：{"是" if pluginconfig["state"] else "否"}\n"
                msg+=f"  - 黑白名单状态：{"白名单" if pluginconfig["filter_mode"]=="whitelist" else "黑名单"}\n"
                for g in pluginconfig[pluginconfig["filter_mode"]]:
                    msg+=f"        {g}\n"
                await showstate.finish(msg[:-1])
            else:
                await showstate.finish("该插件不存在配置文件，状态未知")
        else:
            await showstate.finish("不存在该插件")
                
togglestate=on_command("MG开关",aliases={"MGtoggle"})
@togglestate.handle()
async def toggle(matcher:Matcher,bot:Bot,event:GroupMessageEvent,args: Message = CommandArg()):
    mgconfig=jsonLoad(CONFIG_PATH)
    if not event.user_id in mgconfig["op"]:
        await togglestate.finish("权限不足")
    arg=args.extract_plain_text().split(" ")
    if not arg[0]:#只有指令头这边arg是[""]
        await togglestate.finish("请提供插件名")
    elif len(arg)>=1:
        plugin_name=getPluginName(arg[0])
        if not plugin_name:
            await showstate.finish("不存在该插件")
        if not (ROOT_PATH/"data"/plugin_name/"MG.json").exists():
            await showstate.finish("该插件不存在配置文件，无法调整状态")
        pluginconfig=jsonLoad(ROOT_PATH/"data"/plugin_name/"MG.json")
        if len(arg)==1:
            pluginconfig["state"]=not pluginconfig["state"]
            jsonDump(ROOT_PATH/"data"/plugin_name/"MG.json",pluginconfig)
            await togglestate.finish(f"已将 {getPluginDisplayName(plugin_name)} 的状态修改为：{"ON" if pluginconfig["state"] else "OFF"}")
        else:
            if not arg[1].lower() in mgconfig["toggle_on_command"]+mgconfig["toggle_off_command"]:
                await togglestate.finish(f"请提供正确的状态，当前可用：\n  开启：{mgconfig["toggle_on_command"]}\n  关闭：{mgconfig["toggle_off_command"]}")
            if arg[1].lower() in mgconfig["toggle_on_command"]:
                if pluginconfig["state"]:
                    await togglestate.finish(f"{getPluginDisplayName(plugin_name)} 已经开启了哦~")
                else:
                    pluginconfig["state"]=True
                    jsonDump(ROOT_PATH/"data"/plugin_name/"MG.json",pluginconfig)
                    await togglestate.finish(f"成功开启 {getPluginDisplayName(plugin_name)}")
            else:
                if not pluginconfig["state"]:
                    await togglestate.finish(f"{getPluginDisplayName(plugin_name)} 已经关闭了哦~")
                else:
                    pluginconfig["state"]=False
                    jsonDump(ROOT_PATH/"data"/plugin_name/"MG.json",pluginconfig)
                    await togglestate.finish(f"成功关闭 {getPluginDisplayName(plugin_name)}")

listadd=on_command("MGlistadd",aliases={"MGwhitelistadd","MGblacklistadd","MG添加白名单","MG添加黑名单"})
@listadd.handle()
async def ladd(matcher:Matcher,bot:Bot,event:GroupMessageEvent,args: Message = CommandArg(),message: Message = EventMessage()):
    msg=str(message)
    msg=msg[msg.find("MG"):]
    add_type=""
    if msg.startswith(("MGwhitelistadd","MG添加白名单")):
        add_type="whitelist"
    elif msg.startswith(("MGblacklistadd","MG添加黑名单")):
        add_type="blacklist"
    else:
        await listadd.finish("请指定黑白名单（MGwhite/blacklistadd、MG添加白/黑名单）")
    arg=args.extract_plain_text().split(" ")
    if len(arg)<2:
        await listadd.finish("请提供插件名和群号")
    else:
        plugin_name=getPluginName(arg[0])
        if not plugin_name:
            await listadd.finish("不存在该插件")
        plugin=MGPlugin(plugin_name)
        if not plugin.config:
            await listadd.finish("该插件没有配置文件，无法修改")
        if plugin.filter_mode!=add_type:
            await listadd.send(f"提醒：该插件匹配模式为 {"白名单" if plugin.config=="whitelist" else "黑名单"} ，但仍添加至指定名单中")
        for gid in arg[1:]:
            plugin.config[plugin.filter_mode].append(int(gid))
        plugin.saveConfig()
        await listadd.finish("添加成功！")
    
listdel=on_command("MGlistdel",aliases={"MGwhitelistdel","MGblacklistdel","MG删除白名单","MG删除黑名单"})
@listdel.handle()
async def ldel(matcher:Matcher,bot:Bot,event:GroupMessageEvent,args: Message = CommandArg(),message: Message = EventMessage()):
    msg=str(message)
    msg=msg[msg.find("MG"):]
    del_type=""
    if msg.startswith(("MGwhitelistdel","MG删除白名单")):
        del_type="whitelist"
    elif msg.startswith(("MGblacklistdel","MG删除黑名单")):
        del_type="blacklist"
    else:
        await listdel.finish("请指定黑白名单（MGwhite/blacklistdel、MG删除白/黑名单）")
    arg=args.extract_plain_text().split(" ")
    if len(arg)<2:
        await listdel.finish("请提供插件名和群号")
    else:
        plugin_name=getPluginName(arg[0])
        if not plugin_name:
            await listdel.finish("不存在该插件")
        plugin=MGPlugin(plugin_name)
        if not plugin.config:
            await listdel.finish("该插件没有配置文件，无法修改")
        if plugin.filter_mode!=del_type:
            await listdel.send(f"提醒：该插件匹配模式为 {"白名单" if plugin.config=="whitelist" else "黑名单"} ，但仍在指定名单中删除")
        for gid in arg[1:]:
            fail=[]
            try:
                plugin.config[plugin.filter_mode].remove(int(gid))
            except:
                fail.append(gid)
        plugin.saveConfig()
        msg="删除成功！"
        if fail:
            msg=f"删除完成\n失败项：{"、".join(fail)}"
        await listdel.finish(msg)
