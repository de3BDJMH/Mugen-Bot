import sqlite3
import datetime
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routers.watchice_gacha import router

app=FastAPI()
app.include_router(router)
client=TestClient(app)

import pytest

from src.storage import watchice_gacha as gacha_storage
from src.storage import checkin as checkin_storage
from src.services import watchice_gacha as gacha_service


@pytest.fixture
def gacha_db(tmp_path,monkeypatch):
    gacha_path=tmp_path/"gacha.db"
    checkin_path=tmp_path/"checkin.db"

    monkeypatch.setattr(gacha_storage,"DB_PATH",gacha_path)
    monkeypatch.setattr(checkin_storage,"DATA_PATH",checkin_path)

    gacha_storage.init_database()
    checkin_storage.init_database()

    checkin_storage.create_user(123,"test")

    conn=sqlite3.connect(checkin_path)
    conn.execute(
        """
        UPDATE users
        SET data_base=?,data_addition=?,data_zero=?
        WHERE user_id=?
        """,
        (30,0,False,123)
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(
        gacha_service,
        "get_config",
        lambda:{
            "enabled":True,
            "single_cost":{"base":10,"addition":8,"zero":False},
            "ten_cost":{"base":20,"addition":1,"zero":False}
        }
    )

    monkeypatch.setattr(
        gacha_service,
        "draw_images",
        lambda user_id,count:list(range(101,101+count))
    )

    return gacha_path,checkin_path

def test_draw_rollback(gacha_db,monkeypatch):
    original=gacha_storage.add_draw_items_conn

    def broken_add_draw_items(conn,draw_id,items):
        original(conn,draw_id,items)
        raise RuntimeError("rollback_test")

    monkeypatch.setattr(
        gacha_storage,
        "add_draw_items_conn",
        broken_add_draw_items
    )

    before=checkin_storage.get_user(123)

    with pytest.raises(RuntimeError,match="rollback_test"):
        gacha_service.draw(123,"rollback-test",10)

    after=checkin_storage.get_user(123)

    assert after["data_base"]==before["data_base"]
    assert after["data_addition"]==before["data_addition"]
    assert after["data_zero"]==before["data_zero"]
    conn=gacha_storage._connect()

    assert conn.execute(
        "SELECT COUNT(*) FROM gacha_draws"
    ).fetchone()[0]==0

    assert conn.execute(
        "SELECT COUNT(*) FROM gacha_draw_items"
    ).fetchone()[0]==0

    assert conn.execute(
        "SELECT COUNT(*) FROM user_cards"
    ).fetchone()[0]==0

    conn.close()
    conn=sqlite3.connect(checkin_storage.DATA_PATH)

    assert conn.execute(
        """
        SELECT COUNT(*)
        FROM logs
        WHERE operation='gacha'
        """
    ).fetchone()[0]==0

    conn.close()

def test_multi_database_transaction_mode(gacha_db):
    conn=gacha_storage._connect()

    conn.execute(
        "ATTACH DATABASE ? AS checkin",
        (str(checkin_storage.DATA_PATH),)
    )

    main_mode=conn.execute(
        "PRAGMA main.journal_mode"
    ).fetchone()[0]

    checkin_mode=conn.execute(
        "PRAGMA checkin.journal_mode"
    ).fetchone()[0]

    main_sync=conn.execute(
        "PRAGMA main.synchronous"
    ).fetchone()[0]

    checkin_sync=conn.execute(
        "PRAGMA checkin.synchronous"
    ).fetchone()[0]

    conn.close()

    assert main_mode.lower() not in ("wal","off","memory")
    assert checkin_mode.lower() not in ("wal","off","memory")
    assert main_sync!=0
    assert checkin_sync!=0

def test_draw_api(gacha_db):
    headers={"X-Mugen-Viewer-QQ":"123"}

    response=client.post(
        "/api/watchice/gacha/draw",
        headers=headers,
        json={
            "request_id":"api-test",
            "count":1
        }
    )

    assert response.status_code==200

    data=response.json()

    assert data["count"]==1
    assert len(data["items"])==1
    assert data["items"][0]["image_id"]==101

    response2=client.post(
        "/api/watchice/gacha/draw",
        headers=headers,
        json={
            "request_id":"api-test",
            "count":1
        }
    )

    assert response2.status_code==200
    assert response2.json()==data

def test_draw_api_requires_login(gacha_db):
    response=client.post(
        "/api/watchice/gacha/draw",
        json={
            "request_id":"test",
            "count":1
        }
    )

    assert response.status_code==401

def test_draw_api_invalid_count(gacha_db):
    response=client.post(
        "/api/watchice/gacha/draw",
        headers={"X-Mugen-Viewer-QQ":"123"},
        json={
            "request_id":"test",
            "count":2
        }
    )

    assert response.status_code==400

def test_draw_api_request_id_conflict(gacha_db):
    headers={"X-Mugen-Viewer-QQ":"123"}

    response=client.post(
        "/api/watchice/gacha/draw",
        headers=headers,
        json={
            "request_id":"same-request",
            "count":1
        }
    )

    assert response.status_code==200

    response=client.post(
        "/api/watchice/gacha/draw",
        headers=headers,
        json={
            "request_id":"same-request",
            "count":10
        }
    )

    assert response.status_code==409

def test_config_api(gacha_db):
    response=client.get("/api/watchice/gacha/config")
    assert response.status_code==200
    assert response.json()["enabled"] is True

def test_collection_api(gacha_db):
    headers={"X-Mugen-Viewer-QQ":"123"}

    client.post(
        "/api/watchice/gacha/draw",
        headers=headers,
        json={"request_id":"collection-test","count":1}
    )

    response=client.get(
        "/api/watchice/gacha/collection",
        headers=headers
    )

    assert response.status_code==200
    data=response.json()
    assert data["owned_unique"]>=1
    assert any(item["image_id"]==101 and item["owned"] for item in data["items"])

def test_history_api(gacha_db):
    headers={"X-Mugen-Viewer-QQ":"123"}

    client.post(
        "/api/watchice/gacha/draw",
        headers=headers,
        json={"request_id":"history-test","count":1}
    )

    response=client.get(
        "/api/watchice/gacha/history",
        headers=headers
    )

    assert response.status_code==200
    data=response.json()
    assert data["total"]==1
    assert data["items"][0]["request_id"]=="history-test"
    assert len(data["items"][0]["items"])==1

def test_collection_visibility(gacha_db,monkeypatch):
    conn=gacha_storage._connect()
    now=datetime.datetime.now().replace(microsecond=0)

    gacha_storage.add_user_card_conn(conn,123,101,now)
    conn.commit()
    conn.close()

    monkeypatch.setattr(
        gacha_service.watchice,
        "get_all_visible_images_info",
        lambda user_id:[]
    )

    collection=gacha_service.get_collection(123)

    assert collection["owned_unique"]==0
    assert collection["total_collectible"]==0
    assert collection["items"]==[]

    card=gacha_storage.get_user_card(123,101)
    assert card is not None
    assert card["owned_count"]==1
    monkeypatch.setattr(
        gacha_service.watchice,
        "get_all_visible_images_info",
        lambda user_id:[{
            "image_id":101,
            "member_slug":"test",
            "mime_type":"image/jpeg",
            "width":100,
            "height":100,
            "is_animated":False,
            "uploaded_at":None
        }]
    )

    collection=gacha_service.get_collection(123)

    assert collection["owned_unique"]==1
    assert collection["items"][0]["owned"] is True
    assert collection["items"][0]["copies"]==1

def test_ten_draw_duplicate_copies(gacha_db,monkeypatch):
    monkeypatch.setattr(
        gacha_service,
        "draw_images",
        lambda user_id,count:[101,101,102,103,104,105,106,107,108,109]
    )

    result=gacha_service.draw(123,"duplicate-test",10)

    assert len(result["items"])==10

    assert result["items"][0]=={
        "position":1,
        "image_id":101,
        "is_new":True,
        "copies_after":1
    }

    assert result["items"][1]=={
        "position":2,
        "image_id":101,
        "is_new":False,
        "copies_after":2
    }

    card=gacha_storage.get_user_card(123,101)

    assert card["owned_count"]==2

def test_insufficient_data_no_write(gacha_db):
    conn=sqlite3.connect(checkin_storage.DATA_PATH)
    conn.execute(
        """
        UPDATE users
        SET data_base=?,data_addition=?,data_zero=?
        WHERE user_id=?
        """,
        (0,0,False,123)
    )
    conn.commit()
    conn.close()

    with pytest.raises(ValueError,match="insufficient_data"):
        gacha_service.draw(123,"insufficient-test",1)

    conn=gacha_storage._connect()
    assert conn.execute("SELECT COUNT(*) FROM gacha_draws").fetchone()[0]==0
    assert conn.execute("SELECT COUNT(*) FROM gacha_draw_items").fetchone()[0]==0
    assert conn.execute("SELECT COUNT(*) FROM user_cards").fetchone()[0]==0
    conn.close()

    conn=sqlite3.connect(checkin_storage.DATA_PATH)
    assert conn.execute(
        "SELECT COUNT(*) FROM logs WHERE operation='gacha'"
    ).fetchone()[0]==0
    conn.close()

def test_empty_pool_no_write(gacha_db,monkeypatch):
    monkeypatch.setattr(
        gacha_service,
        "draw_images",
        lambda user_id,count:(_ for _ in ()).throw(ValueError("empty_pool"))
    )

    before=checkin_storage.get_user(123)

    with pytest.raises(ValueError,match="empty_pool"):
        gacha_service.draw(123,"empty-pool-test",1)

    after=checkin_storage.get_user(123)

    assert after["data_base"]==before["data_base"]
    assert after["data_addition"]==before["data_addition"]
    assert after["data_zero"]==before["data_zero"]

    conn=gacha_storage._connect()
    assert conn.execute("SELECT COUNT(*) FROM gacha_draws").fetchone()[0]==0
    assert conn.execute("SELECT COUNT(*) FROM gacha_draw_items").fetchone()[0]==0
    assert conn.execute("SELECT COUNT(*) FROM user_cards").fetchone()[0]==0
    conn.close()

    conn=sqlite3.connect(checkin_storage.DATA_PATH)
    assert conn.execute(
        "SELECT COUNT(*) FROM logs WHERE operation='gacha'"
    ).fetchone()[0]==0
    conn.close()