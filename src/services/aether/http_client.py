import requests
from curl_cffi import requests as browser_requests
from curl_cffi.requests.exceptions import RequestException

class AetherSession(browser_requests.Session):
    """使用浏览器式握手，沿用系统代理和现有网络异常处理。"""
    def __init__(self,url:str):
        super().__init__(impersonate="chrome",proxies=requests.utils.get_environ_proxies(url),trust_env=False)

    def request(self,*args,**kwargs):
        try:
            return super().request(*args,**kwargs)
        except RequestException as exc:
            raise requests.RequestException(str(exc)) from exc

