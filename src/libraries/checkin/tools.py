import pathlib
import math
import time
import datetime
import random
from zoneinfo import ZoneInfo

from .data import *
from ..tools import *
from ...storage import checkin as checkin_storage
from ...services import checkin as checkin_service


DATA_PATH=pathlib.Path(__file__).resolve().parent.parent.parent.parent/"data"/"checkin"
CONFIG_PATH=DATA_PATH/"config.json"
USER_PATH=DATA_PATH/"data"/"user.json"
TIME_PATH=DATA_PATH/"data"/"time.json"
LOG_PATH=DATA_PATH/"data"/"logs"
ROB_CONFIG_PATH=DATA_PATH.parent/"rob"/"config.json"
OUT_PATH=DATA_PATH/"out"

VOLTAGE_LEVELS=[
    (0,"Steam"),
    (3,"ULV"),
    (5,"LV"),
    (7,"MV"),
    (9,"HV"),
    (11,"EV"),
    (13,"IV"),
    (15,"LuV"),
    (17,"ZPM"),
    (19,"UV"),
    (21,"UHV"),
    (23,"UEV"),
    (25,"UIV"),
    (27,"UMV"),
    (29,"UXV"),
    (31,"MAX")
]#GTNH电压

def getVoltageLevel(voltage:float) -> str:
    """获取电压等级"""
    for i in range(len(VOLTAGE_LEVELS)):
        if voltage<VOLTAGE_LEVELS[i][0]:
            return VOLTAGE_LEVELS[i-1][1]
    return VOLTAGE_LEVELS[-1][1]

def log(user_id:int,operation:str,change_type:str,created_at:datetime.datetime,data:Data|None=None,item_id:int|None=None,item_count:int|None=None,related_user_id:int|None=None,detail:str|None=None):
    """记录Data或物品变化"""

    checkin_storage.add_log(
        user_id=user_id,
        operation=operation,
        change_type=change_type,
        related_user_id=related_user_id,
        data_base=data.base if data else None,
        data_addition=data.addition if data else None,
        data_zero=data.is_zero if data else None,
        item_id=item_id,
        item_count=item_count,
        created_at=created_at,
        detail=detail
    )

class CheckDay:
    def __init__(self,date:datetime.datetime):
        self.date=date
        self.day=date.strftime("%Y-%m-%d")
        self.time=date.strftime("%H:%M:%S")
        self.daytime=f"{self.day} {self.time}"
        self.info=checkin_storage.get_checkin_by_date(self.date.date())#签到排名信息
    
    def getRank(self):
        """获取排名"""
        return len(self.info)+1

    def generateCheckedRank(self,target,length:int=10)->tuple[str,bool]:
        """生成签到排名"""
        nicknames=checkin_storage.get_user_nicknames()
        msg,me=generateRank([[i[0],nicknames.get(i[0],"Unknown"), datetime.datetime.strftime(i[1], "%H:%M:%S")] for i in self.info],target,length)
        return msg,me

    def firstType(self):
        """获取第一的类型：'year'/'month'/'day'/'',不是第一返回''"""
        last=checkin_storage.get_last_checkin_date(self.date.date())
        if last is None or last.year!=self.date.year:
            return "year"
        if last.month!=self.date.month:
            return "month"
        if last.day!=self.date.day:
            return "day"
        return ""
    
    def log(self,id,data:Data):
        """签到记录"""
        self.info.append([id,self.date])
        checkin_storage.add_checkin(id,self.date)
        log(user_id=id,operation="checkin",change_type="+",data=data,created_at=self.date)

    def makeup_log(self,id,data:Data,now:datetime.datetime,date:datetime.datetime):
        """补签记录"""
        self.info.append([id,date])
        log(user_id=id,operation="makeup_checkin",change_type="-",detail=str(date.date()),data=data,created_at=now)

class User:
    def __init__(self,uid:int,nickname:str=""):
        self.id=uid
        self.nickname=nickname
        user_data=checkin_storage.get_user(self.id)
        if user_data is None:
            checkin_storage.create_user(self.id,self.nickname)
            user_data=checkin_storage.get_user(self.id)
        if nickname and nickname!=self.nickname:
            self.nickname=nickname
            checkin_storage.update_user_nickname(self.id,nickname)
        self.last_check:datetime.date=user_data["last_checkin"]
        self.total_check=user_data["total"]
        self.consecutive_check=user_data["consecutive"]
        self.max_consecutive_check=user_data["max_consecutive"]
        self.data=Data(
            [user_data["data_base"],user_data["data_addition"]],
            user_data["data_zero"]
        )
        self.rob_rate=user_data["rob_rate"]
        self.last_rob:datetime.datetime=user_data["last_rob"]
        self.items={}
        self.reloadUserInfo()
    
    def reloadUserInfo(self):
        """重载用户信息"""
        user=checkin_storage.get_user(self.id)
        if user is None:
            checkin_storage.create_user(self.id,self.nickname)
            user=checkin_storage.get_user(self.id)

        self.nickname=user["nickname"]
        self.last_check=user["last_checkin"]
        self.total_check=user["total"]
        self.consecutive_check=user["consecutive"]
        self.max_consecutive_check=user["max_consecutive"]
        self.data=Data(
            [user["data_base"],user["data_addition"]],
            user["data_zero"]
        )
        robbed=checkin_storage.get_rob_records(self.id)
        self.rob_rate=user["rob_rate"]
        self.last_rob=user["last_rob"]
        self.robbed={target_id:record for target_id,record in robbed.items()}
        items=checkin_storage.get_user_items(self.id)
        self.items={
            item_id:item
            for item_id,item in items.items()
        }
    
    def updateUserInfo(self):
        """更新保存用户基础信息"""
        checkin_storage.update_user(
            user_id=self.id,
            nickname=self.nickname,
            last_checkin=self.last_check,
            total=self.total_check,
            consecutive=self.consecutive_check,
            max_consecutive=self.max_consecutive_check,
            data_base=self.data.base,
            data_addition=self.data.addition,
            data_zero=self.data.is_zero,
            rob_rate=self.rob_rate,
            last_rob=self.last_rob
        )
    
    def addData(self,data:Data):
        """增加用户data"""
        self.data=plus(self.data,data)

    def delData(self,data:Data):
        """扣除用户data"""
        self.data=substract(self.data,data)
    
    def check(self) -> dict:
        """签到并更新数据，返回数据量和增益状态"""
        now=datetime.datetime.now(ZoneInfo("Asia/Shanghai"))
        today=CheckDay(now)
        rank=today.getRank()
        check_config=jsonLoad(CONFIG_PATH)
        #获取data量
        data=Data([0,0],zero=True)
        result={"data":data,"consecutivebonus":1,"ratingbonus":1,"thursday":False,"super":None,"rank":rank,"rankbonus":1,"basedata":data,"first":today.firstType(),"items":[]}
        #result字段说明
        #data: 最终data量
        #consecutivebonus: 连续签到加成，乘
        #ratingbonus: rating加成，乘#已删除，rating影响的是各种操作的口径
        #thursday: 是否中了fkxqs
        #super: 是否中了大奖
        #rank: 签到排名
        #rankbonus: 签到排名加成，乘
        #basedata: 最原始未经任何加成的data
        #first: 第一类型
        #items: 物品列表
        if now.weekday()+1==4:#周四
            if random.random()<=check_config["thursday"][0]-check_config["thursday"][1]*(rank-1):
                result["thursday"]=True
                data=plus(data,Data([20,math.log2(50)]))
        if random.random()<=check_config["superBonus"]["probability"]:
            superbonus=rangeRandom(*check_config["superBonus"]["range"])
            superbonus=Data([superbonus//10*10,superbonus%10])
            result["super"]=superbonus
            data=plus(data,superbonus)
        ratingbonus=1+0.001*self.getRating()["rating"]
        basedata=rangeRandom(check_config["checkDataRange"][0]*ratingbonus,check_config["checkDataRange"][1]*ratingbonus)
        basedata=Data([basedata//10*10,basedata%10])
        result["basedata"]=basedata
        data=plus(data,basedata)
        if rank<=len(check_config["firstBonus"]):#前几
            final_data=exponent(data,check_config["firstBonus"][rank-1])
            bonus_rate=final_data.getBytes()/data.getBytes()
            result["rankbonus"]=bonus_rate
            data=final_data
        #data=exponent(data,math.log2(1+self.getRating()["rating"]))#rating加成
        #result["ratingbonus"]=1+self.getRating()["rating"]
        consecutive_bonus=1+0.003*(self.consecutive_check-1)+0.00001*(self.consecutive_check-1)**2
        result["consecutivebonus"]=consecutive_bonus
        data=Data([data.base,data.addition+math.log2(consecutive_bonus)])#连续签到加成
        result["data"]=data
        #更新数据
        self.addData(data)
        yesterday=(now-datetime.timedelta(days=1)).date()
        if self.last_check==yesterday:
            self.consecutive_check+=1
        else:
            self.consecutive_check=1
        self.max_consecutive_check=max(self.consecutive_check,self.max_consecutive_check)
        self.last_check=now.date()
        self.total_check+=1
        self.updateUserInfo()
        today.log(self.id,data)
        reward=self.gacha()
        if reward:
            result["items"].append(reward)
        return result

    def makeup_check(self,date:datetime.datetime)->dict:
        """补签"""
        checkday=CheckDay(date)
        result={"success":False,"msg":"","data":Data([0,0],zero=True),"items":[],"first":checkday.firstType(),"rank":checkday.getRank(),"rankbonus":1}
        now=datetime.datetime.now(ZoneInfo("Asia/Shanghai"))
        if date.date()>=now.date():#不能补签今天或未来
            result["msg"]="不能补签今天或未来的日期"
            return result
        if self.id in [i[0] for i in checkday.info]:#已经签到过了
            result["msg"]="这天已经签到过了"
            return result
        checkcost=makeup_cost(now,date,self.getRating()["rating"])
        if self.data.getBytes()<checkcost.getBytes():
            result["msg"]=f"补签失败，Data不足喵~（{checkcost.display}）"
            return result
        if not checkin_storage.add_makeupcheckin(self.id,now,date.date()):
            result["msg"]="补签失败"
            return result
        self.delData(checkcost)
        checkday.makeup_log(self.id,checkcost,now,date)
        result["success"]=True
        self.total_check+=1
        user_checkin_logs=checkin_storage.get_checkin_dates(self.id)
        max_consecutive=0
        consecutive=0
        for i in range(len(user_checkin_logs)):
            if i==0:
                consecutive=1
            elif (user_checkin_logs[i]-user_checkin_logs[i-1]).days==1:
                consecutive+=1
            else:
                max_consecutive=max(max_consecutive,consecutive)
                consecutive=1
        max_consecutive=max(max_consecutive,consecutive)
        self.max_consecutive_check=max_consecutive
        self.consecutive_check=consecutive
        self.updateUserInfo()
        return result

    def rob(self,target:int):
        """模拟一次抢劫其他人，target为被抢人的id"""
        target_user=User(target)
        now=datetime.datetime.now(ZoneInfo("Asia/Shanghai"))
        rob_config=jsonLoad(ROB_CONFIG_PATH)
        delta=now-self.last_rob
        rest_cooldown=rob_config["robCooldown"]-delta.total_seconds()
        if delta.total_seconds()<rob_config["robCooldown"]:
            return f"还在冷却中哦~别急嘛——\n再等 {int(rest_cooldown//60)} 分 {int(rest_cooldown%60)} 秒 就好啦"
        self.last_rob=now
        ratingbonus=1+0.001*self.getRating()["rating"]
        r=rangeRandom(rob_config["robRange"][0]*ratingbonus,rob_config["robRange"][1]*ratingbonus)
        rob_data=Data([r//10*10,r%10])
        if random.random()>self.rob_rate:#抢劫失败
            if rob_data.getBytes()>self.data.getBytes():#被抢光了
                rob_data=self.data
                self.data=Data([0,0],True)
                delta_rate=min(max(1,rob_data.getBytes()/2**(sum(rob_config["robRange"])/2)),8)/100#计算成功率变化
                self.rob_rate=min(1,self.rob_rate+delta_rate)
                if target in self.robbed:#是不是第一次抢这个人
                    self.robbed[target]["fail_times"]+=1
                    tmp=Data([self.robbed[target]["fail_data"]["base"],self.robbed[target]["fail_data"]["addition"]],self.robbed[target]["fail_data"]["zero"])
                    tmp=plus(tmp,rob_data)
                    self.robbed[target]["fail_data"]={"base":tmp.base,"addition":tmp.addition,"zero":tmp.is_zero}
                else:#初始化
                    self.robbed[target]={"success_times":0,"success_data":{"base":0,"addition":0,"zero":True},"fail_times":1,"fail_data":{"base":rob_data.base,"addition":rob_data.addition,"zero":rob_data.is_zero}}
                checkin_storage.update_rob_record(self.id,target,self.robbed[target])
                self.updateUserInfo()
                log(user_id=self.id,operation="rob",change_type="-",detail="initiator",related_user_id=target,data=rob_data,created_at=now)
                target_user.addData(rob_data)
                target_user.updateUserInfo()
                log(user_id=target,operation="rob",change_type="+",detail="target",related_user_id=self.id,data=rob_data,created_at=now)
                return f"( -{rob_data.display} / +{delta_rate*100:.2f}%) 抢劫失败啦，你被 {target_user.nickname} 抢走了 {rob_data.display} ，你现在什么都没有了！\n成功率增加了 {delta_rate*100:.2f}%，当前：{self.rob_rate*100:.2f}%"
            else:
                self.delData(rob_data)
                delta_rate=min(max(1,rob_data.getBytes()/2**(sum(rob_config["robRange"])/2)),8)/100#计算成功率变化
                self.rob_rate=min(1,self.rob_rate+delta_rate)
                if target in self.robbed:#是不是第一次抢这个人
                    self.robbed[target]["fail_times"]+=1
                    tmp=Data([self.robbed[target]["fail_data"]["base"],self.robbed[target]["fail_data"]["addition"]],self.robbed[target]["fail_data"]["zero"])
                    tmp=plus(tmp,rob_data)
                    self.robbed[target]["fail_data"]={"base":tmp.base,"addition":tmp.addition,"zero":tmp.is_zero}
                else:#初始化
                    self.robbed[target]={"success_times":0,"success_data":{"base":0,"addition":0,"zero":True},"fail_times":1,"fail_data":{"base":rob_data.base,"addition":rob_data.addition,"zero":rob_data.is_zero}}
                checkin_storage.update_rob_record(self.id,target,self.robbed[target])
                self.updateUserInfo()
                log(user_id=self.id,operation="rob",change_type="-",detail="initiator",related_user_id=target,data=rob_data,created_at=now)
                target_user.addData(rob_data)
                target_user.updateUserInfo()
                log(user_id=target,operation="rob",change_type="+",detail="target",related_user_id=self.id,data=rob_data,created_at=now)
                return f"( -{rob_data.display} / +{delta_rate*100:.2f}%) 抢劫失败啦，你被 {target_user.nickname} 抢走了 {rob_data.display}\n成功率增加了 {delta_rate*100:.2f}%，当前：{self.rob_rate*100:.2f}%"
        else:#抢劫成功
            if rob_data.getBytes()>target_user.data.getBytes():#把对面抢光了
                rob_data=target_user.data
                target_user.data=Data([0,0],True)
                self.addData(rob_data)
                delta_rate=min(max(1,rob_data.getBytes()/2**(sum(rob_config["robRange"])/2)),8)/100#计算成功率变化
                self.rob_rate=max(0,self.rob_rate-delta_rate)
                if target in self.robbed:#是不是第一次抢这个人
                    self.robbed[target]["success_times"]+=1
                    tmp=Data([self.robbed[target]["success_data"]["base"],self.robbed[target]["success_data"]["addition"]],self.robbed[target]["success_data"]["zero"])
                    tmp=plus(tmp,rob_data)
                    self.robbed[target]["success_data"]={"base":tmp.base,"addition":tmp.addition,"zero":tmp.is_zero}
                else:#初始化
                    self.robbed[target]={"success_times":1,"success_data":{"base":rob_data.base,"addition":rob_data.addition,"zero":rob_data.is_zero},"fail_times":0,"fail_data":{"base":0,"addition":0,"zero":True}}
                checkin_storage.update_rob_record(self.id,target,self.robbed[target])
                self.updateUserInfo()
                log(user_id=self.id,operation="rob",change_type="+",detail="initiator",related_user_id=target,data=rob_data,created_at=now)
                target_user.updateUserInfo()
                log(user_id=target,operation="rob",change_type="-",detail="target",related_user_id=self.id,data=rob_data,created_at=now)
                return f"( +{rob_data.display} / -{delta_rate*100:.2f}%) 抢劫成功，{target_user.nickname} 被你抢破产了...\n成功率减少了 {delta_rate*100:.2f}%，当前：{self.rob_rate*100:.2f}%"
            else:
                self.addData(rob_data)
                target_user.delData(rob_data)
                delta_rate=min(max(1,rob_data.getBytes()/2**(sum(rob_config["robRange"])/2)),8)/100#计算成功率变化
                self.rob_rate=max(0,self.rob_rate-delta_rate)
                if target in self.robbed:#是不是第一次抢这个人
                    self.robbed[target]["success_times"]+=1
                    tmp=Data([self.robbed[target]["success_data"]["base"],self.robbed[target]["success_data"]["addition"]],self.robbed[target]["success_data"]["zero"])
                    tmp=plus(tmp,rob_data)
                    self.robbed[target]["success_data"]={"base":tmp.base,"addition":tmp.addition,"zero":tmp.is_zero}
                else:#初始化
                    self.robbed[target]={"success_times":1,"success_data":{"base":rob_data.base,"addition":rob_data.addition,"zero":rob_data.is_zero},"fail_times":0,"fail_data":{"base":0,"addition":0,"zero":True}}
                checkin_storage.update_rob_record(self.id,target,self.robbed[target])
                self.updateUserInfo()
                log(user_id=self.id,operation="rob",change_type="+",detail="initiator",related_user_id=target,data=rob_data,created_at=now)
                target_user.updateUserInfo()
                log(user_id=target,operation="rob",change_type="-",detail="target",related_user_id=self.id,data=rob_data,created_at=now)
                return f"( +{rob_data.display} / -{delta_rate*100:.2f}%) 抢劫成功，{target_user.nickname} 被你抢走了 {rob_data.display}！\n成功率减少了 {delta_rate*100:.2f}%，当前：{self.rob_rate*100:.2f}%"

    def gacha(self):
        """抽取一个物品"""
        check_config=jsonLoad(CONFIG_PATH)
        items=check_config["items"]
        result={}
        r=random.random()
        for item in items:
            r-=item["probability"]
            if r<0:
                result=item
                item_id=result["id"]
                if item_id in self.items:
                    self.items[item_id]["count"]+=1
                else:
                    self.items[item_id]={
                        "name":result["name"],
                        "count":1
                    }
                checkin_storage.add_user_item(self.id,result["id"],result["name"],1)
                break
        if result:
            log(user_id=self.id,operation="item",change_type="+",created_at=datetime.datetime.now(ZoneInfo("Asia/Shanghai")),item_id=result["id"],item_count=1)
        return result
    
    def getLogs(self,lines:int=-1):
        """获取用户的data变动日志，lines为获取的记录条数，-1为全部"""
        return checkin_storage.get_user_logs(self.id,lines)
    
    def getLogsByDate(self,date:datetime.date):
        """根据日期获取用户的data变动日志"""
        return checkin_storage.get_user_logs_by_date(self.id,date)
    
    def getCheckInfo(self,day:datetime.date):
        """获取用户的签到信息，只能获取一天的
        返回[bool,h:m:s,rank]#是否签到，签到时间，签到排名，是否为补签"""
        checkin_at=checkin_storage.get_checkin_time(self.id,day)
        if checkin_at is None:
            return [False,None,None,False]
        makeup=False
        if checkin_at.date()!=day:
            makeup=True

        return [True,checkin_at.strftime("%H:%M:%S"),checkin_storage.get_checkin_rank(self.id,day),makeup]
    
    def getRobInfo(self):
        return checkin_service.get_rob_rank_data()

    def getRating(self):
        """获取用户rating"""
        return checkin_service.get_user_rating(self.id)

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

def makeup_cost(now:datetime.datetime,target:datetime.datetime,rating:float)->Data:
    """获取补签消耗"""#现在是第一天1MB，每隔4天x2
    days=(now.date()-target.date()).days
    exp=20+(days-1)/4-math.log2(1+rating/100)
    return Data([exp//10*10,exp%10],False)
