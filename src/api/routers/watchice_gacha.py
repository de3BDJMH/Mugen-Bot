from fastapi import APIRouter,Header,HTTPException,Query

from src.api.schemas.watchice_gacha import *
from src.services import watchice_gacha as service


router=APIRouter(prefix="/api/watchice/gacha",tags=["watchice-gacha"])

def _parse_viewer_qq(value:str|None)->int|None:
    """解析Web传入的QQ号"""
    if value is None or not value.isdigit():
        return None
    return int(value)

@router.get("/config",response_model=GachaConfigResponse)
def get_config():
    """获取抽卡配置"""
    return service.get_config()

@router.post("/draw",response_model=GachaDrawResponse)
def draw(
    body:GachaDrawRequest,
    x_mugen_viewer_qq:str|None=Header(default=None,alias="X-Mugen-Viewer-QQ")
):
    """执行抽卡"""
    user_id=_parse_viewer_qq(x_mugen_viewer_qq)

    if user_id is None:
        raise HTTPException(status_code=401,detail="Login required")

    try:
        return service.draw(user_id,body.request_id,body.count)
    except ValueError as e:
        error=str(e)

        if error=="invalid_count":
            raise HTTPException(status_code=400,detail="Invalid draw count")
        if error=="gacha_disabled":
            raise HTTPException(status_code=503,detail="Gacha disabled")
        if error=="empty_pool":
            raise HTTPException(status_code=404,detail="No collectible images")
        if error=="insufficient_data":
            raise HTTPException(status_code=409,detail="Insufficient Data")
        if error=="request_id_conflict":
            raise HTTPException(status_code=409,detail="Request ID conflict")
        if error=="user_not_found":
            raise HTTPException(status_code=404,detail="User not found")

        raise

@router.get("/collection",response_model=GachaCollectionResponse)
def get_collection(
    x_mugen_viewer_qq:str|None=Header(default=None,alias="X-Mugen-Viewer-QQ")
):
    """获取当前用户收藏"""
    user_id=_parse_viewer_qq(x_mugen_viewer_qq)

    if user_id is None:
        raise HTTPException(status_code=401,detail="Login required")

    return service.get_collection(user_id)

@router.get("/history",response_model=GachaHistoryResponse)
def get_history(
    page:int=Query(default=1,ge=1),
    page_size:int=Query(default=20,ge=1,le=50),
    x_mugen_viewer_qq:str|None=Header(default=None,alias="X-Mugen-Viewer-QQ")
):
    """获取当前用户抽卡历史"""
    user_id=_parse_viewer_qq(x_mugen_viewer_qq)

    if user_id is None:
        raise HTTPException(status_code=401,detail="Login required")

    return service.get_draw_history(user_id,page,page_size)