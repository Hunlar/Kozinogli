from aiogram import Router
from .even_odd import router as even_odd_router
from .slots import router as slots_router
from .games_menu import router as games_menu_router
from .roulette import router as roulette_router
from .blackjack import router as blackjack_router
from .mines import router as mines_router
from .crash import router as crash_router

router = Router()
router.include_router(even_odd_router)
router.include_router(slots_router)
router.include_router(games_menu_router)
router.include_router(roulette_router)
router.include_router(blackjack_router)
router.include_router(mines_router)
router.include_router(crash_router)