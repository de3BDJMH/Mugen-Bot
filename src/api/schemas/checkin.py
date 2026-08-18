from pydantic import BaseModel, Field
import datetime

#最基础的Data货币
class DataInfo(BaseModel):
    base: int = Field(description="Data 的基础单位的指数，为10的倍数，用于转换单位")
    addition: float = Field(description="Data 的值，为指数，例如2表示有4 xB Data，x由base决定")
    zero: bool = Field(description="Data 是否为 0B，只要这个字段为True即为0B")
    display:str=Field(description="格式化后的Data文本")
    bytes:int=Field(description="Data对应的字节数，用于排序和比例计算")

class RobDataInfo(BaseModel):#抢劫的少两个字段
    base: int = Field(description="Data 的基础单位的指数，为10的倍数，用于转换单位")
    addition: float = Field(description="Data 的值，为指数，例如2表示有4 xB Data，x由base决定")
    zero: bool = Field(description="Data 是否为 0B，只要这个字段为True即为0B")

#用户数据
class CheckinSummary(BaseModel):
    """用户签到概况"""

    last_checkin:datetime.date|None=Field(description="最近一次签到日期")
    total:int=Field(description="累计签到天数")
    consecutive:int=Field(description="当前连续签到天数")
    max_consecutive:int=Field(description="最大连续签到天数")

class RobSummary(BaseModel):
    """用户抢劫概况"""

    rate:float=Field(description="当前抢劫成功率，范围0~1")
    last_rob:datetime.datetime|None=Field(description="最近一次抢劫时间")

class UserInfoResponse(BaseModel):
    """用户签到系统基础信息"""

    user_id:int=Field(description="用户QQ号")
    nickname:str=Field(description="用户昵称")
    data:DataInfo
    checkin:CheckinSummary
    rob:RobSummary

class CalendarRecord(BaseModel):
    """单日签到记录"""

    date:datetime.date=Field(description="签到日期")
    checkin_at:datetime.datetime=Field(description="签到时间")
    rank:int=Field(description="当日签到排名")

class UserCalendarResponse(BaseModel):
    """用户指定月份签到情况"""

    year:int=Field(description="年份")
    month:int=Field(description="月份")
    count:int=Field(description="本月签到天数")
    checked_dates:list[datetime.date]=Field(description="本月所有已签到日期")
    records:list[CalendarRecord]=Field(description="本月签到详细记录")

#日志
class LogData(BaseModel):
    """日志中的Data变化"""

    base:int
    addition:float
    zero:bool

class LogItem(BaseModel):
    """日志中的物品变化"""

    item_id:int
    count:int

class LogRecord(BaseModel):
    """签到系统日志记录"""

    id:int=Field(description="日志ID")
    operation:str=Field(description="操作类型，如checkin、rob、send、item")
    change_type:str|None=Field(description="变化类型，+或-")
    related_user_id:int|None=Field(description="相关用户ID，例如抢劫对象")
    created_at:datetime.datetime=Field(description="日志产生时间")
    data:LogData|None=None
    item:LogItem|None=None
    detail:str|None=None

class UserLogsResponse(BaseModel):
    """用户日志查询结果"""

    user_id:int
    count:int
    logs:list[LogRecord]

#排行榜
class DailyCheckinRankItem(BaseModel):
    """每日签到排行榜单项"""

    rank:int
    user_id:int
    nickname:str
    checkin_at:datetime.datetime

class DailyCheckinRankResponse(BaseModel):
    """每日签到排行榜"""

    date:datetime.date
    ranks:list[DailyCheckinRankItem]

class DataRankItem(BaseModel):
    """Data排行榜单项"""

    rank:int
    user_id:int
    nickname:str
    data:DataInfo

class DataRankResponse(BaseModel):
    """Data排行榜"""

    ranks:list[DataRankItem]

#抢劫数据
class RobRecordData(BaseModel):
    """与某用户之间的抢劫统计"""

    success_times:int
    fail_times:int
    success_data:DataInfo
    fail_data:DataInfo

class OutgoingRobRecord(BaseModel):
    """用户主动抢劫某人的统计"""

    target_user_id:int
    target_nickname:str
    success_times:int
    fail_times:int
    success_data:RobDataInfo
    fail_data:RobDataInfo

class IncomingRobRecord(BaseModel):
    """其他用户抢劫当前用户的统计"""

    user_id:int
    nickname:str
    success_times:int
    fail_times:int
    success_data:RobDataInfo
    fail_data:RobDataInfo

class UserRobResponse(BaseModel):
    """用户抢劫关系数据"""

    user_id:int
    robbed:list[OutgoingRobRecord]
    robbed_by:list[IncomingRobRecord]

#抢劫排行榜
class RobTimesRankItem(BaseModel):
    """抢劫次数排行单项"""

    rank:int
    user_id:int
    nickname:str
    total:int
    success:int
    fail:int

class RobDataGainRankItem(BaseModel):
    """抢劫获得Data排行单项"""

    rank:int
    user_id:int
    nickname:str
    total:DataInfo
    active:DataInfo=Field(description="主动抢劫成功获得的Data")
    passive:DataInfo=Field(description="别人抢劫失败送来的Data")

class RobDataLossRankItem(BaseModel):
    """抢劫失去Data排行单项"""

    rank:int
    user_id:int
    nickname:str
    total:DataInfo
    robbed:DataInfo=Field(description="被别人抢走的Data")
    failed:DataInfo=Field(description="主动抢劫失败送出的Data")

class RobRankResponse(BaseModel):
    """抢劫排行榜集合"""

    rob_times:list[RobTimesRankItem]=Field(description="主动抢劫次数排行榜")
    robbed_times:list[RobTimesRankItem]=Field(description="被抢次数排行榜")
    gain_data:list[RobDataGainRankItem]=Field(description="通过抢劫获得Data排行榜")
    loss_data:list[RobDataLossRankItem]=Field(description="通过抢劫失去Data排行榜")