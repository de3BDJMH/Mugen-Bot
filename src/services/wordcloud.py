import datetime
import hashlib
import hmac
import re
import sqlite3
import os
import gzip
import json
import threading

from pathlib import Path
from dotenv import load_dotenv
from collections import Counter,defaultdict
from dataclasses import dataclass

from ..libraries.tools import ROOT_PATH

PROJECT_ROOT=Path(__file__).resolve().parents[2]
USER_DATABASE_PATH=ROOT_PATH/"data"/"wordcloud"/"database"/"user"
SNAPSHOT_CACHE_VERSION=1
SNAPSHOT_CACHE_PATH=ROOT_PATH/"data"/"wordcloud"/"cache"/"snapshot.json.gz"

def get_anon_key()->str:
    """读取词云匿名化密钥。"""

    load_dotenv(PROJECT_ROOT/".env.api",override=False)

    secret=os.getenv("MUGEN_WORDCLOUD_ANON_KEY","").strip()

    if not secret:
        raise RuntimeError("MUGEN_WORDCLOUD_ANON_KEY未配置")

    return secret

@dataclass(frozen=True)
class WordCloudSnapshot:
    generated_at:datetime.datetime
    period_start:datetime.date
    period_end:datetime.date
    daily_counts:dict[datetime.date,dict[str,Counter[str]]]
    daily_groups:dict[datetime.date,set[str]]

_snapshot_cache:WordCloudSnapshot|None=None
_cache_lock=threading.Lock()
_refresh_thread:threading.Thread|None=None

DATE_TABLE=re.compile(r"^\d{4}_\d{1,2}_\d{1,2}$")
CJK_CHARACTER=re.compile(r"[\u4e00-\u9fff]")

BOT_ACCOUNT_RANGES=(#官方机器人qq账号范围
    (3328144510,3328144510),
    (2854196301,2854216399),
    (66600000,66600000),
    (3889000000,3889999999),
    (4010000000,4019999999),
)

STOPWORDS=frozenset({#ban词
    "这个","那个","什么","怎么","可以","可能","没有","我们","你们","他们","她们",
    "就是","然后","因为","所以","如果","但是","不是","真的","感觉","知道","觉得",
    "现在","今天","昨天","时候","一个","已经","还是","东西","这样","那么","为什么",
    "一些","这种","而且","还有","其实","应该","不会","不能","不要","的话","自己",
    "直接","不过","比较","非常","特别","有点","对了","好了","谢谢","哈哈","呜呜",
    "好的","一下","一下子","不是吧","没事","没关系","出来","进去","这里","那里",
})


def is_bot_account(account:int)->bool:
    """判断账号是否属于机器人"""
    return any(start<=account<=end for start,end in BOT_ACCOUNT_RANGES)


def is_displayable_word(word:str)->bool:
    """过滤不适合进入词云基础快照的词语"""

    normalized=word.strip()

    if len(normalized)<2 or len(normalized)>18:
        return False
    if normalized in STOPWORDS:
        return False
    if normalized.isnumeric() or normalized.lower().startswith(("http","www")):
        return False

    return any(character.isalnum() or CJK_CHARACTER.fullmatch(character) for character in normalized)


def parse_date_table(table:str)->datetime.date|None:
    """将合法日期表名转换为日期"""

    if not DATE_TABLE.fullmatch(table):
        return None

    try:
        return datetime.datetime.strptime(table,"%Y_%m_%d").date()
    except ValueError:
        return None


def anonymous_key(type_:str,id_:str,secret:str)->str:
    """将QQ号或群号转换为稳定且不可直接反推的匿名标识"""

    digest=hmac.new(
        secret.encode("utf-8"),
        f"{type_}:{id_}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:16]

    prefix="u" if type_=="user" else "g"

    return f"{prefix}_{digest}"


secret=get_anon_key()
def read_snapshot(period_start:datetime.date,period_end:datetime.date)->WordCloudSnapshot:
    """读取用户词频数据库并生成匿名词云快照。"""

    daily_counts=defaultdict(lambda:defaultdict(Counter))
    daily_groups=defaultdict(set)

    for database_path in USER_DATABASE_PATH.glob("*/*.db"):
        try:
            user_id=int(database_path.stem)
            group_id=database_path.parent.name
        except ValueError:
            continue
        if is_bot_account(user_id):
            continue

        user_key=anonymous_key("user",str(user_id),secret)
        group_key=anonymous_key("group",group_id,secret)

        database_uri=f"{database_path.resolve().as_uri()}?mode=ro"
        with sqlite3.connect(database_uri,uri=True,timeout=2) as conn:
            conn.execute("PRAGMA busy_timeout=2000")

            cursor=conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")

            for (table,) in cursor.fetchall():
                table_date=parse_date_table(table)
                if table_date is None or not period_start<=table_date<=period_end:
                    continue
                has_word=False
                for word,count in conn.execute(f'SELECT word,n FROM "{table}"'):
                    normalized=str(word).strip()
                    if not is_displayable_word(normalized):
                        continue
                    daily_counts[table_date][normalized][user_key]+=int(count)
                    has_word=True
                if has_word:
                    daily_groups[table_date].add(group_key)

    return WordCloudSnapshot(
        generated_at=datetime.datetime.now().astimezone(),
        period_start=period_start,
        period_end=period_end,
        daily_counts=dict(daily_counts),
        daily_groups=dict(daily_groups),
    )

def snapshot_payload(snapshot:WordCloudSnapshot)->dict[str,object]:
    """将词云快照转换为可序列化的JSON结构。"""

    days={}
    for current_day in sorted(set(snapshot.daily_counts)|set(snapshot.daily_groups)):
        days[current_day.isoformat()]={
            "groups":sorted(snapshot.daily_groups.get(current_day,set())),
            "counts":{
                word:dict(per_user)
                for word,per_user in snapshot.daily_counts.get(current_day,{}).items()
            },
        }

    return {
        "version":SNAPSHOT_CACHE_VERSION,
        "generated_at":snapshot.generated_at.isoformat(),
        "period":{
            "start":snapshot.period_start.isoformat(),
            "end":snapshot.period_end.isoformat(),
        },
        "days":days,
    }

def write_snapshot_file(snapshot:WordCloudSnapshot)->None:
    """将词云快照压缩保存到磁盘。"""

    SNAPSHOT_CACHE_PATH.parent.mkdir(parents=True,exist_ok=True)
    temporary_path=SNAPSHOT_CACHE_PATH.with_name(f"{SNAPSHOT_CACHE_PATH.name}.tmp")#保证数据能完整写完，防止中断，写完再替换.gz

    try:
        with gzip.open(temporary_path,"wt",encoding="utf-8",compresslevel=5) as file:
            json.dump(
                snapshot_payload(snapshot),
                file,
                ensure_ascii=False,
                separators=(",",":"),
            )

        temporary_path.replace(SNAPSHOT_CACHE_PATH)
    finally:
        temporary_path.unlink(missing_ok=True)

def snapshot_from_payload(payload:object)->WordCloudSnapshot|None:
    """将JSON数据恢复为词云快照。"""

    if not isinstance(payload,dict) or payload.get("version")!=SNAPSHOT_CACHE_VERSION:
        return None

    period=payload.get("period")
    days=payload.get("days")
    if not isinstance(period,dict) or not isinstance(days,dict):
        return None

    daily_counts={}
    daily_groups={}
    try:
        for day_text,day_data in days.items():
            if not isinstance(day_text,str) or not isinstance(day_data,dict):
                return None
            current_day=datetime.date.fromisoformat(day_text)
            raw_counts=day_data.get("counts",{})
            raw_groups=day_data.get("groups",[])
            if not isinstance(raw_counts,dict) or not isinstance(raw_groups,list):
                return None
            daily_counts[current_day]={
                str(word):Counter({str(user):int(count) for user,count in per_user.items()})
                for word,per_user in raw_counts.items()
                if isinstance(per_user,dict)
            }
            daily_groups[current_day]={str(group) for group in raw_groups}

        return WordCloudSnapshot(
            generated_at=datetime.datetime.fromisoformat(str(payload["generated_at"])),
            period_start=datetime.date.fromisoformat(str(period["start"])),
            period_end=datetime.date.fromisoformat(str(period["end"])),
            daily_counts=daily_counts,
            daily_groups=daily_groups,
        )
    except (ValueError,TypeError,KeyError):
        return None

def load_snapshot_file()->WordCloudSnapshot|None:
    """读取磁盘中的词云快照缓存。"""

    if not SNAPSHOT_CACHE_PATH.is_file():
        return None

    try:
        with gzip.open(SNAPSHOT_CACHE_PATH,"rt",encoding="utf-8") as file:
            return snapshot_from_payload(json.load(file))
    except (OSError,ValueError,TypeError,json.JSONDecodeError):
        return None

def snapshot_is_fresh(snapshot:WordCloudSnapshot)->bool:
    """判断快照是否为今天生成的完整30天快照。"""

    today=datetime.date.today()
    start=today-datetime.timedelta(days=29)

    return snapshot.period_start==start and snapshot.period_end==today and snapshot.generated_at.date()==today


def install_snapshot(snapshot:WordCloudSnapshot)->None:
    """将快照安装到内存缓存。"""

    global _snapshot_cache
    with _cache_lock:
        _snapshot_cache=snapshot


def refresh_snapshot_worker()->None:
    """在后台重新生成词云快照。"""

    global _refresh_thread

    try:
        end=datetime.date.today()
        start=end-datetime.timedelta(days=29)

        snapshot=read_snapshot(start,end)
        install_snapshot(snapshot)
        try:
            write_snapshot_file(snapshot)
        except OSError:
            pass

    except (sqlite3.Error,OSError,RuntimeError):
        pass
    finally:
        with _cache_lock:
            _refresh_thread=None


def schedule_snapshot_refresh()->None:
    """启动后台快照刷新，同一时间只允许一个刷新任务。"""

    global _refresh_thread

    with _cache_lock:
        if _refresh_thread is not None and _refresh_thread.is_alive():
            return

        _refresh_thread=threading.Thread(
            target=refresh_snapshot_worker,
            name="wordcloud-snapshot-refresh",
            daemon=True,
        )
        thread=_refresh_thread

    thread.start()


def prepare_snapshot_cache()->None:
    """启动时加载已有缓存，并在需要时后台刷新。"""

    snapshot=load_snapshot_file()
    if snapshot is not None:
        install_snapshot(snapshot)
        if not snapshot_is_fresh(snapshot):
            schedule_snapshot_refresh()
        return
    schedule_snapshot_refresh()


def get_snapshot()->WordCloudSnapshot|None:
    """获取当前快照，过期时自动在后台刷新。"""

    with _cache_lock:
        snapshot=_snapshot_cache
        
    if snapshot is None:
        schedule_snapshot_refresh()
    elif not snapshot_is_fresh(snapshot):
        schedule_snapshot_refresh()

    return snapshot