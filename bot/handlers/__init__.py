
from bot.middlewares.bankruptcy import BankruptcyMiddleware


def setup_handlers(dp):

    from bot.handlers.auth import router as auth_router
    from bot.handlers.common import router as common_router
    from bot.handlers.profile import router as profile_router
    from bot.handlers.debt import router as debt_router

    from bot.handlers.games.games_menu import router as games_menu_router
    from bot.handlers.games.slots import router as slots_router
    from bot.handlers.games.roulette import router as roulette_router
    from bot.handlers.games.blackjack import router as blackjack_router
    from bot.handlers.games.mines import router as mines_router
    from bot.handlers.games.crash import router as crash_router
    from bot.handlers.games.even_odd import router as even_odd_router

    from bot.handlers.bonuses import router as bonuses_router
    from bot.handlers.support import router as support_router
    from bot.handlers.admin_handlers import router as admin_router

    game_routers = [
        slots_router,
        roulette_router,
        blackjack_router,
        mines_router,
        crash_router,
        even_odd_router
    ]

    # İflas kontrolü yalnızca eşleşen oyun handler'larında çalışır.
    for game_router in game_routers:
        game_router.message.middleware(
            BankruptcyMiddleware()
        )

        game_router.callback_query.middleware(
            BankruptcyMiddleware()
        )

    # Temel sistemler
    dp.include_router(auth_router)
    dp.include_router(common_router)
    dp.include_router(profile_router)

    # Borç sistemi
    dp.include_router(debt_router)

    # Oyun menüsü
    dp.include_router(games_menu_router)

    # Oyunlar
    for game_router in game_routers:
        dp.include_router(game_router)

    # Diğer sistemler
    dp.include_router(bonuses_router)
    dp.include_router(support_router)
    dp.include_router(admin_router)
