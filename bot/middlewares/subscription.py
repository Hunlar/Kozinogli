
import logging

from aiogram import Router, BaseMiddleware
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

router = Router()
logger = logging.getLogger(__name__)

# Zorunlu üyelik sohbetleri
REQUIRED_CHATS = [
    "@emeklisanalci",
    -1004326389896
]

GROUP_INVITE_LINK = "https://t.me/+_XbbelgBCFJkZjk0"


def subscription_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 Kanalımıza Katıl",
                    url="https://t.me/emeklisanalci"
                )
            ],
            [
                InlineKeyboardButton(
                    text="👥 Grubumuza Katıl",
                    url=GROUP_INVITE_LINK
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Üyeliğimi Kontrol Et",
                    callback_data="check_subscription"
                )
            ]
        ]
    )


async def check_membership(bot, user_id: int) -> bool:
    for chat in REQUIRED_CHATS:
        try:
            member = await bot.get_chat_member(
                chat_id=chat,
                user_id=user_id
            )

            status = member.status

            if status not in ("creator", "administrator", "member"):
                if status != "restricted" or not member.is_member:
                    return False

        except Exception:
            logger.exception(
                "Üyelik kontrolü başarısız: %s / %s",
                user_id,
                chat
            )
            return False

    return True


class SubscriptionMiddleware(BaseMiddleware):

    async def __call__(self, handler, event, data):

        user = getattr(event, "from_user", None)

        if user is None:
            return await handler(event, data)

        # Sohbet türünü belirle
        chat_type = None

        if isinstance(event, Message):
            chat_type = event.chat.type

        elif isinstance(event, CallbackQuery):
            if event.message:
                chat_type = event.message.chat.type

        # Grup ve süper gruplarda üyelik kontrolünü tamamen atla
        if chat_type in ("group", "supergroup"):
            return await handler(event, data)

        # Yalnızca özel sohbetlerde üyelik kontrolü yap
        if chat_type != "private":
            return await handler(event, data)

        # Üyelik kontrol butonunun kendi handler'ı çalışabilsin
        if (
            isinstance(event, CallbackQuery)
            and event.data == "check_subscription"
        ):
            return await handler(event, data)

        bot = data["bot"]

        if await check_membership(bot, user.id):
            return await handler(event, data)

        text = (
            "🔒 **ÖzVeGas'a Devam Etmek İçin**\n\n"
            "Kanalımıza ve grubumuza katılmalısın.\n\n"
            "1. Kanalımıza katıl.\n"
            "2. Grubumuza katıl.\n"
            "3. Üyeliğini kontrol et."
        )

        if isinstance(event, Message):
            await event.answer(
                text,
                reply_markup=subscription_keyboard(),
                parse_mode="Markdown"
            )

        elif isinstance(event, CallbackQuery):
            if event.message:
                await event.message.answer(
                    text,
                    reply_markup=subscription_keyboard(),
                    parse_mode="Markdown"
                )

            await event.answer()

        return None


@router.callback_query(
    lambda callback: callback.data == "check_subscription"
)
async def verify_subscription(callback: CallbackQuery):

    # Üyelik kontrolü yalnızca özel sohbetlerde yapılır
    if (
        callback.message is None
        or callback.message.chat.type != "private"
    ):
        await callback.answer()
        return

    is_member = await check_membership(
        callback.bot,
        callback.from_user.id
    )

    if is_member:
        await callback.answer(
            "Üyelik doğrulandı!",
            show_alert=True
        )

        await callback.message.edit_text(
            "✅ Kanal ve grup üyeliğin doğrulandı!\n\n"
            "ÖzVeGas'ı kullanmak için /start komutunu gönder."
        )

    else:
        await callback.answer(
            "❌ Henüz kanal veya grup üyeliğin tamamlanmamış.",
            show_alert=True
            )
        
