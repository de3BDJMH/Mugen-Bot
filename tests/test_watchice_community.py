import sqlite3
from datetime import datetime,timedelta
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routers.watchice import router

app=FastAPI()
app.include_router(router,prefix="")
for route in app.routes:
    print(route.path)

client=TestClient(app)

import pytest

from src.storage import watchice as storage
from src.services import watchice as service


@pytest.fixture
def community_db(tmp_path,monkeypatch):
    db_path=tmp_path/"watchice.db"
    monkeypatch.setattr(storage,"DB_PATH",db_path)

    conn=sqlite3.connect(db_path)
    cursor=conn.cursor()

    # community表有外键，先造一张最小images表
    cursor.execute("""
        CREATE TABLE images(
            image_id INTEGER PRIMARY KEY
        )
    """)

    cursor.execute("""
        INSERT INTO images(image_id)
        VALUES(1)
    """)

    conn.commit()
    conn.close()

    storage.init_community_tables()

    return db_path

def test_update_rating(community_db):
    now=datetime.now()

    storage.set_image_rating(1,10001,5,now)
    storage.set_image_rating(1,10001,3,now)

    score=storage.get_user_rating(1,10001)
    summary=storage.get_image_rating_summary(1)

    assert score==3
    assert summary["count"]==1
    assert summary["average"]==3
    assert summary["distribution"]["3"]==1
    assert summary["distribution"]["5"]==0

def test_delete_rating(community_db):
    now=datetime.now()

    storage.set_image_rating(1,10001,5,now)

    assert storage.delete_image_rating(1,10001) is True
    assert storage.get_user_rating(1,10001) is None

    summary=storage.get_image_rating_summary(1)

    assert summary["count"]==0
    assert summary["average"] is None

def test_delete_comment(community_db):
    now=datetime.now()

    comment_id=storage.create_comment(
        1,
        10001,
        "测试评论",
        now
    )

    comment=storage.get_comment(comment_id)

    assert comment is not None
    assert comment["content"]=="测试评论"

    assert storage.delete_comment(comment_id) is True

    # deleted评论不能再被get_comment查到
    assert storage.get_comment(comment_id) is None

def test_delete_comment_twice(community_db):
    now=datetime.now()

    comment_id=storage.create_comment(
        1,
        10001,
        "测试评论",
        now
    )

    assert storage.delete_comment(comment_id) is True
    assert storage.delete_comment(comment_id) is False

def test_cannot_delete_others_comment(monkeypatch):
    monkeypatch.setattr(
        storage,
        "get_comment",
        lambda comment_id:{
            "id":comment_id,
            "image_id":1,
            "user_id":10001,
            "content":"测试",
            "status":"visible"
        }
    )

    monkeypatch.setattr(
        storage,
        "can_view_image",
        lambda image_id,user_id,admin:True
    )

    monkeypatch.setattr(
        service,
        "is_admin",
        lambda user_id:False
    )

    with pytest.raises(PermissionError):
        service.remove_comment(
            comment_id=1,
            user_id=20002
        )

def test_owner_can_delete_comment(monkeypatch):
    monkeypatch.setattr(
        storage,
        "get_comment",
        lambda comment_id:{
            "id":comment_id,
            "image_id":1,
            "user_id":10001,
            "content":"测试",
            "status":"visible"
        }
    )

    monkeypatch.setattr(
        storage,
        "can_view_image",
        lambda image_id,user_id,admin:True
    )

    monkeypatch.setattr(
        service,
        "is_admin",
        lambda user_id:False
    )

    monkeypatch.setattr(
        storage,
        "delete_comment",
        lambda comment_id:True
    )

    result=service.remove_comment(
        comment_id=1,
        user_id=10001
    )

    assert result is True

def test_admin_can_delete_comment(monkeypatch):
    monkeypatch.setattr(
        storage,
        "get_comment",
        lambda comment_id:{
            "id":comment_id,
            "image_id":1,
            "user_id":10001,
            "content":"测试",
            "status":"visible"
        }
    )

    monkeypatch.setattr(
        storage,
        "can_view_image",
        lambda image_id,user_id,admin:True
    )

    monkeypatch.setattr(
        service,
        "is_admin",
        lambda user_id:True
    )

    monkeypatch.setattr(
        storage,
        "delete_comment",
        lambda comment_id:True
    )

    result=service.remove_comment(
        comment_id=1,
        user_id=20002
    )

    assert result is True

def test_hidden_image_has_no_community(monkeypatch):
    monkeypatch.setattr(
        storage,
        "can_view_image",
        lambda image_id,user_id,admin:False
    )

    monkeypatch.setattr(
        service,
        "is_admin",
        lambda user_id:False
    )

    result=service.get_community(
        image_id=1,
        user_id=10001
    )

    assert result is None

@pytest.mark.parametrize(
    "content",
    [
        "",
        "   ",
        "a"*301
    ]
)
def test_invalid_comment_content(monkeypatch,content):
    monkeypatch.setattr(
        storage,
        "can_view_image",
        lambda image_id,user_id,admin:True
    )

    monkeypatch.setattr(
        service,
        "is_admin",
        lambda user_id:False
    )

    with pytest.raises(ValueError):
        service.add_comment(
            image_id=1,
            user_id=10001,
            content=content
        )

@pytest.mark.parametrize("score",[0,6,-1,100])
def test_invalid_rating(monkeypatch,score):
    monkeypatch.setattr(
        storage,
        "can_view_image",
        lambda image_id,user_id,admin:True
    )

    monkeypatch.setattr(
        service,
        "is_admin",
        lambda user_id:False
    )

    with pytest.raises(ValueError):
        service.set_rating(
            image_id=1,
            user_id=10001,
            score=score
        )

def test_comment_pagination(community_db):
    start=datetime.now()

    for i in range(25):
        storage.create_comment(
            1,
            10001,
            f"评论{i}",
            start+timedelta(seconds=i)
        )

    page1=storage.get_image_comments(
        1,
        page=1,
        page_size=20
    )

    page2=storage.get_image_comments(
        1,
        page=2,
        page_size=20
    )

    total=storage.get_image_comment_count(1)

    assert total==25
    assert len(page1)==20
    assert len(page2)==5
    assert page1[0]["content"]=="评论24"
    assert page1[-1]["content"]=="评论5"

    assert page2[0]["content"]=="评论4"
    assert page2[-1]["content"]=="评论0"

def test_rating_requires_login():
    response=client.put(
        "/api/watchice/images/1/rating",
        json={"score":5}
    )

    assert response.status_code==401

def test_comment_requires_login():
    response=client.post(
        "/api/watchice/images/1/comments",
        json={"content":"测试"}
    )

    assert response.status_code==401

def test_invalid_rating_schema():
    response=client.put(
        "/api/watchice/images/1/rating",
        headers={
            "X-Mugen-Viewer-QQ":"10001"
        },
        json={"score":6}
    )

    assert response.status_code==422

def test_delete_others_comment_returns_403(monkeypatch):
    monkeypatch.setattr(
        service,
        "remove_comment",
        lambda comment_id,user_id:(
            (_ for _ in ()).throw(PermissionError())
        )
    )

    response=client.delete(
        "/api/watchice/comments/1",
        headers={
            "X-Internal-API-Key":"...",
            "X-Mugen-Viewer-QQ":"10002"
        }
    )

    assert response.status_code==403

def test_hidden_image_returns_404(monkeypatch):
    monkeypatch.setattr(
        service,
        "get_community",
        lambda *args,**kwargs:None
    )

    response=client.get(
        "/api/watchice/images/1/community",
        headers={
            "X-Internal-API-Key":"..."
        }
    )

    assert response.status_code==404