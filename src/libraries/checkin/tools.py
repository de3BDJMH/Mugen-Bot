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
ROB_CONFIG_PATH=DATA_PATH.parent/"rob"/"config.json"

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
    while ans.addition>=10:#统一单位
        ans.base+=10
        ans.addition-=10
    ans.reload()
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
    while ans.addition<0:
        ans.base-=10
        ans.addition+=10
    ans.reload()
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
        self.rob_info={
            "rate":0.5,
            "last_rob": "1970-01-01 00:00:00",
            "robbed": {},
            "robbed_by": []
        }
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
            },
            "rob": self.rob_info
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
            self.rob_info=self.info["rob"]
        else:
            self.info={
                "id": self.id,
                "nickname": self.nickname,
                "last": "",
                "total": 0,
                "consecutive": 0,
                "max_consecutive": 0,
                "data": {"base": 0, "addition": 0.0, "zero": True},
                "rob": {
                    "rate": 0.5,
                    "last_rob": "1970-01-01 00:00:00",
                    "robbed": {},
                    "robbed_by": []
                }
            }
            info[str(self.id)]=self.info
            jsonDump(USER_PATH,info)
        return self.info
    
    def updateUserInfo(self):
        """更新保存用户信息"""
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

    def rob(self,target:int):
        """模拟一次抢劫其他人，target为被抢人的id"""
        target_user=User(target)
        now=datetime.datetime.now()
        rob_config=jsonLoad(ROB_CONFIG_PATH)
        delta=now-datetime.datetime.strptime(self.rob_info["last_rob"],"%Y-%m-%d %H:%M:%S")
        rest_cooldown=rob_config["robCooldown"]-delta.total_seconds()
        if delta.total_seconds()<rob_config["robCooldown"]:
            return f"还在冷却中哦~别急嘛——\n再等 {int(rest_cooldown//60)} 分 {int(rest_cooldown%60)} 秒 就好啦"
        r=rangeRandom(*rob_config["robRange"])
        rob_data=Data([r//10*10,r%10])
        if random.random()>self.rob_info["rate"]:#抢劫失败
            if rob_data.getBytes()>self.data.getBytes():#被抢光了
                rob_data=self.data
                self.data=Data([0,0],True)
                self.rob_info["last_rob"]=now.strftime("%Y-%m-%d %H:%M:%S")
                delta_rate=max(1,rob_data.getBytes()/2**(sum(rob_config["robRange"])/2))/100#计算成功率变化
                self.rob_info["rate"]=min(100,self.rob_info["rate"]+delta_rate)
                if str(target) in self.rob_info["robbed"]:#是不是第一次抢这个人
                    self.rob_info["robbed"][str(target)]["fail_times"]+=1
                    tmp=Data([self.rob_info["robbed"][str(target)]["fail_data"]["base"],self.rob_info["robbed"][str(target)]["fail_data"]["addition"]],self.rob_info["robbed"][str(target)]["fail_data"]["zero"])
                    tmp=plus(tmp,rob_data)
                    self.rob_info["robbed"][str(target)]["fail_data"]={"base":tmp.base,"addition":tmp.addition,"zero":tmp.is_zero}
                else:#初始化
                    self.rob_info["robbed"][str(target)]={"success_times":0,"success_data":{"base":0,"addition":0,"zero":True},"fail_times":1,"fail_data":{"base":rob_data.base,"addition":rob_data.addition,"zero":rob_data.is_zero}}
                self.info["data"]={"base":self.data.base,"addition":self.data.addition,"zero":self.data.is_zero}
                self.info["rob"]=self.rob_info
                self.updateUserInfo()
                log(self.id,"rob","-",rob_data,self.rob_info["last_rob"])
                target_user.addData(rob_data)
                if not self.id in target_user.rob_info["robbed_by"]:
                    target_user.rob_info["robbed_by"].append(self.id)
                target_user.info["rob"]=target_user.rob_info
                target_user.updateUserInfo()
                log(target,"rob","+",rob_data,self.rob_info["last_rob"])
                return f"( -{rob_data.display} / +{delta_rate*100:.2f}%) 抢劫失败啦，你被 {target_user.nickname} 抢走了 {rob_data.display} ，你现在什么都没有了！\n成功率增加了 {delta_rate*100:.2f}%，当前：{self.rob_info["rate"]*100:.2f}%"
            else:
                self.delData(rob_data)
                self.rob_info["last_rob"]=now.strftime("%Y-%m-%d %H:%M:%S")
                delta_rate=max(1,rob_data.getBytes()/2**(sum(rob_config["robRange"])/2))/100#计算成功率变化
                self.rob_info["rate"]=min(100,self.rob_info["rate"]+delta_rate)
                if str(target) in self.rob_info["robbed"]:#是不是第一次抢这个人
                    self.rob_info["robbed"][str(target)]["fail_times"]+=1
                    tmp=Data([self.rob_info["robbed"][str(target)]["fail_data"]["base"],self.rob_info["robbed"][str(target)]["fail_data"]["addition"]],self.rob_info["robbed"][str(target)]["fail_data"]["zero"])
                    tmp=plus(tmp,rob_data)
                    self.rob_info["robbed"][str(target)]["fail_data"]={"base":tmp.base,"addition":tmp.addition,"zero":tmp.is_zero}
                else:#初始化
                    self.rob_info["robbed"][str(target)]={"success_times":0,"success_data":{"base":0,"addition":0,"zero":True},"fail_times":1,"fail_data":{"base":rob_data.base,"addition":rob_data.addition,"zero":rob_data.is_zero}}
                self.info["rob"]=self.rob_info
                self.updateUserInfo()
                log(self.id,"rob","-",rob_data,self.rob_info["last_rob"])
                target_user.addData(rob_data)
                if not self.id in target_user.rob_info["robbed_by"]:
                    target_user.rob_info["robbed_by"].append(self.id)
                target_user.info["rob"]=target_user.rob_info
                target_user.updateUserInfo()
                log(target,"rob","+",rob_data,self.rob_info["last_rob"])
                return f"( -{rob_data.display} / +{delta_rate*100:.2f}%) 抢劫失败啦，你被 {target_user.nickname} 抢走了 {rob_data.display}\n成功率增加了 {delta_rate*100:.2f}%，当前：{self.rob_info["rate"]*100:.2f}%"
        else:#抢劫成功
            if rob_data.getBytes()>target_user.data.getBytes():#把对面抢光了
                rob_data=target_user.data
                target_user.data=Data([0,0],True)
                self.rob_info["last_rob"]=now.strftime("%Y-%m-%d %H:%M:%S")
                delta_rate=max(1,rob_data.getBytes()/2**(sum(rob_config["robRange"])/2))/100#计算成功率变化
                self.rob_info["rate"]=max(0,self.rob_info["rate"]-delta_rate)
                if str(target) in self.rob_info["robbed"]:#是不是第一次抢这个人
                    self.rob_info["robbed"][str(target)]["success_times"]+=1
                    tmp=Data([self.rob_info["robbed"][str(target)]["success_data"]["base"],self.rob_info["robbed"][str(target)]["success_data"]["addition"]],self.rob_info["robbed"][str(target)]["success_data"]["zero"])
                    tmp=plus(tmp,rob_data)
                    self.rob_info["robbed"][str(target)]["success_data"]={"base":tmp.base,"addition":tmp.addition,"zero":tmp.is_zero}
                else:#初始化
                    self.rob_info["robbed"][str(target)]={"success_times":1,"success_data":{"base":rob_data.base,"addition":rob_data.addition,"zero":rob_data.is_zero},"fail_times":0,"fail_data":{"base":0,"addition":0,"zero":True}}
                self.info["data"]={"base":self.data.base,"addition":self.data.addition,"zero":self.data.is_zero}
                self.info["rob"]=self.rob_info
                self.updateUserInfo()
                log(self.id,"rob","+",rob_data,self.rob_info["last_rob"])
                target_user.info["data"]={"base":target_user.data.base,"addition":target_user.data.addition,"zero":target_user.data.is_zero}
                if not self.id in target_user.rob_info["robbed_by"]:
                    target_user.rob_info["robbed_by"].append(self.id)
                target_user.info["rob"]=target_user.rob_info
                target_user.updateUserInfo()
                log(target,"rob","-",rob_data,self.rob_info["last_rob"])
                return f"( +{rob_data.display} / -{delta_rate*100:.2f}%) 抢劫成功，{target_user.nickname} 被你抢破产了...\n成功率减少了 {delta_rate*100:.2f}%，当前：{self.rob_info["rate"]*100:.2f}%"
            else:
                self.addData(rob_data)
                target_user.delData(rob_data)
                self.rob_info["last_rob"]=now.strftime("%Y-%m-%d %H:%M:%S")
                delta_rate=max(1,rob_data.getBytes()/2**(sum(rob_config["robRange"])/2))/100#计算成功率变化
                self.rob_info["rate"]=max(0,self.rob_info["rate"]-delta_rate)
                if str(target) in self.rob_info["robbed"]:#是不是第一次抢这个人
                    self.rob_info["robbed"][str(target)]["success_times"]+=1
                    tmp=Data([self.rob_info["robbed"][str(target)]["success_data"]["base"],self.rob_info["robbed"][str(target)]["success_data"]["addition"]],self.rob_info["robbed"][str(target)]["success_data"]["zero"])
                    tmp=plus(tmp,rob_data)
                    self.rob_info["robbed"][str(target)]["success_data"]={"base":tmp.base,"addition":tmp.addition,"zero":tmp.is_zero}
                else:#初始化
                    self.rob_info["robbed"][str(target)]={"success_times":1,"success_data":{"base":rob_data.base,"addition":rob_data.addition,"zero":rob_data.is_zero},"fail_times":0,"fail_data":{"base":0,"addition":0,"zero":True}}
                self.info["data"]={"base":self.data.base,"addition":self.data.addition,"zero":self.data.is_zero}
                self.info["rob"]=self.rob_info
                self.updateUserInfo()
                log(self.id,"rob","+",rob_data,self.rob_info["last_rob"])
                target_user.info["data"]={"base":target_user.data.base,"addition":target_user.data.addition,"zero":target_user.data.is_zero}
                if not self.id in target_user.rob_info["robbed_by"]:
                    target_user.rob_info["robbed_by"].append(self.id)
                target_user.info["rob"]=target_user.rob_info
                target_user.updateUserInfo()
                log(target,"rob","-",rob_data,self.rob_info["last_rob"])
                return f"( +{rob_data.display} / -{delta_rate*100:.2f}%) 抢劫成功，{target_user.nickname} 被你抢走了 {rob_data.display}！\n成功率减少了 {delta_rate*100:.2f}%，当前：{self.rob_info["rate"]*100:.2f}%"

def generateRank(ranks:list,target,length:int=10) -> list[str,bool]:
    """
    请提供格式化好的ranks: [[id(给target对照用),名字,值],...]
    target是需要的查找的id
    返回完整的msg消息
    """
    msg=""
    me=False
    for i in range(min(length,len(ranks))):
        user_info=ranks[i]
        user_id=user_info[0]
        nickname=user_info[1]
        value=user_info[2]
        msg+=f"{i+1}. {nickname}      {value}"
        if user_id==target:
            msg+="    <- 你在这里！"
            me=True
        msg+="\n"
    if not me:
        for i in range(len(ranks)):
            if ranks[i][0]==target:
                user_info=ranks[i]
                user_id=user_info[0]
                nickname=user_info[1]
                value=user_info[2]
                if i==length+1:#就一行，显示一下吧
                    msg+=f"{i}. {ranks[i-1][1]}      {ranks[i-1][2]}\n"
                elif i>length+1:#刚好第length个不需要省略号
                    msg+=f"......(省略 {i-length} 人)\n"
                msg+=f"{i+1}. {nickname}      {value}    <- 你在这里！\n"
                me=True
                break
    if not (len(ranks)<=length or (len(ranks)==i+1 and me)):#除了小于length个和有我并且我是最后一个以外的情况都需要加省略号
        msg+=f"......(剩余 {len(ranks)-max(length,i+1)} 人)\n"
    return [msg,me]

