import json
import pathlib
import random
import portalocker

from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import MessageSegment

ROOT_PATH=pathlib.Path(__file__).resolve().parent.parent.parent

def getGroupID(event) -> str:
    """生成合适的ID
    格式：
    群组：group1234
    私聊：private1234"""
    if "message.group" in event.get_event_name():
        gid="group"+str(event.group_id)
    elif "message.private" in event.get_event_name():
        gid="private"+str(event.user_id)
    return gid

def isGroup(event) -> bool:
    """
    判断该event是否为群聊事件
    """
    if "message.group" in event.get_event_name():
        return True
    return False

def jsonLoad(path):
    with open(path,encoding="utf-8") as f:
        #portalocker.lock(f, portalocker.LOCK_SH)  # 共享锁
        data=json.load(f)
        #portalocker.unlock(f)
    return data
    
def jsonDump(path,item):
    with open(path,"w",encoding="utf-8") as f:
        #portalocker.lock(f, portalocker.LOCK_EX)  # 排他锁
        json.dump(item,f,ensure_ascii=False,indent=2)
        #portalocker.unlock(f)

def rangeRandom(a,b):
    return random.random()*abs(a-b)+min(a,b)

class MGPlugin:
    def __init__(self,tag):
        self.tag:str=tag                            #插件标签
        self.data_path=ROOT_PATH/"data"/tag     #插件data路径
        self.src_path=ROOT_PATH/"src"/"plugins"/tag     #插件源码路径
        self.config:dict={}                          #插件配置文件，为空时说明配置文件不存在
        self.filter_mode:str=""
        self.help:Message=""                            #帮助文字
        self.reloadConfig()                     #init重载

    def reloadConfig(self):
        """重载配置文件"""
        if not (self.data_path/"MG.json").exists():
            self.config={}
        else:
            self.config=jsonLoad(self.data_path/"MG.json")
            self.filter_mode=self.config["filter_mode"]
            self.help=self.config["help"]["text"]
            for img in self.config["help"]["image"]:
                self.help+=MessageSegment.image(img)
    
    def exists(self):
        """插件是否存在"""
        return self.src_path.exists()

    def getPluginState(self):
        """获取插件运行状态"""
        self.reloadConfig()#先重载
        if not self.config:#没有配置文件默认一直开启
            return True
        return self.config["state"]
    
    def getGroupPluginState(self,event):
        """
        判断该插件在该群是否可用
        直接传入event是因为需要判断是否为群聊
        """
        if isGroup(event):
            group_id=event.group_id
        else:#不是群聊不做限制
            return True
        self.reloadConfig()#先重载
        if not self.config:#没配置文件默认可用
            return True
        group_list=self.config[self.filter_mode]
        if self.filter_mode=="whitelist":
            if group_id in group_list:
                return True
            else:
                return False
        else:
            if group_id in group_list:
                return False
            else:
                return True
    
    def getFilterList(self) -> dict:
        """获取黑白名单列表"""
        self.reloadConfig()#先重载
        if not self.config:#没config返回空字典
            return {}
        return {self.filter_mode:self.config[self.filter_mode]}#类型：列表
    
    def saveConfig(self):
        """保存config至文件"""
        if not self.config:
            return
        jsonDump(self.data_path/"MG.json",self.config)
        