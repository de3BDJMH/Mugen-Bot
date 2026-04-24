import pathlib
import math
import time
import datetime
import random

from ..tools import *

DATA_PATH=pathlib.Path(__file__).resolve().parent.parent.parent.parent/"data"/"checkin"
CONFIG_PATH=DATA_PATH/"config.json"
USER_PATH=DATA_PATH/"data"/"user.json"
TIME_PATH=DATA_PATH/"data"/"time.json"
LOG_PATH=DATA_PATH/"data"/"logs"

DATA_UNIT={0:"B",
           10:"KB",
           20:"MB",
           30:"GB",
           40:"TB",
           50:"PB",
           60:"EB",
           70:"ZB",
           80:"YB",
           90:"BB",
           100:"NB",
           110:"DB",
           120:"CB"}

class Data:
    def __init__(self,data:list[int|float],zero:bool=False):
        """zero为true时，该data大小=0B"""
        self.base=data[0]
        self.addition=data[1]
        self.is_zero=zero
        if zero:
            self.unit="B"
            self.display="0B"
        else:
            self.unit=DATA_UNIT[self.base]
            self.display=f"{round(2**data[1],2)}{self.unit}"
    
    def getBytes(self):
        """获取字节数"""
        if self.is_zero:
            return 0
        return int((2**self.base)*(2**self.addition))

    def up(self):
        """向上走一个单位"""
        self.base+=10
        self.addition-=10
    
    def down(self):
        """向下走一个单位"""
        self.base-=10
        self.addition+=10

    def reload(self):
        """计算完成后使用该函数更新unit和display"""
        if self.is_zero:
            self.unit="B"
            self.display="0B"
        else:
            self.unit=DATA_UNIT[self.base]
            self.display=f"{round(2**self.addition,2)}{self.unit}"

def plus(a:Data,b:Data):
    """Data相加"""
    if a.is_zero:
        return b
    if b.is_zero:
        return a
    #备份
    ac=Data([a.base,a.addition],a.is_zero)
    bc=Data([b.base,b.addition],b.is_zero)
    if ac.base<bc.base:#保证数量级a>b
        ac,bc=bc,ac
    while bc.base<ac.base:
        bc.up()
    ans=Data([ac.base,ac.addition],ac.is_zero)
    ans.addition=math.log2(2**ac.addition+2**bc.addition)
    return ans

def substract(a:Data,b:Data):
    """Data相减"""
    #不交换顺序，小于0的都返回0
    if a.is_zero or b.is_zero:
        return a
    if a.base<b.base or (a.base==b.base and a.addition<=b.addition):
        return Data([0,0],True)
    ac=Data([a.base,a.addition],a.is_zero)
    bc=Data([b.base,b.addition],b.is_zero)
    while bc.base<ac.base:
        bc.up()
    ans=Data([ac.base,ac.addition],ac.is_zero)
    ans.addition=math.log2(2**ac.addition-2**bc.addition)
    return ans

def exponent(base:Data,e:float|int):
    """将data进行e次方"""
    if base.is_zero:
        return base
    datae=base.base+base.addition
    datae*=e
    return Data([datae//10*10,datae%10])

def log(id:int,operate: str,type_: str,data:Data,timestr:str):
    """记录data变化，注意time参数需要传入已经格式化好的"""
    filename=f"log_{timestr.split(" ")[0]}.json"
    log_path=LOG_PATH/filename
    if not log_path.is_file():#文件不存在
        jsonDump(log_path,[])#初始化为空列表
    data_log:list=jsonLoad(log_path)
    data_log.append({
        "id":id,
        "operate": operate,
        "type": type_,
        "data":{
            "base":data.base,
            "addition":data.addition,
            "zero": data.is_zero
        },
        "time":timestr
    })
    jsonDump(log_path,data_log)

class CheckDay:
    def __init__(self,date:datetime.datetime):
        self.date=date
        self.day=date.strftime("%Y-%m-%d")
        self.time=date.strftime("%H:%M:%S")
        self.daytime=f"{self.day} {self.time}"
        check_info=jsonLoad(TIME_PATH)
        if self.day in check_info:
            self.info=check_info[self.day]#签到排名信息
        else:
            self.info=[]
    
    def getRank(self):
        """获取排名"""
        return len(self.info)+1
    
    def firstType(self):
        """获取第一的类型：'year'/'month'/'day'/'',不是第一返回''"""
        check_info=jsonLoad(TIME_PATH)
        ftype="year"
        for day in check_info:
            if ftype=="year" and self.date.year==int(day[:4]) and self.day!=day:
                ftype="month"
            if ftype=="month" and self.date.month==int(day[5:7]) and self.day!=day:
                ftype="day"
            if ftype=="day" and self.getRank()!=1:
                ftype=''
        return ftype
    
    def log(self,id,data:Data):
        self.info.append([id,self.time])
        check_info=jsonLoad(TIME_PATH)
        check_info[self.day]=self.info
        jsonDump(TIME_PATH,check_info)
        log(id,"checkin","+",data,self.daytime)

class User:
    def __init__(self,uid:int,nickname:str=""):
        self.id=uid
        self.nickname=nickname
        self.last_check=""
        self.total_check=0
        self.consecutive_check=0
        self.max_consecutive_check=0
        self.data=Data([0,0],True)
        self.info={
            "id": self.id,
            "nickname": self.nickname,
            "last": self.last_check,
            "total": self.total_check,
            "consecutive": self.consecutive_check,
            "max_consecutive": self.max_consecutive_check,
            "data": {
                "base": self.data.base,
                "addition": self.data.addition,
                "zero": True
            }
        }#info仅供举例用，不要使用它进行任何操作，有用的数据均被导出
        self.reloadUserInfo()
    
    def reloadUserInfo(self):
        """重载用户信息"""
        info=jsonLoad(USER_PATH)
        if str(self.id) in info:#新用户默认self.info就足够了
            self.info=info[str(self.id)]
            self.id=self.info["id"]
            self.nickname=self.info["nickname"]
            self.last_check=self.info["last"]
            self.total_check=self.info["total"]
            self.consecutive_check=self.info["consecutive"]
            self.max_consecutive_check=self.info["max_consecutive"]
            self.data=Data([self.info["data"]["base"],self.info["data"]["addition"]],self.info["data"]["zero"])
        else:
            self.info={
                "id": self.id,
                "nickname": self.nickname,
                "last": "",
                "total": 0,
                "consecutive": 0,
                "max_consecutive": 0,
                "data": {"base": 0, "addition": 0.0, "zero": True}
            }
            info[str(self.id)]=self.info
            jsonDump(USER_PATH,info)
        return self.info
    
    def updateUserInfo(self):
        """更新用户信息"""
        info=jsonLoad(USER_PATH)
        info[str(self.id)]=self.info
        jsonDump(USER_PATH,info)
    
    def addData(self,data:Data):
        """增加用户data"""
        self.data=plus(self.data,data)
        self.info["data"]={"base":self.data.base,"addition":self.data.addition,"zero":self.data.is_zero}

    def delData(self,data:Data):
        """扣除用户data"""
        self.data=substract(self.data,data)
        self.info["data"]={"base":self.data.base,"addition":self.data.addition,"zero":self.data.is_zero}
    
    def check(self) -> dict:
        """签到并更新数据，返回数据量和增益状态"""
        now=datetime.datetime.now()
        today=CheckDay(now)
        rank=today.getRank()
        check_config=jsonLoad(CONFIG_PATH)
        #获取data量
        data=Data([0,0],zero=True)
        result={"data":data,"thursday":False,"super":None,"rank":rank,"rankbonus":1,"basedata":data,"first":today.firstType()}
        if now.weekday()+1==4:#周四
            if random.random()<=check_config["thursday"][0]-check_config["thursday"][1]*(rank-1):
                result["thursday"]=True
                data=plus(data,Data([20,math.log2(50)]))
        if random.random()<=check_config["superBonus"]["probability"]:
            superbonus=rangeRandom(*check_config["superBonus"]["range"])
            superbonus=Data([superbonus//10*10,superbonus%10])
            result["super"]=superbonus
            data=plus(data,superbonus)
        basedata=rangeRandom(*check_config["checkDataRange"])
        basedata=Data([basedata//10*10,basedata%10])
        result["basedata"]=basedata
        data=plus(data,basedata)
        if rank<=len(check_config["firstBonus"]):#前几
            final_data=exponent(data,check_config["firstBonus"][rank-1])
            bonus_rate=final_data.getBytes()/data.getBytes()
            result["rankbonus"]=bonus_rate
            data=final_data
        result["data"]=data
        #更新数据
        self.addData(data)
        yesterday_str=(now-datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        if self.last_check==yesterday_str:
            self.consecutive_check+=1
            self.info["consecutive"]+=1
        else:
            self.consecutive_check=1
            self.info["consecutive"]=1
        self.max_consecutive_check=max(self.consecutive_check,self.max_consecutive_check)
        self.info["max_consecutive"]=max(self.consecutive_check,self.max_consecutive_check)
        self.last_check=today.day
        self.info["last"]=today.day
        self.total_check+=1
        self.info["total"]+=1
        self.updateUserInfo()
        today.log(self.id,data)
        return result

