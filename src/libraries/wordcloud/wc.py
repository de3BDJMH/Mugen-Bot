import wordcloud
import jieba
import json
import requests
import sqlite3 as sql
import datetime
import pytz
import os
import pathlib
from collections import Counter


STOPWORDS=['的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这', '那', '她', '他', '它', '我们', '你们', '他们', '她们', '它们', '但', '而', '以', '与', '为', '此', '于', '或', '且', '之', '其', '所', '得', '里', '中', '下', '过', '吧', '啊', '吗', '呢', '呀', '啦', '哇', '哦', '哎', '哼', '把', '被', '让', '向', '对', '对于', '关于', '由于', '因此', '所以', '并且', '而且', '如果', '虽然', '即使', '既然', '无论', '还', '更', '最', '太', '非常', '十分', '特别', '尤其', '比较', '有点', '一些', '一切', '所有', '任何', '每个', '这种', '那种', '哪些', '并', '却', '只', '仅', '才', '曾', '曾将', '已经', '正在', '将', '要', '想', '不要', '能否', '可以', '可能', '能够', '进行', '可以', '知道', '觉得', '理解', '感觉', '看到', '看到', '发现', '使用', '做', '作', '走', '来', '去', '出', '回', '起来', '下来', '过来', '这样', '那样', '那么', '怎么', '什么', '为什么', '如何', '怎样', '哪里', '哪个', '谁', '多少', '几个', '为什么', '大', '小', '多', '少', '新', '老', '高', '低', '长', '短', '红', '白', '黑', '好', '坏', '快', '慢', '强', '弱', '真', '假', '全', '美', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十', '百', '千', '万', '亿', '几', '第一', '年', '月', '日', '时', '分', '秒', '今天', '昨天', '明天', '刚才', '现在', '之前', '之后', '以后', '然后', '最后', '最近', '当时', '同时', '等', '等等', '之类', '一样', '一般', '一下', '一点', '一种', '之一', '的话', '所谓', '所谓', '的话', '来说', '来讲', '来看', '呀', '呗', '罢了', '而已', '这个', '那个']
BAN=[201587152,2530444361,3328144510,1316513361,(2854196301,2854216399),66600000,(3889000000,3889999999),(4010000000,4019999999)]
STOPWORDS_ADDITION=["签到","抢劫"]
STOPWORDS_COMMA=['，', '。', '！', '？', '；', '：', '、', '·', '《', '》', '「', '」', '『', '』','【', '】', '（', '）', '〔', '〕', '—', '～', '…', '‧', '﹏', '﹑', '﹒', '﹔','﹕', '！', '＃', '＄', '％', '＆', '＊', '＋', '－', '／', '＜', '＝', '＞', '＠','［', '］', '＼', '］', '＿', '｀', '｛', '｜', '｝', '～', '｟', '｠', '｡', '｢','｣', '､', '･', ',', '.', '!', '?', ';', ':', '"', "'", '(', ')', '[', ']','{', '}', '/', '\\', '|', '-', '_', '+', '=', '*', '&', '^', '%', '$', '#','@', '~', '`', '<', '>', '。', '，', '！', '？', '；', '：', '、', '·','“','”']

DATA_PATH=pathlib.Path(__file__).resolve().parent.parent.parent.parent/"data"/"wordcloud"

def get_history_message(group_id: int, message_seq: int=0, count: int=20, reverseOrder: bool=False):
    url = "http://127.0.0.1:3000/get_group_msg_history"

    payload = json.dumps({
    "group_id": group_id,
    "message_seq": message_seq,
    "count": count,
    "reverseOrder": reverseOrder
    })
    headers = {
    'Authorization': 'Bearer ',
    'Content-Type': 'application/json'
    }

    response = requests.request("POST", url, headers=headers, data=payload)
    return response.json()


class User:
    def __init__(self,user_id:int,group_id:int):
        self.user_id=user_id
        self.group_id=group_id
        self.save_path=DATA_PATH/"database"/"user"/f"{self.group_id}\\{self.user_id}.db"
        if not os.path.exists(DATA_PATH/"database"/"user"/f"{self.group_id}"):
            os.makedirs(DATA_PATH/"database"/"user"/f"{self.group_id}")

    def path_exists(self) -> bool: 
        if os.path.exists(self.save_path):
            return True
        return False
    
    def save_words(self,words:dict,table_name:str):
        """存储单个用户的每日词频"""
        if not os.path.exists(self.save_path):#不存在则创建
            with open(self.save_path,"w",encoding="utf-8") as f:
                pass
        conn=sql.connect(self.save_path)
        cursor=conn.cursor()
        cursor.execute(f"CREATE TABLE IF NOT EXISTS `{table_name}` (word TEXT PRIMARY KEY, n INT)")#创建当天分词表
        data=[(word,words[word]) for word in words]
        cursor.executemany(f"INSERT INTO `{table_name}` (word, n) VALUES (?, ?) ON CONFLICT(word) DO UPDATE SET n = n + excluded.n",data)#更新词频
        conn.commit()
        conn.close()
    
    def get_data(self,date:tuple):
        """获取降序排序的指定日期词频"""
        table_name=f"{date[0]}_{date[1]}_{date[2]}"
        conn=sql.connect(self.save_path)
        cursor=conn.cursor()
        try:
            cursor.execute(f"""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='{table_name}'
            """)# 检查表是否存在
            if cursor.fetchone():
                cursor.execute(f"SELECT * FROM '{table_name}' ORDER BY n DESC")#获取数据，降序排序
                rows=cursor.fetchall()
                conn.close()
                res={}
                for row in rows:
                    res[row[0]]=row[1]
                return res
        except:
            conn.close()
            return {}


class Group:
    def __init__(self,group_id:int):
        self.group_id=group_id
        self.save_path=DATA_PATH/"database"/"group"/f"{self.group_id}.db"
    
    def get_msg(self,timestamp:int,end:int=-1):
        """获取指定时间后的消息
        提供end（时间戳）表示结束时间"""
        messages=[]
        msgs=get_history_message(self.group_id,0,500)
        while msgs["data"]["messages"] and msgs["data"]["messages"][0]["time"]>=timestamp:
            print(f"当前时间戳：{msgs["data"]["messages"][0]["time"]}")
            if end>=0:
                for p in range(len(msgs["data"]["messages"])-1,-1,-1):
                    if msgs["data"]["messages"][p]["time"]<=end:
                        messages=msgs["data"]["messages"][:p+1]+messages
                        break
            else:
                messages=msgs["data"]["messages"]+messages
            last_seq=msgs["data"]["messages"][0]["message_seq"]-1
            msgs=get_history_message(self.group_id,last_seq,500)
        for p in range(len(msgs["data"]["messages"])):
            if msgs["data"]["messages"][p]["time"]>=timestamp:
                messages=msgs["data"]["messages"][p:]+messages
                break
        return messages

    def save_words(self,timestamp:int,end:int=-1):
        """存储指定群聊及群内用户的每日词频，end同上"""
        messages=self.get_msg(timestamp,end)
        users={}
        for msg in messages:
            uid=msg["user_id"]
            for m in msg["message"]:
                if m["type"]=="text":
                    if not uid in users:
                        users[uid]=[]
                    users[uid].append(m["data"]["text"])
        timezone = pytz.timezone('Asia/Shanghai')
        savetime=datetime.datetime.fromtimestamp(timestamp,timezone)
        table_name=f"{savetime.year}_{savetime.month}_{savetime.day}"#用时间戳的日期作表名
        group_words=Counter()#全群词频
        for uid in users:
            user=User(uid,self.group_id)
            text="".join(users[uid])
            words=Counter(jieba.lcut(text))#群友词频
            group_words.update(words)
            user.save_words(words,table_name)#保存群友词频
        conn=sql.connect(self.save_path)
        cursor=conn.cursor()
        cursor.execute(f"CREATE TABLE IF NOT EXISTS `{table_name}` (word TEXT PRIMARY KEY, n INT)")#创建当天分词表
        data=[(word,group_words[word]) for word in group_words]
        cursor.executemany(f"INSERT INTO `{table_name}` (word, n) VALUES (?, ?) ON CONFLICT(word) DO UPDATE SET n = n + excluded.n",data)#更新词频
        conn.commit()
        conn.close()
    
    def save_msg_words(self,msg,uid):
        """存储指定消息的词频"""
        savetime=datetime.datetime.now()
        table_name=f"{savetime.year}_{savetime.month}_{savetime.day}"#用时间戳的日期作表名
        user=User(uid,self.group_id)
        words=Counter(jieba.lcut(msg))#单条消息的用户和群组词频相等
        user.save_words(words,table_name)#保存群友词频
        conn=sql.connect(self.save_path)
        cursor=conn.cursor()
        cursor.execute(f"CREATE TABLE IF NOT EXISTS `{table_name}` (word TEXT PRIMARY KEY, n INT)")#创建当天分词表
        data=[(word,words[word]) for word in words]
        cursor.executemany(f"INSERT INTO `{table_name}` (word, n) VALUES (?, ?) ON CONFLICT(word) DO UPDATE SET n = n + excluded.n",data)#更新词频
        conn.commit()
        conn.close()
    
    def get_data(self,date:tuple):
        """获取降序排序的指定日期词频"""
        table_name=f"{date[0]}_{date[1]}_{date[2]}"
        conn=sql.connect(self.save_path)
        cursor=conn.cursor()
        try:
            cursor.execute(f"""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='{table_name}'
            """)# 检查表是否存在
            if cursor.fetchone():
                cursor.execute(f"SELECT * FROM '{table_name}' ORDER BY n DESC")#获取数据，降序排序
                rows=cursor.fetchall()
                conn.close()
                res={}
                for row in rows:
                    res[row[0]]=row[1]
                return res
        except:
            conn.close()
            return {}

    def get_user_data(self,user_id:int,date:tuple):
        """获取指定用户降序排序的指定日期词频"""
        user=User(user_id,self.group_id)
        if not user.path_exists():
            return {}
        res=user.get_data(date)
        return res

def generate(words:dict,save_path:str):
    """生成词云"""
    stopwords=STOPWORDS+STOPWORDS_ADDITION+STOPWORDS_COMMA
    for stopword in stopwords:
        if stopword in words:
            del words[stopword]
    wc=wordcloud.WordCloud(font_path=DATA_PATH/"1681647739829689.otf",width=800,height=600,background_color="white").generate_from_frequencies(words)
    wc.to_file(save_path)
    return save_path