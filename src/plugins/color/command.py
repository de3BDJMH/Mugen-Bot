from nonebot.adapters.onebot.v11 import Message,MessageEvent
from ...command.base import Command,CommandParseError

class Color(Command):
    """颜色参数，保留原有解析规则"""
    key="color.color"
    rgbs:list[int]|None

    @classmethod
    def parse(cls,event:MessageEvent,arg:Message):
        cmd=cls(event,arg)
        arg=arg.extract_plain_text().lower().split(" ")
        rgbs=[0,0,0]
        if arg and arg[0]:
            if len(arg)==1:
                if len(arg[0])!=6 and (arg[0][0]=="#" and len(arg[0])!=7):
                    raise CommandParseError("这不是一个有效的颜色代码")
                for n in range(6):
                    c=arg[0][n-6]
                    if not ("0"<=c<="9" or "a"<=c<="f"):
                        raise CommandParseError("这不是一个有效的颜色代码")
                    else:
                        rgbs[n//2]=rgbs[n//2]*16+int(c,16)
            elif len(arg)==3:
                p=0
                for v in arg:
                    if type(v)!=int:
                        raise CommandParseError("请提供[0,255]内的数")
                    else:
                        v=int(v)
                        if v<0 or v>255:
                            raise CommandParseError("请提供[0,255]内的数")
                        else:
                            rgbs[p]=v
                    p+=1
            else:
                raise CommandParseError("这不是一个有效的颜色代码")
        else:
            rgbs=None
        cmd.rgbs=rgbs
        return cmd
