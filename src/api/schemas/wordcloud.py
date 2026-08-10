import datetime

from pydantic import BaseModel,Field


class WordCloudPeriod(BaseModel):
    start:datetime.date=Field(description="快照开始日期")
    end:datetime.date=Field(description="快照结束日期")


class WordCloudDaySnapshot(BaseModel):
    groups:list[str]=Field(description="当天有有效词频数据的匿名群组")
    counts:dict[str,dict[str,int]]=Field(description="词语到匿名用户使用次数的映射")


class WordCloudSnapshotResponse(BaseModel):
    version:int=Field(description="词云快照格式版本")
    generated_at:datetime.datetime=Field(description="快照实际生成时间")
    period:WordCloudPeriod
    days:dict[str,WordCloudDaySnapshot]