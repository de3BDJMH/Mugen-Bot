import datetime

from fastapi import APIRouter,HTTPException,Query

from ...services import checkin as checkin_service
from ..schemas.checkin import (
    UserInfoResponse,
    UserCalendarResponse,
    UserLogsResponse,
    UserRobResponse,
    DailyCheckinRankResponse,
    DataRankResponse,
    RobRankResponse
)


router=APIRouter(
    prefix="/api/checkin",
    tags=["签到系统"]
)


@router.get(
    "/user/{user_id}",
    response_model=UserInfoResponse,
    summary="获取用户签到信息",
    description="获取指定用户的Data、签到统计以及抢劫基础信息。"
)
def get_user_info(user_id:int):
    """获取用户签到系统基础信息"""

    data=checkin_service.get_user_info(user_id)

    if data is None:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    return data

@router.get(
    "/user/{user_id}/calendar",
    response_model=UserCalendarResponse,
    summary="获取用户月度签到记录",
    description="获取指定用户在某年某月的签到日期、签到时间以及每日签到排名。"
)
def get_user_calendar(
    user_id:int,
    year:int=Query(description="年份"),
    month:int=Query(ge=1,le=12,description="月份")
):
    """获取用户指定月份签到情况"""

    try:
        data=checkin_service.get_user_calendar(
            user_id,
            year,
            month
        )
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid year or month"
        )

    if data is None:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    return data

@router.get(
    "/user/{user_id}/logs",
    response_model=UserLogsResponse,
    summary="获取用户日志",
    description=(
        "获取指定用户的签到系统日志。"
        "可通过date查询某一天日志；未提供date时可通过limit限制最近日志数量。"
    )
)
def get_user_logs(
    user_id:int,
    date:datetime.date|None=Query(
        default=None,
        description="指定日期，格式YYYY-MM-DD"
    ),
    limit:int=Query(
        default=-1,
        ge=-1,
        description="返回最近日志数量，-1表示全部"
    )
):
    """获取用户签到系统日志"""

    data=checkin_service.get_user_logs(
        user_id,
        date,
        limit
    )

    if data is None:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    return {
        "user_id":user_id,
        "count":len(data),
        "logs":data
    }

@router.get(
    "/rank/daily",
    response_model=DailyCheckinRankResponse,
    summary="获取每日签到排行榜",
    description="获取指定日期所有签到用户，并按照签到时间生成排名。"
)
def get_daily_checkin_rank(
    date:datetime.date=Query(
        description="查询日期，格式YYYY-MM-DD"
    )
):
    """获取指定日期签到排行榜"""

    ranks=checkin_service.get_daily_checkin_rank(date)

    return {
        "date":date,
        "ranks":ranks
    }

@router.get(
    "/rank/data",
    response_model=DataRankResponse,
    summary="获取Data排行榜",
    description="获取拥有Data的用户，并按照Data字节数从高到低排序。"
)
def get_data_rank():
    """获取Data排行榜"""

    return {
        "ranks":checkin_service.get_data_rank()
    }

@router.get(
    "/user/{user_id}/rob",
    response_model=UserRobResponse,
    summary="获取用户抢劫统计",
    description="获取指定用户主动抢劫其他用户以及被其他用户抢劫的历史统计。"
)
def get_user_rob_info(user_id:int):
    """获取用户抢劫关系统计"""

    data=checkin_service.get_user_rob_info(user_id)

    if data is None:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    return data

@router.get(
    "/rank/rob",
    response_model=RobRankResponse,
    summary="获取抢劫排行榜",
    description=(
        "获取抢劫次数、被抢次数、抢劫获得Data以及抢劫失去Data四类排行榜。"
    )
)
def get_rob_rank():
    """获取全部抢劫排行榜"""

    return checkin_service.get_rob_rank_response()