
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from settings import TECH_SUPPORT_USER_ID


router = Router()


class SupportStates(StatesGroup):
    AWAITING_DESCRIPTION = State()


@router.message(Command("support"))
async def start_support_request(
    message: Message,
    state: FSMContext
):
    await state.clear()

    await message.answer(
        "🛠 **ÖzVeGas Destek Merkezi**\n\n"
        "📨 Yaşadığın sorunu ayrıntılı şekilde anlat.\n\n"
        "Metin, fotoğraf, video, belge veya sesli mesaj "
        "gönderebilirsin.\n\n"
        "❌ İşlemi iptal etmek için /iptal yaz.",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )

    await state.set_state(SupportStates.AWAITING_DESCRIPTION)


@router.message(
    Command("iptal"),
    SupportStates.AWAITING_DESCRIPTION
)
async def cancel_support_request(
    message: Message,
    state: FSMContext
):
    await state.clear()

    await message.answer(
        "❌ Destek talebi iptal edildi.",
        reply_markup=ReplyKeyboardRemove()
    )


@router.message(SupportStates.AWAITING_DESCRIPTION)
async def forward_to_support(
    message: Message,
    state: FSMContext,
    bot
):
    if not TECH_SUPPORT_USER_ID:
        await message.answer(
            "❌ Destek sistemi şu anda yapılandırılmamış. "
            "Lütfen daha sonra tekrar dene.",
            reply_markup=ReplyKeyboardRemove()
        )
        await state.clear()
        return

    username = (
        f"@{message.from_user.username}"
        if message.from_user.username
        else "Kullanıcı adı bulunmuyor"
    )

    user_info = (
        "🛠 **YENİ DESTEK TALEBİ**\n\n"
        f"👤 Kullanıcı: {message.from_user.full_name}\n"
        f"🔗 Kullanıcı adı: {username}\n"
        f"🆔 Telegram ID: `{message.from_user.id}`\n"
        f"💬 Sohbet ID: `{message.chat.id}`"
    )

    try:
        await bot.send_message(
            chat_id=TECH_SUPPORT_USER_ID,
            text=user_info,
            parse_mode="Markdown"
        )

        await bot.copy_message(
            chat_id=TECH_SUPPORT_USER_ID,
            from_chat_id=message.chat.id,
            message_id=message.message_id
        )

    except Exception:
        await message.answer(
            "❌ Destek talebin gönderilemedi.\n"
            "Lütfen daha sonra tekrar dene."
        )
        return

    await state.clear()

    await message.answer(
        "✅ Destek talebin başarıyla gönderildi!\n\n"
        "Ekibimiz başvurunu inceleyecek ve seninle "
        "en kısa sürede iletişime geçecektir.",
        reply_markup=ReplyKeyboardRemove()
    )
    
