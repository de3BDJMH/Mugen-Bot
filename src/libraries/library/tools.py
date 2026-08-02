import requests
from bs4 import BeautifulSoup
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import base64
import random
import json
from pathlib import Path
import datetime
from functools import wraps

REGION_LIST={
    "10": ["新书畅阅空间","一楼"],
    "12": ["第二借阅室","二楼"],
    "13": ["外文借阅室","二楼"],
    "15": ["自主学习区一","二楼"],
    "16": ["第三借阅室","三楼"],
    "17": ["报刊阅览室","四楼"],
    "18": ["教参库","四楼"],
    "19": ["自主学习区二","四楼"],
    "23": ["研究厢","二层"],
    "24": ["研究厢","三层"],
    "26": ["好书馆","三楼"],
    "39": ["研习区","四楼"],
    "51": ["单人研习位","三楼"],
    "61": ["24小时书房","一楼"],
    "25": ["综合阅览室（西区）","邵馆"],
    "56": ["综合阅览室（东区）","邵馆"],
    "47": ["三楼阅览区","杭州校区"],
}

CHARS = "ABCDEFGHJKMNPQRSTWXYZabcdefhijkmnprstwxyz2345678"

class ZJNUClient:
    def __init__(self, username, password, cookie_file="cookies.json"):
        self.username = username
        self.password = password
        self.cookie_file = Path(cookie_file)
        self.session = None
        self._ensure_login()

    def _random_str(self, n):
        return ''.join(random.choice(CHARS) for _ in range(n))

    def _encrypt_password(self, password, key):
        salt = self._random_str(64)
        plain = salt + password
        iv = self._random_str(16).encode()
        cipher = AES.new(key.encode(), AES.MODE_CBC, iv)
        encrypted = cipher.encrypt(pad(plain.encode(), AES.block_size))
        return base64.b64encode(encrypted).decode()

    def _ensure_login(self):
        """确保会话有效，自动复用或重新登录"""
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'Mozilla/5.0'})

        if self.cookie_file.exists():
            self.session.cookies.update(json.loads(self.cookie_file.read_text()))
            resp = self.session.get("http://zwgl.zjnu.edu.cn/h5/index.html", allow_redirects=False)
            if resp.status_code == 200 and "登录" not in resp.text:
                print("✅ 使用已有 Cookie")
                return

        print("🔄 登录中...")
        login_url = "https://authserver.zjnu.edu.cn/authserver/login"
        params = {'service': 'http://zwgl.zjnu.edu.cn/api/cas/cas'}

        resp = self.session.get(login_url, params=params)
        soup = BeautifulSoup(resp.text, 'html.parser')
        lt = soup.find('input', {'name': 'lt'})['value']
        execution = soup.find('input', {'name': 'execution'})['value']
        salt = soup.find('input', {'id': 'pwdEncryptSalt'})['value']

        data = {
            'username': self.username,
            'password': self._encrypt_password(self.password, salt),
            'captcha': '',
            '_eventId': 'submit',
            'cllt': 'userNameLogin',
            'dllt': 'generalLogin',
            'lt': lt,
            'execution': execution,
            'rememberMe': 'true',
        }
        resp = self.session.post(login_url, data=data, params=params, allow_redirects=False)
        if resp.status_code != 302:
            raise Exception("登录失败")

        self.session.get(resp.headers['Location'])
        self.session.get("http://zwgl.zjnu.edu.cn/h5/index.html")
        self.cookie_file.write_text(json.dumps(dict(self.session.cookies), indent=2))
        print("✅ 登录成功")

    def _check_login(self) -> bool:
        """检查会话是否仍然有效"""
        if not self.session:
            return False
        try:
            resp = self.session.get(
                "http://zwgl.zjnu.edu.cn/h5/index.html",
                allow_redirects=False,
                timeout=3
            )
            return resp.status_code == 200 and "登录" not in resp.text
        except Exception:
            return False
    
    def _ensure_session(func):
        """装饰器：在调用方法前确保会话有效"""
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if not self._check_login():
                print("会话已过期，重新登录...")
                self._ensure_login()
            print("登录未过期")
            return func(self, *args, **kwargs)
        return wrapper

    @_ensure_session
    def query(self, area, segment, day=None, startTime=None, endTime="22:00"):
        """查询座位"""
        if day is None:
            day = datetime.datetime.now().strftime("%Y-%m-%d")
        if startTime is None:
            startTime = datetime.datetime.now().strftime("%H:%M")

        resp = self.session.post(
            "http://zwgl.zjnu.edu.cn/api/Seat/seat",
            json={
                "area": area,
                "segment": segment,
                "day": day,
                "startTime": startTime,
                "endTime": endTime,
            }
        )
        return resp.json()["data"]