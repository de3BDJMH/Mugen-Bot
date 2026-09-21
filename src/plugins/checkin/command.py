from nonebot.adapters.onebot.v11 import Message,MessageEvent
from nonebot.params import CommandArg

import math

from ...command.base import Command,CommandParseError
from ...libraries.checkin.data import Data,DATA_UNIT

class Checkin(Command):
    key="checkin.checkin"

class Send(Command):#send @xxx data
    key="checkin.send"
    to_me:bool
    target_id:int
    send_data:Data

    @classmethod
    def parse(cls,event:MessageEvent,arg:Message=CommandArg()):
        cmd=cls(event)
        cmd.to_me=event.is_tome()#是否和bot有关，bot的at不会被算在at里
        at=None
        send_data=""
        for seg in arg:
            if seg.type=="at":
                at=seg
            if seg.type=="text":
                send_data+=seg.data["text"].upper()
        if at is None or send_data=="":
            raise CommandParseError()#静默
        try:#防@全体
            cmd.target_id=int(at.data["qq"])
        except:
            raise CommandParseError()
        send_data_unit=20#默认MB
        for u in list(DATA_UNIT.keys())[::-1]:#倒序，防止先匹配B
            if send_data.endswith(DATA_UNIT[u]):
                send_data_unit=u
                send_data=send_data[:-len(DATA_UNIT[u])].strip()
                break
        try:
            send_data=float(send_data)
            #if not math.isfinite(send_data):#头一次知道float("inf")和float("nan")不会报错。。。
            if math.isinf(send_data):
                raise CommandParseError("@无限！")
            if math.isnan(send_data):
                raise ValueError
            if send_data_unit==0:#B不能小数，稍微严谨一些
                send_data=int(send_data)
        except ValueError:
            raise CommandParseError("输入数据有误，需要为整数或小数+单位(B KB MB...)，无单位默认MB")
        if send_data<=0 or (send_data<1 and send_data_unit==0):
            raise CommandParseError("笨蛋！你想干什么？！")
        elif send_data>=1024:
            raise CommandParseError("太大了...不可以哦...")
        cmd.send_data=Data([send_data_unit,math.log2(send_data)],False)
        return cmd