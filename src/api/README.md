## 注册API流程

`src/api` 内的代码用于向 Web 等外部程序提供访问 Bot 数据和功能的 HTTP API。

Bot 启动时，PluginAPI 插件会调用 `setup_api()`，
将各 Router 注册到 NoneBot 自带的 FastAPI 应用中。


*假设你的插件名字为“MGP”*

### 1.创建schema

创建src/api/schemas/MGP.py，并写入定义你需要返回的数据结构内容

### 2.创建router

创建src/api/routers/MGP.py

写入：
```
from fastapi import APIRouter

router = APIRouter(
    prefix="/api/MGP",
    tags=["MGP"],
)
```

然后添加你的方法

### 3.注册router

编辑scr/api/__init__.py

导入你的router：
```
from .routers.MGP import router as MGP_router
```
并在setup_api()中注册：
```
app.include_router(MGP_router)
```

### 4.检查

访问 [](http://127.0.0.1:8080/docs)

测试你的接口能否正常工作