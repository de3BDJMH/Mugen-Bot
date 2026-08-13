import datetime
from zoneinfo import ZoneInfo

from src.storage import watchice as storage

ADMIN_QQS={
    2404164262,
    2421372100
}

def is_admin(viewer_qq:int|None)->bool:
    """判断是否为看群友管理员"""

    return viewer_qq is not None and viewer_qq in ADMIN_QQS

def get_members(viewer_qq:int|None)->list[dict]:
    """获取当前用户可见的群友列表"""

    return storage.get_visible_members(
        viewer_qq,
        is_admin(viewer_qq)
    )

def get_images(
    slug:str,
    viewer_qq:int|None,
    page:int=1,
    page_size:int=10,
    sort:str="latest"
)->dict|None:
    """获取群友图片列表"""
    return storage.get_visible_images(
        slug,
        viewer_qq,
        is_admin(viewer_qq),
        page,
        page_size,
        sort
    )

def get_image_content(image_id:int,viewer_qq:int|None)->dict|None:
    """获取允许当前用户访问的图片文件信息"""

    admin=is_admin(viewer_qq)

    if not storage.can_view_image(image_id,viewer_qq,admin):
        return None

    image=storage.get_image(image_id)

    if image is None:
        return None

    path=storage.DATA_PATH/image["relative_path"]

    # 数据库有记录，但实际文件不存在
    if not path.is_file():
        return None

    return {
        "path":path,
        "mime_type":image["mime_type"]
    }

def add_comment(image_id:int,user_id:int,content:str)->dict|None:
    """发表评论"""

    if not storage.can_view_image(
        image_id,
        user_id,
        is_admin(user_id)
    ):
        return None

    content=content.strip()

    if not 1<=len(content)<=300:
        raise ValueError("invalid_content")

    created_at=datetime.datetime.now(ZoneInfo("Asia/Shanghai"))

    comment_id=storage.create_comment(
        image_id,
        user_id,
        content,
        created_at
    )

    return storage.get_comment(comment_id)

def get_comments(
    image_id:int,
    user_id:int|None,
    page:int=1,
    page_size:int=20
)->dict|None:
    """获取图片评论"""

    admin=is_admin(user_id)

    if not storage.can_view_image(image_id,user_id,admin):
        return None

    comments=storage.get_image_comments(
        image_id,
        page,
        page_size
    )

    total=storage.get_image_comment_count(image_id)

    for comment in comments:
        comment["can_delete"]=(
            admin or
            comment["user_id"]==user_id
        )

    return {
        "page":page,
        "page_size":page_size,
        "total":total,
        "items":comments
    }

def remove_comment(comment_id:int,user_id:int)->bool|None:
    """删除评论"""

    comment=storage.get_comment(comment_id)

    if comment is None:
        return None

    admin=is_admin(user_id)

    if not storage.can_view_image(
        comment["image_id"],
        user_id,
        admin
    ):
        return None

    if not admin and comment["user_id"]!=user_id:
        raise PermissionError("cannot_delete_comment")

    return storage.delete_comment(comment_id)

def set_rating(image_id:int,user_id:int,score:int)->dict|None:
    """设置图片评分"""

    if not storage.can_view_image(
        image_id,
        user_id,
        is_admin(user_id)
    ):
        return None

    if not 1<=score<=5:
        raise ValueError("invalid_score")

    rated_at=datetime.datetime.now(ZoneInfo("Asia/Shanghai"))

    storage.set_image_rating(
        image_id,
        user_id,
        score,
        rated_at
    )

    result=storage.get_image_rating_summary(image_id)
    result["viewer_score"]=score

    return result

def remove_rating(image_id:int,user_id:int)->dict|None:
    """取消图片评分"""

    if not storage.can_view_image(
        image_id,
        user_id,
        is_admin(user_id)
    ):
        return None

    storage.delete_image_rating(image_id,user_id)

    result=storage.get_image_rating_summary(image_id)
    result["viewer_score"]=None

    return result

def get_community(
    image_id:int,
    user_id:int|None,
    page:int=1,
    page_size:int=20
)->dict|None:
    """获取图片社区数据"""

    admin=is_admin(user_id)

    if not storage.can_view_image(image_id,user_id,admin):
        return None

    rating=storage.get_image_rating_summary(image_id)

    if user_id is None:
        rating["viewer_score"]=None
    else:
        rating["viewer_score"]=storage.get_user_rating(
            image_id,
            user_id
        )

    comments=get_comments(
        image_id,
        user_id,
        page,
        page_size
    )

    if comments is None:
        return None

    return {
        "rating":rating,
        "comments":comments
    }