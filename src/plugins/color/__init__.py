from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata
from nonebot.plugin import on_command
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot.matcher import Matcher
from nonebot.adapters.onebot.v11 import Bot,MessageSegment,Event,GroupMessageEvent,PrivateMessageEvent
from nonebot.adapters.onebot.v11.event import MessageEvent
from nonebot.plugin import on_message


import pathlib
import random
from PIL import Image,ImageFilter,ImageDraw,ImageFont

from ...libraries.tools import *

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="color",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

TAG="color"
MGPLUGIN=MGPlugin(TAG)

DATA_PATH=MGPLUGIN.data_path

HEXCODE={"a":10,"b":11,"c":12,"d":13,"e":14,"f":15,'0': 0, '1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9}
REHEXCODE={10: 'a', 11: 'b', 12: 'c', 13: 'd', 14: 'e', 15: 'f', 0: '0', 1: '1', 2: '2', 3: '3', 4: '4', 5: '5', 6: '6', 7: '7', 8: '8', 9: '9'}
WIDTH=256
HEIGHT=256
PATH=DATA_PATH/"out"

color = on_command("#color", block=True,aliases={"色色","涩涩"})
@color.handle()
async def colorcolor(matcher:Matcher,bot:Bot,event:Event,args: Message = CommandArg()):

    if not MGPLUGIN.getPluginState():
        return
    if not MGPLUGIN.getGroupPluginState(event):
        return
    
    arg=args.extract_plain_text().lower().split(" ")
    rgbs=[0,0,0]
    if arg and arg[0]:
        if len(arg)==1:
            if len(arg[0])!=6 and (arg[0][0]=="#" and len(arg[0])!=7):
                await color.finish("这不是一个有效的颜色代码")
            for n in range(6):
                c=arg[0][n-6]
                if not ("0"<=c<="9" or "a"<=c<="f"):
                    await color.finish("这不是一个有效的颜色代码")
                else:
                    rgbs[n//2]=rgbs[n//2]*16+HEXCODE[c]
        elif len(arg)==3:
            p=0
            for v in arg:
                if type(v)!=int:
                    await color.finish("请提供[0,255]内的数")
                else:
                    v=int(v)
                    if v<0 or v>255:
                        await color.finish("请提供[0,255]内的数")
                    else:
                        rgbs[p]=v
                p+=1
        else:
            await color.finish("这不是一个有效的颜色代码")
    else:
        rgbs=[random.randint(0,255) for _ in range(3)]
    rgbs.append(255)
    rgbs=tuple(rgbs)
    background=Image.new("RGBA",(WIDTH,HEIGHT),rgbs)
    text=ImageDraw.Draw(background,"RGBA")
    font=ImageFont.truetype(DATA_PATH/"汉仪正圆-75W.ttf",30)
    fontcolor=[255,255,255]
    if rgbs[0]+rgbs[1]+rgbs[2]<128*3:
        for i in range(3):
            fontcolor[i]=(fontcolor[i]+rgbs[i])//2
    else:
        for i in range(3):
            fontcolor[i]=rgbs[i]//2
    fontcolor.append(255)
    fontcolor=tuple(fontcolor)
    colortext=""
    for v in rgbs[:3]:
        colortext+=REHEXCODE[v//16]+REHEXCODE[v%16]
    colortext=colortext.upper()
    text.text((10,200),"#"+colortext,fontcolor,font)
    background.save(PATH/f"{" ".join([str(v) for v in rgbs])}.png")
    await color.finish(MessageSegment.image(PATH/f"{" ".join([str(v) for v in rgbs])}.png"))

