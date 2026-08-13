import datetime
import re
import sqlite3

from fastapi import APIRouter,HTTPException,Query

from ...libraries.tools import ROOT_PATH
from ..schemas.charcounter import DailyStatisticsResponse,AllTimeStatisticsResponse,DailyCharacterCount,CharacterSummary,CharacterCount


DB_PATH=ROOT_PATH/"data"/"charcounter"/"database"/"data.db"
DATE_TABLE=re.compile(r"^\d{4}_\d{1,2}_\d{1,2}$")


def get_date_tables(cursor:sqlite3.Cursor)->dict[datetime.date,list[str]]:
    """获取所有合法日期表，并按真实日期归类。"""

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables=[row[0] for row in cursor.fetchall()]

    result={}
    for table in tables:
        if not DATE_TABLE.fullmatch(table):
            continue
        try:
            date=datetime.datetime.strptime(table,"%Y_%m_%d").date()
        except ValueError:
            continue
        if date not in result:
            result[date]=[]
        result[date].append(table)

    return result

def get_daily_counts(start:datetime.date,end:datetime.date)->list[DailyCharacterCount]:
    """读取指定日期范围内每天的字符数量。"""

    result=[]
    with sqlite3.connect(f"file:{DB_PATH.resolve().as_posix()}?mode=ro",uri=True) as conn:
        cursor=conn.cursor()
        date_tables=get_date_tables(cursor)

        current=start
        while current<=end:
            count=0
            for table in date_tables.get(current,[]):
                cursor.execute(f"SELECT SUM(n) FROM `{table}`")
                count+=cursor.fetchone()[0] or 0
            result.append(DailyCharacterCount(date=current,count=count))
            current+=datetime.timedelta(days=1)

    return result


def get_all_time_statistics()->tuple[CharacterSummary,list[CharacterCount]]:
    """读取CharCounter全历史统计概况和字符排行。"""

    today=datetime.date.today()

    total_characters=0
    today_characters=0
    active_dates=set()
    counts:dict[str,int]={}

    with sqlite3.connect(f"file:{DB_PATH.resolve().as_posix()}?mode=ro",uri=True) as conn:
        cursor=conn.cursor()
        date_tables=get_date_tables(cursor)

        for table_date,tables in date_tables.items():
            active_dates.add(table_date)
            for table in tables:
                cursor.execute(f"SELECT c,n FROM `{table}`")
                for character,count in cursor.fetchall():
                    total_characters+=count
                    counts[character]=counts.get(character,0)+count
                    if table_date==today:
                        today_characters+=count

    ranking=sorted(counts.items(),key=lambda item:item[1],reverse=True)

    summary=CharacterSummary(
        total_characters=total_characters,
        today_characters=today_characters,
        active_days=len(active_dates),
    )
    characters=[
        CharacterCount(character=character,count=count)
        for character,count in ranking
    ]

    return summary,characters


router=APIRouter(
    prefix="/api/charcounter",
    tags=["CharCounter"],
)


@router.get(
    "/daily",
    response_model=DailyStatisticsResponse,
    summary="获取每日字符统计",
    description="返回指定日期范围内每天记录的字符数量。",
)
def get_daily_statistics(start:datetime.date|None=Query(default=None,description="开始日期，默认最近30天"),end:datetime.date|None=Query(default=None,description="结束日期，默认今天")):
    today=datetime.date.today()

    if end is None:
        end=today
    if start is None:
        start=end-datetime.timedelta(days=29)

    if start>end:
        raise HTTPException(status_code=400,detail="start不能晚于end")

    if (end-start).days>365:
        raise HTTPException(status_code=400,detail="最多查询366天")

    if not DB_PATH.exists():
        raise HTTPException(status_code=404,detail="字符统计数据源不存在")

    try:
        daily=get_daily_counts(start,end)
    except sqlite3.OperationalError:
        raise HTTPException(status_code=503,detail="统计数据库暂时无法读取")
    except sqlite3.DatabaseError:
        raise HTTPException(status_code=500,detail="字符统计数据库发生异常")

    return DailyStatisticsResponse(
        generated_at=datetime.datetime.now().astimezone(),
        period={"start":start,"end":end},
        daily=daily,
    )


@router.get(
    "/all-time",
    response_model=AllTimeStatisticsResponse,
    summary="获取全历史字符统计",
    description="返回CharCounter记录以来的统计概况和完整字符排行。",
)
def get_all_time_statistics_api():
    if not DB_PATH.exists():
        raise HTTPException(status_code=404,detail="字符统计数据源不存在")

    try:
        summary,characters=get_all_time_statistics()
    except sqlite3.OperationalError:
        raise HTTPException(status_code=503,detail="统计数据库暂时无法读取")
    except sqlite3.DatabaseError:
        raise HTTPException(status_code=500,detail="字符统计数据库发生异常")

    return AllTimeStatisticsResponse(
        generated_at=datetime.datetime.now().astimezone(),
        summary=summary,
        ranking_scope="all_time",
        characters=characters,
    )