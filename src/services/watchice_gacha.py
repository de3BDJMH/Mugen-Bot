import random
import json
import pathlib
import datetime

from src.services import watchice
from src.storage import watchice_gacha as storage
from src.storage import checkin as checkin_storage
from src.libraries.checkin.data import Data,substract

CONFIG_PATH=pathlib.Path(__file__).resolve().parent.parent.parent/"data"/"watchice_gacha"/"gacha_config.json"

def get_config()->dict:
    """获取抽卡配置"""
    with open(CONFIG_PATH,"r",encoding="utf-8") as f:
        return json.load(f)
    
def draw_images(user_id:int,count:int)->list[int]:
    """从当前用户可见图片中随机抽取图片"""
    if count not in (1,10):
        raise ValueError("invalid_count")

    pool=watchice.get_all_visible_image_ids(user_id)

    if not pool:
        raise ValueError("empty_pool")

    return [random.choice(pool) for _ in range(count)]

def get_cost(config:dict,count:int)->dict:
    """获取抽卡价格"""
    if count==1:
        return config["single_cost"]
    if count==10:
        return config["ten_cost"]
    raise ValueError("invalid_count")

def draw(user_id:int,request_id:str,count:int)->dict:
    """执行一次抽卡"""
    if count not in (1,10):
        raise ValueError("invalid_count")

    conn=storage._connect()

    try:
        conn.execute(
            "ATTACH DATABASE ? AS checkin",
            (str(checkin_storage.DATA_PATH),)
        )

        conn.execute("BEGIN IMMEDIATE")

        old_draw=storage.get_draw_by_request_id_conn(conn,user_id,request_id)#请求id重复时候会读取旧记录
        if old_draw is not None:
            if old_draw["count"]!=count:
                raise ValueError("request_id_conflict")

            items=storage.get_draw_items_conn(conn,old_draw["draw_id"])
            conn.rollback()

            return {
                **old_draw,
                "items":items
            }

        config=get_config()
        if not config["enabled"]:
            raise ValueError("gacha_disabled")
    
        cost=get_cost(config,count)

        image_ids=draw_images(user_id,count)
        now=datetime.datetime.now().replace(microsecond=0)

        after=deduct_data(conn,user_id,cost,request_id,now)

        draw_id=storage.create_draw_conn(
            conn,
            user_id,
            request_id,
            count,
            cost["base"],
            cost["addition"],
            cost["zero"],
            now
        )

        items=[]

        for position,image_id in enumerate(image_ids,1):
            card=storage.add_user_card_conn(conn,user_id,image_id,now)

            items.append({
                "position":position,
                **card
            })

        storage.add_draw_items_conn(conn,draw_id,items)

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    return {
        "draw_id":draw_id,
        "count":count,
        "cost_base":cost["base"],
        "cost_addition":cost["addition"],
        "cost_zero":cost["zero"],
        "created_at":now,
        "items":items
    }

def deduct_data(conn,user_id:int,cost:dict,request_id:str,created_at:datetime.datetime)->Data:
    """扣除抽卡所需Data"""
    user_data=checkin_storage.get_user_data_conn(conn,user_id,"checkin")

    if user_data is None:
        raise ValueError("user_not_found")

    current=Data(
        [user_data["base"],user_data["addition"]],
        user_data["zero"]
    )
    cost_data=Data(
        [cost["base"],cost["addition"]],
        cost["zero"]
    )

    if current.getBytes()<cost_data.getBytes():
        raise ValueError("insufficient_data")

    after=substract(current,cost_data)

    checkin_storage.update_user_data_conn(
        conn,
        user_id,
        after.base,
        after.addition,
        after.is_zero,
        "checkin"
    )

    checkin_storage.add_log_conn(
        conn,
        user_id=user_id,
        operation="gacha",
        change_type="-",
        data_base=cost_data.base,
        data_addition=cost_data.addition,
        data_zero=cost_data.is_zero,
        created_at=created_at,
        detail=request_id,
        schema="checkin"
    )

    return after

def get_collection(user_id:int)->dict:
    """获取用户当前可见的收藏"""
    visible_images=watchice.get_all_visible_images_info(user_id)
    cards=storage.get_user_cards(user_id)
    owned_map={card["image_id"]:card for card in cards}

    items=[]

    for image in visible_images:
        card=owned_map.get(image["image_id"])

        items.append({
            **image,
            "owned":card is not None,
            "copies":card["owned_count"] if card else 0,
            "first_obtained_at":card["first_obtained_at"] if card else None
        })

    return {
        "owned_unique":sum(1 for item in items if item["owned"]),
        "total_collectible":len(items),
        "items":items
    }

def get_draw_history(user_id:int,page:int=1,page_size:int=20)->dict:
    """获取用户抽卡历史"""
    return storage.get_user_draw_history(user_id,page,page_size)
