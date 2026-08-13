from fastapi import APIRouter,Header,HTTPException,Query
from fastapi.responses import FileResponse

from typing import Literal

from src.api.schemas.watchice import *
from src.services import watchice as service


router=APIRouter(prefix="/api/watchice",tags=["watchice"])

def _parse_viewer_qq(value:str|None)->int|None:
    """解析Web传入的QQ号"""

    if value is None or not value.isdigit():
        return None

    return int(value)


@router.get("/members",response_model=list[WatchiceMember])
def get_members(x_mugen_viewer_qq:str|None=Header(default=None)):
    """获取当前用户可见的群友列表"""

    viewer_qq=None

    if x_mugen_viewer_qq and x_mugen_viewer_qq.isdigit():
        viewer_qq=int(x_mugen_viewer_qq)

    return service.get_members(viewer_qq)

@router.get("/members/{slug}/images",response_model=WatchiceImageList)
def get_member_images(
    slug:str,
    page:int=Query(1,ge=1),
    page_size:int=Query(10,ge=1,le=50),
    sort:Literal["latest","oldest"]="latest",
    x_mugen_viewer_qq:str|None=Header(default=None)
):
    """获取指定群友的图片列表"""

    viewer_qq=None

    if x_mugen_viewer_qq and x_mugen_viewer_qq.isdigit():
        viewer_qq=int(x_mugen_viewer_qq)

    result=service.get_images(
        slug,
        viewer_qq,
        page,
        page_size,
        sort
    )

    # 不存在和无权访问统一返回404
    if result is None:
        raise HTTPException(status_code=404,detail="Member not found")

    return result

@router.get("/images/{image_id}/content")
def get_image_content(
    image_id:int,
    x_mugen_viewer_qq:str|None=Header(default=None)
):
    """获取图片内容"""

    viewer_qq=None

    if x_mugen_viewer_qq and x_mugen_viewer_qq.isdigit():
        viewer_qq=int(x_mugen_viewer_qq)

    result=service.get_image_content(image_id,viewer_qq)

    # 图片不存在和无权访问统一404
    if result is None:
        raise HTTPException(status_code=404,detail="Image not found")

    return FileResponse(
        result["path"],
        media_type=result["mime_type"]
    )

@router.post(
    "/images/{image_id}/comments",
    response_model=WatchiceComment,
    summary="发表评论"
)
def create_comment(
    image_id:int,
    body:CommentCreateRequest,
    x_mugen_viewer_qq:str|None=Header(default=None)
):
    viewer_qq=_parse_viewer_qq(x_mugen_viewer_qq)

    if viewer_qq is None:
        raise HTTPException(
            status_code=401,
            detail="Login required"
        )

    try:
        comment=service.add_comment(
            image_id,
            viewer_qq,
            body.content
        )
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid comment content"
        )

    if comment is None:
        raise HTTPException(
            status_code=404,
            detail="Image not found"
        )

    comment["can_delete"]=True
    return comment

@router.delete(
    "/comments/{comment_id}",
    summary="删除评论"
)
def delete_comment(
    comment_id:int,
    x_mugen_viewer_qq:str|None=Header(default=None)
):
    viewer_qq=_parse_viewer_qq(x_mugen_viewer_qq)

    if viewer_qq is None:
        raise HTTPException(
            status_code=401,
            detail="Login required"
        )

    try:
        result=service.remove_comment(
            comment_id,
            viewer_qq
        )
    except PermissionError:
        raise HTTPException(
            status_code=403,
            detail="Cannot delete this comment"
        )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Comment not found"
        )

    return {
        "success":True
    }

@router.get(
    "/images/{image_id}/community",
    response_model=CommunityResponse,
    summary="获取图片社区数据"
)
def get_community(
    image_id:int,
    page:int=Query(default=1,ge=1),
    page_size:int=Query(default=20,ge=1,le=50),
    x_mugen_viewer_qq:str|None=Header(
        default=None,
        alias="X-Mugen-Viewer-QQ"
    )
):
    viewer_qq=_parse_viewer_qq(x_mugen_viewer_qq)

    data=service.get_community(
        image_id,
        viewer_qq,
        page,
        page_size
    )

    if data is None:
        raise HTTPException(
            status_code=404,
            detail="Image not found"
        )

    return data

@router.put(
    "/images/{image_id}/rating",
    response_model=RatingSummary,
    summary="设置图片评分"
)
def set_rating(
    image_id:int,
    body:RatingRequest,
    x_mugen_viewer_qq:str|None=Header(
        default=None,
        alias="X-Mugen-Viewer-QQ"
    )
):
    viewer_qq=_parse_viewer_qq(x_mugen_viewer_qq)

    if viewer_qq is None:
        raise HTTPException(
            status_code=401,
            detail="Login required"
        )

    try:
        result=service.set_rating(
            image_id,
            viewer_qq,
            body.score
        )
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid score"
        )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Image not found"
        )

    return result

@router.delete(
    "/images/{image_id}/rating",
    response_model=RatingSummary,
    summary="取消图片评分"
)
def delete_rating(
    image_id:int,
    x_mugen_viewer_qq:str|None=Header(
        default=None,
        alias="X-Mugen-Viewer-QQ"
    )
):
    viewer_qq=_parse_viewer_qq(x_mugen_viewer_qq)

    if viewer_qq is None:
        raise HTTPException(
            status_code=401,
            detail="Login required"
        )

    result=service.remove_rating(
        image_id,
        viewer_qq
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Image not found"
        )

    return result