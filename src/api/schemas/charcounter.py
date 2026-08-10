import datetime
from typing import Literal

from pydantic import BaseModel,Field


class PeriodInfo(BaseModel):
    start:datetime.date=Field(description="本次每日统计的开始日期")
    end:datetime.date=Field(description="本次每日统计的结束日期")


class CharacterSummary(BaseModel):
    total_characters:int=Field(description="CharCounter记录以来的总字符数")
    today_characters:int=Field(description="今日记录的字符数")
    active_days:int=Field(description="CharCounter记录以来存在统计数据的天数")


class DailyCharacterCount(BaseModel):
    date:datetime.date=Field(description="日期")
    count:int=Field(description="当天记录的字符数")


class CharacterCount(BaseModel):
    character:str=Field(description="字符原文，包括空格和换行等字符")
    count:int=Field(description="该字符累计出现次数")


class DailyStatisticsResponse(BaseModel):
    generated_at:datetime.datetime=Field(description="本次响应生成时间")
    period:PeriodInfo
    daily:list[DailyCharacterCount]


class AllTimeStatisticsResponse(BaseModel):
    generated_at:datetime.datetime=Field(description="本次响应生成时间")
    summary:CharacterSummary
    ranking_scope:Literal["all_time"]="all_time"
    characters:list[CharacterCount]