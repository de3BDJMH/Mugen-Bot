from fastapi import APIRouter,HTTPException

from ...services.wordcloud import get_snapshot,snapshot_payload
from ..schemas.wordcloud import WordCloudSnapshotResponse


router=APIRouter(
    prefix="/api/wordcloud",
    tags=["WordCloud"],
)


@router.get(
    "/snapshot",
    response_model=WordCloudSnapshotResponse,
    summary="获取词云快照",
    description="返回最近30天的匿名词频快照。",
)
def get_wordcloud_snapshot():
    snapshot=get_snapshot()

    if snapshot is None:
        raise HTTPException(
            status_code=503,
            detail="词云快照正在生成，请稍后重试",
        )

    return snapshot_payload(snapshot)