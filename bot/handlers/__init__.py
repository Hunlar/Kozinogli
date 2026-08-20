# bot/handlers/__init__.py
from aiogram import Dispatcher


def setup_handlers(dp: Dispatcher):
    from .common import router as common_router
    from .auth import router as auth_router
    from .profile import router as profile_router
    from .purchase import router as purchase_router
    from .top_up import router as top_up_router
    from .support import router as support_router
    from .games import router as games_router
    from .bonuses import router as bonuses_router
    from .admin_handlers import router as admin_router

    dp.include_router(common_router)
    dp.include_router(auth_router)
    dp.include_router(profile_router)
    dp.include_router(games_router)
    dp.include_router(purchase_router)
    dp.include_router(top_up_router)
    dp.include_router(support_router)
    dp.include_router(bonuses_router)
    dp.include_router(admin_router)
