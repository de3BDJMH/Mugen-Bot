###
#给commands.json的注释：
#结构：
#"tag":[
#    "description":"帮助信息", //随便写写，用不到
#    "help_pic_path":"", //可选，如果提供了帮助图片就会在用户只输入根指令时发送图片
#    "commands":{
#        "command1":{
#            "description":"帮助信息", //必填
#            "alias":["alias1","alias2"], //必填，并且至少包含指令本身
#            "sub_command":["sub1","sub2"] //可选，如果有子命令需要写
#            "with_num":0 //可选，如果指令后面可以直接跟数字，且数字缺省时会采用该默认值
#        },
#    }
#]
###
import json
import pathlib

from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import MessageSegment

COMMAND_PATH=pathlib.Path(__file__).parent/"commands.json"
COMMAND_CONFIG_PATH=pathlib.Path(__file__).parent/"command_config.json"

def split(raw_msg:Message[MessageSegment],tag:str,gid:str) -> dict[bool,list[str]]:
    """
    将普通聊天消息按指定规则分割为指令
    tag为指定规则（可选列表为commands.json的key）
    gid为用户/群组id，例如private1234、group2345
    """
    #Message -> str
    msg=""
    for m in raw_msg:
        if m.type=="text":
            msg+=m.data["text"]
        elif m.type=="at":
            atid=m.data["qq"]
            if m.data["qq"]=="all":
                atid=""#这里全体不要管
            msg+=atid
    if not msg:
        return {
            "state":False,
            "arg":[],
            "msg":"",
            "pic":"",
            "need_reply":False
        }

    with open(COMMAND_PATH,encoding="utf-8") as f:
        data=json.load(f)
    commands=data[tag]
    with open(COMMAND_CONFIG_PATH,encoding="utf-8") as f:
        config=json.load(f)
    
    #去除头部指令
    is_command=False#有指令前缀的是指令
    matched=True#是否匹配到前缀，简化指令一定要记得在后面改回true
    if msg[0] in config["COMMAND_START"]:
        msg=msg[1:]
        is_command=True
    for a in sorted(config["COMMAND_ALIAS"][tag],key=len,reverse=True):#从长到短排序，优先匹配长指令
        if msg[:len(a)]==a:
            msg=msg[len(a):]
            break
    else:
        matched=False
    msg=msg.strip()

    #开字母等指令简化处理
    need_reply=True#指令是否需要回复，默认是需要的
    if tag=="mai":
        GUESS_STATE_PATH=pathlib.Path(__file__).parent.parent.parent/"data"/"mai"/"guess"/"state.json"
        with open(GUESS_STATE_PATH,encoding="utf-8") as f:
            state=json.load(f)
        if gid in state and state[gid]["start"]:
            matched=True
            if msg[0]=="开" and len(msg)==2:
                msg="guess 开 "+msg[1]
            else:
                msg="guess 答 "+msg
                need_reply=False
        else:
            for a in ["霸者进度","舞极进度","舞将进度","舞神进度","舞舞舞进度","舞系列进度","DX霸者进度","DX舞极进度","DX舞将进度","DX舞神进度","DX舞舞舞进度","DX舞系列进度"]:
                if msg[:len(a)].lower()==a.lower():
                    matched=True
                    break
    
    #该走的走完了，没match到的就return了
    if not matched:
        return {
            "state":False,
            "arg":[],
            "msg":"",
            "pic":"",
            "need_reply":False
        }

    #默认处理，不管哪个规则都要走
    available=True
    arg=[]
    for c in sorted(commands["commands"],key=len,reverse=True):#从长到短排序，优先匹配长指令，例如b和bind会在没排序的情况下产生冲突
        for a in commands["commands"][c]["alias"]:#c是指令实际名字，a是用户输入的指令别名
            a=a.lower()
            if a==msg[:len(a)].lower():#找出根指令
                arg.append(c)
                if "with_num" in commands["commands"][c]:#对于那种指令后可以加数字的
                    temp=""
                    tempa=a#不是数字时候返回这个值
                    for ch in msg[len(a):]:
                        if ch==" " and not temp:
                            a+=" "
                            continue
                        elif "0"<=ch<="9":
                            a+=ch
                            temp+=ch
                        elif ch==" ":#遇到空格就停止，有些是定数不好处理
                            break
                        else:#其他字符直接停止并且不算数字
                            a=tempa
                            temp=""
                            break
                    if temp:#有数字加上
                        arg.append(temp)
                    else:#没数字加默认的
                        arg.append(str(commands["commands"][c]["with_num"]))
                if msg.lower()!=a:
                    if msg[len(a)]==" ":#如果用户老老实实用空格分隔就直接split(" ")放列表里
                        arg+=msg[len(a)+1:].split(" ")
                    else:#针对那些不老实的用户
                        if "sub_command" in commands["commands"][c]:#如果包含子命令的
                            for sc in commands["commands"][c]["sub_command"]:
                                if not sc:
                                    continue
                                if msg[len(a):len(a)+len(sc)]==sc:
                                    arg.append(sc)#子命令放进去
                                    if not sc==msg[len(a):]:
                                        if msg[len(a)+len(sc)]==" ":#看看子命令后面有没有跟空格
                                            arg+=msg[len(a)+len(sc)+1:].split(" ")
                                        else:
                                            arg+=msg[len(a)+len(sc):].split(" ")
                                    break
                            else:#有子命令但是用户输入的子命令有误，就提供帮助
                                if not sc[0]:#子命令第一项为空字符串时表示该指令可以跟任意参数
                                    available=False
                                    return {
                                        "state":available,
                                        "arg":[],
                                        "msg":"指令格式有误，以下是该指令的帮助\n"+commands["commands"][c]["description"],
                                        "pic":"",
                                        "need_reply":need_reply
                                    }
                                else:
                                    arg.append(msg[len(a):])
                        else:#这里是没有子命令的
                            arg+=msg[len(a):].split(" ")
                break
        if arg:
            break
    else:
        available=False
        if (msg and is_command) or not msg:#如果用户输入的消息以指令起始符开头但是没有匹配到任何指令，就提示没有找到指令
            help_msg="没有查找到对应的指令，以下是所有指令的帮助\n"
            for c in commands["commands"]:
                help_msg+=f"{c}：{commands['commands'][c]['description']}\n"
            return {
                "state":available,
                "arg":[],
                "msg":help_msg,
                "pic":"",
                "need_reply":need_reply
            }
        elif not msg and "help_pic_path" in commands:#这个情况对应/phi这样的，只提供主指令并且提供了指令标识符
            return {
                "state":available,
                "arg":[],
                "msg":"",
                "pic": commands["help_pic_path"],
                "need_reply":need_reply
            }
        else:
            return {
                "state":available,
                "arg":[],
                "msg":"",
                "pic":"",
                "need_reply":need_reply
            }
    return {
        "state":available,
        "arg":arg,
        "msg":"",
        "pic":"",
        "need_reply":need_reply
    }