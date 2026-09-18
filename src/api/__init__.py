from nonebot import get_app
from fastapi import Depends
from fastapi.middleware.gzip import GZipMiddleware

from .dependencies import require_internal_api_key
from .routers.bot import router as bot_router
from .routers.checkin import router as checkin_router
from .routers.charcounter import router as charcounter_router
from .routers.wordcloud import router as wordcloud_router
from .routers.watchice import router as watchice_router
from .routers.watchice_gacha import router as watchice_gacha_router
from .routers.aether import router as aether_router,status_router as aether_status_router


def setup_api():
    """
    将各APIRouter注册到NoneBot自带的FastAPI应用中。并添加API鉴权
    """
    app = get_app()
    app.add_middleware(GZipMiddleware,minimum_size=1024,compresslevel=5,)
    app.include_router(bot_router,dependencies=[Depends(require_internal_api_key)])
    app.include_router(checkin_router,dependencies=[Depends(require_internal_api_key)])
    app.include_router(charcounter_router,dependencies=[Depends(require_internal_api_key)])
    app.include_router(wordcloud_router,dependencies=[Depends(require_internal_api_key)])
    app.include_router(watchice_router,dependencies=[Depends(require_internal_api_key)])
    app.include_router(watchice_gacha_router,dependencies=[Depends(require_internal_api_key)])
    app.include_router(aether_router,dependencies=[Depends(require_internal_api_key)])
    app.include_router(aether_status_router,dependencies=[Depends(require_internal_api_key)])
