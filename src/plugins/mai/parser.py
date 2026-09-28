from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot import get_driver

COMMAND=["mai","maimai"]#根指令
SUB_COMMAND={#子命令
            "guess": {
                "description": "猜歌根指令",
                "alias": [
                    "guess",
                    "开字母",
                    "开",
                    "k",
                    "字母"
                ],
                "allowDirect": False#是否允许忽略根指令，True为可直接调用
            },
            "霸者进度": {
                "description": "查询霸者进度",
                "alias": [
                    "霸者进度"
                ],
                "allowDirect": True
            },
            "舞极进度": {
                "description": "查询舞极进度",
                "alias": [
                    "舞极进度"
                ],
                "allowDirect": True
            },
            "舞将进度": {
                "description": "查询舞将进度",
                "alias": [
                    "舞将进度"
                ],
                "allowDirect": True
            },
            "舞神进度": {
                "description": "查询舞神进度",
                "alias": [
                    "舞神进度"
                ],
                "allowDirect": True
            },
            "舞舞舞进度": {
                "description": "查询舞舞舞进度",
                "alias": [
                    "舞舞舞进度"
                ],
                "allowDirect": True
            },
            "舞系列进度": {
                "description": "查询舞系列进度",
                "alias": [
                    "舞系列进度"
                ],
                "allowDirect": True
            },
            "DX霸者进度": {
                "description": "查询DX霸者进度",
                "alias": [
                    "DX霸者进度",
                    "dx霸者进度"
                ],
                "allowDirect": True
            },
            "DX舞极进度": {
                "description": "查询DX舞极进度",
                "alias": [
                    "DX舞极进度",
                    "dx舞极进度"
                ],
                "allowDirect": True
            },
            "DX舞将进度": {
                "description": "查询DX舞将进度",
                "alias": [
                    "DX舞将进度",
                    "dx舞将进度"
                ],
                "allowDirect": True
            },
            "DX舞神进度": {
                "description": "查询DX舞神进度",
                "alias": [
                    "DX舞神进度",
                    "dx舞神进度"
                ],
                "allowDirect": True
            },
            "DX舞舞舞进度": {
                "description": "查询DX舞舞舞进度",
                "alias": [
                    "DX舞舞舞进度",
                    "dx舞舞舞进度"
                ],
                "allowDirect": True
            },
            "DX舞系列进度": {
                "description": "查询DX舞系列进度",
                "alias": [
                    "DX舞系列进度",
                    "dx舞系列进度"
                ],
                "allowDirect": True
            }
        }

GLOBAL_CONFIG=get_driver().config#.env的配置

def match_sub_command(message:str,direct_only:bool=False)->list[str]|None:
    #判断是否为允许缩写的指令
    for sc in SUB_COMMAND:
        if direct_only and not SUB_COMMAND[sc]["allowDirect"]:
            continue
        for sc_alias in sorted(SUB_COMMAND[sc]["alias"],key=len,reverse=True):
            if message.startswith(sc_alias):#子命令不切除
                return [sc]+message.removeprefix(sc_alias).strip().split()
    return None

def parse(event:MessageEvent)->list[str]|None:
    """
    用于判断是否为COMMAND开头的指令 或 为可直接调用的子命令
    不是指令时返回None
    是指令但是空参数是[]，注意区分
    """
    message=event.message.extract_plain_text().strip()
    command_starts=GLOBAL_CONFIG.command_start
    #去指令头
    for command_start in command_starts:#匹配指令前缀
        if command_start and message.startswith(command_start):#确保前缀不是""
            message=message.removeprefix(command_start)
            break
    #判断是否为正常指令
    for c in sorted(COMMAND,key=len,reverse=True):#匹配根指令，优先匹配长的
        if message.startswith(c):
            message=message.removeprefix(c).strip()
            if not message:
                return []
            result=match_sub_command(message)#统一别名用的
            return result if result is not None else message.split()#后面全当参数
    #没有匹配到正常指令进入下一流程
    return match_sub_command(message,True)
