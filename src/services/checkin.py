import calendar
import datetime

from ..storage import checkin as checkin_storage
from ..libraries.checkin.data import *


def _data_dict(data:Data)->dict:
    """将Data转换为API可返回的数据"""
    return {
        "base":data.base,
        "addition":data.addition,
        "zero":data.is_zero,
        "display":data.display,
        "bytes":data.getBytes()
    }

def get_user_info(user_id:int)->dict|None:
    """获取用户基础信息"""
    user=checkin_storage.get_user(user_id)

    if user is None:
        return None

    data=Data(
        [user["data_base"],user["data_addition"]],
        user["data_zero"]
    )

    return {
        "user_id":user["user_id"],
        "nickname":user["nickname"],
        "data":_data_dict(data),
        "checkin":{
            "last_checkin":user["last_checkin"],
            "total":user["total"],
            "consecutive":user["consecutive"],
            "max_consecutive":user["max_consecutive"]
        },
        "rob":{
            "rate":user["rob_rate"],
            "last_rob":user["last_rob"]
        }
    }

def get_user_calendar(user_id:int,year:int,month:int)->dict|None:
    """获取用户指定月份的签到情况"""
    if checkin_storage.get_user(user_id) is None:
        return None

    days=calendar.monthrange(year,month)[1]
    start=datetime.date(year,month,1)
    end=datetime.date(year,month,days)

    records=checkin_storage.get_user_calendar_records(user_id,start,end)
    dates=[record["date"] for record in records]

    return {
        "year":year,
        "month":month,
        "count":len(records),
        "checked_dates":dates,
        "records":records
    }

def get_daily_checkin_rank(date:datetime.date)->list[dict]:
    """获取指定日期签到排行榜"""
    records=checkin_storage.get_checkin_by_date(date)
    nicknames=checkin_storage.get_user_nicknames()
    return [{
        "rank":rank,
        "user_id":record[0],
        "nickname":nicknames.get(record[0],"Unknown"),
        "checkin_at":record[1]
    } for rank,record in enumerate(records,1)]

def get_data_rank()->list[dict]:
    """获取Data排行榜"""
    ranks=[]
    for user in checkin_storage.get_all_user_data():
        data=Data(
            [user["base"],user["addition"]],
            user["zero"]
        )
        if not user["nickname"] or data.getBytes()<=0:
            continue
        ranks.append({
            "user_id":user["user_id"],
            "nickname":user["nickname"],
            "data":_data_dict(data)
        })

    ranks.sort(key=lambda x:x["data"]["bytes"],reverse=True)
    for rank,user in enumerate(ranks,1):
        user["rank"]=rank

    return ranks

def get_user_rob_info(user_id:int)->dict|None:
    """获取用户抢劫与被抢统计"""
    if checkin_storage.get_user(user_id) is None:
        return None

    robbed=checkin_storage.get_rob_records(user_id)
    robbed_by=checkin_storage.get_rob_records_by_target(user_id)
    nicknames=checkin_storage.get_user_nicknames()

    robbed_records=[]

    for target_id,record in robbed.items():
        robbed_records.append({
            "target_user_id":target_id,
            "target_nickname":nicknames.get(target_id,"Unknown"),
            "success_times":record["success_times"],
            "fail_times":record["fail_times"],
            "success_data":record["success_data"],
            "fail_data":record["fail_data"]
        })

    return {
        "user_id":user_id,
        "robbed":robbed_records,
        "robbed_by":robbed_by
    }

def get_rob_rank_data()->tuple[dict,dict,dict,dict]:
    """获取用户抢劫详细数据"""
    robtimes_ranks={}
    robbedtimes_ranks={}
    rob_gain_data_ranks={}
    rob_give_data_ranks={}

    records=checkin_storage.get_all_rob_records()
    for record in records:
        uid=record["user_id"]
        target=record["target_id"]
        user_nickname=record["user_nickname"]
        target_nickname=record["target_nickname"]

        # 初始化主动抢劫次数
        if uid not in robtimes_ranks:
            robtimes_ranks[uid]=[0,0,uid,user_nickname]
        # 初始化被抢次数
        if target not in robbedtimes_ranks:
            robbedtimes_ranks[target]=[0,0,target,target_nickname]

        robtimes_ranks[uid][0]+=record["success_times"]
        robtimes_ranks[uid][1]+=record["fail_times"]
        robbedtimes_ranks[target][0]+=record["success_times"]
        robbedtimes_ranks[target][1]+=record["fail_times"]

        # 初始化Data统计
        if uid not in rob_gain_data_ranks:
            rob_gain_data_ranks[uid]=[Data([0,0],True),Data([0,0],True),uid,user_nickname]
        if uid not in rob_give_data_ranks:
            rob_give_data_ranks[uid]=[Data([0,0],True),Data([0,0],True),uid,user_nickname]
        if target not in rob_gain_data_ranks:
            rob_gain_data_ranks[target]=[Data([0,0],True),Data([0,0],True),target,target_nickname]
        if target not in rob_give_data_ranks:
            rob_give_data_ranks[target]=[Data([0,0],True),Data([0,0],True),target,target_nickname]

        success_data=Data(
            [record["success_data"]["base"],record["success_data"]["addition"]],
            record["success_data"]["zero"]
        )
        fail_data=Data(
            [record["fail_data"]["base"],record["fail_data"]["addition"]],
            record["fail_data"]["zero"]
        )

        # user抢成功
        rob_gain_data_ranks[uid][0]=plus(rob_gain_data_ranks[uid][0],success_data)
        rob_give_data_ranks[target][0]=plus(rob_give_data_ranks[target][0],success_data)
        # user抢失败
        rob_give_data_ranks[uid][1]=plus(rob_give_data_ranks[uid][1],fail_data)
        rob_gain_data_ranks[target][1]=plus(rob_gain_data_ranks[target][1],fail_data)

    return robtimes_ranks,robbedtimes_ranks,rob_gain_data_ranks,rob_give_data_ranks

def get_rob_rank_response()->dict:
    """获取API使用的抢劫排行榜"""
    robtimes,robbedtimes,gain_data,give_data=get_rob_rank_data()

    robtimes=sorted(robtimes.values(),key=lambda x:x[0]+x[1],reverse=True)
    robbedtimes=sorted(robbedtimes.values(),key=lambda x:x[0]+x[1],reverse=True)
    gain_data=sorted(gain_data.values(),key=lambda x:x[0].getBytes()+x[1].getBytes(),reverse=True)
    give_data=sorted(give_data.values(),key=lambda x:x[0].getBytes()+x[1].getBytes(),reverse=True)

    return {
        "rob_times":[
            {
                "rank":rank,
                "user_id":i[2],
                "nickname":i[3],
                "total":i[0]+i[1],
                "success":i[0],
                "fail":i[1]
            }
            for rank,i in enumerate(robtimes,1)
        ],
        "robbed_times":[
            {
                "rank":rank,
                "user_id":i[2],
                "nickname":i[3],
                "total":i[0]+i[1],
                "success":i[0],
                "fail":i[1]
            }
            for rank,i in enumerate(robbedtimes,1)
        ],
        "gain_data":[
            {
                "rank":rank,
                "user_id":i[2],
                "nickname":i[3],
                "total":_data_dict(plus(i[0],i[1])),
                "active":_data_dict(i[0]),
                "passive":_data_dict(i[1])
            }
            for rank,i in enumerate(gain_data,1)
        ],
        "loss_data":[
            {
                "rank":rank,
                "user_id":i[2],
                "nickname":i[3],
                "total":_data_dict(plus(i[0],i[1])),
                "robbed":_data_dict(i[0]),
                "failed":_data_dict(i[1])
            }
            for rank,i in enumerate(give_data,1)
        ]
    }

def _convert_log(log:dict)->dict:
    """将旧版日志结构转换为API结构"""

    result={
        "id":log["id"],
        "operation":log["operate"],
        "change_type":log["type"],
        "related_user_id":log["related_user_id"],
        "created_at":datetime.datetime.strptime(
            log["time"],
            "%Y-%m-%d %H:%M:%S"
        ),
        "data":log.get("data"),
        "item":log.get("item"),
        "detail":log.get("detail"),
    }

    return result

def get_user_logs(user_id:int,date:datetime.date|None=None,limit:int=-1)->list[dict]|None:
    """获取用户日志"""

    if checkin_storage.get_user(user_id) is None:
        return None

    if date is not None:
        logs=checkin_storage.get_user_logs_by_date(user_id,date)
    else:
        logs=checkin_storage.get_user_logs(user_id,limit)

    return [_convert_log(log) for log in logs]