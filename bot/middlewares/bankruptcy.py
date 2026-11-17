
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select

from db.database import AsyncSessionLocal
from db.models import User


BANKRUPTCY_LIMIT = 4000

ACTIVE_GAME_STATES = {
    "BlackjackStates:PLAYER_TURN",
    "MinesStates:CHOOSE_MINES",
    "MinesStates:PLAYING",
    "CrashStates:COEFF_INPUT",
    "CrashStates:FLYING",
    "EvenOddStates:CHOICE",
}


class BankruptcyMiddleware(BaseMiddleware):

    async def __call__(self, handler, event, data):

        telegram_user = getattr(event, "from_user", None)

        if telegram_user is None:
            return await handler(event, data)

        if isinstance(event, Message):
            chat_type = event.chat.type
        elif isinstance(event, CallbackQuery) and event.message:
            chat_type = event.message.chat.type
        else:
            chat_type = None

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User).where(
                    User.tg_id == telegram_user.id
                )
            )

            user = result.scalar_one_or_none()

            if chat_type in ("group", "supergroup"):
                if user is None or not user.has_started:
                    return

            if user is None:
                return await handler(event, data)

            balance = user.balance or 0
            is_bankrupt = user.is_bankrupt

        fsm_state = data.get("state")

        if fsm_state is not None:
            try:
                current_state = await fsm_state.get_state()

                if current_state in ACTIVE_GAME_STATES:
                    return await handler(event, data)
            except Exception:
                pass

        if balance < BANKRUPTCY_LIMIT or is_bankrupt:

            # Sohbete iflas mesajı gönderme.
            # İflas bildirimi özelden check_bankruptcy
            # fonksiyonu tarafından yalnızca bir defa gönderilir.

            if isinstance(event, CallbackQuery):
                await event.answer(
                    "💸 İflas durumundasın. "
                    "Yeni oyun için /borc komutunu kullan.",
                    show_alert=True
                )

            return

        return await handler(event, data)
        
