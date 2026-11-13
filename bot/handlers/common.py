
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardRemove
)

from settings import ADMINS


router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMINS


def help_keyboard(user_id: int):
    buttons = [
        [
            InlineKeyboardButton(
                text="👤 Kullanıcı Komutları",
                callback_data="help:user"
            )
        ],
        [
            InlineKeyboardButton(
                text="🎮 Oyun Komutları",
                callback_data="help:games"
            )
        ]
    ]

    if is_admin(user_id):
        buttons.append([
            InlineKeyboardButton(
                text="🛡 Admin Komutları",
                callback_data="help:admin"
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def back_keyboard(user_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔙 Geri",
                    callback_data="help:back"
                )
            ]
        ]
    )


@router.message(Command("help"))
async def show_help(message: Message):
    await message.answer(
        "📚 <b>ÖzVeGas Yardım Menüsü</b>\n\n"
        "Görmek istediğin komut kategorisini seç:",
        reply_markup=help_keyboard(message.from_user.id),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("help:"))
async def help_navigation(callback: CallbackQuery):
    user_id = callback.from_user.id
    action = callback.data.split(":", 1)[1]

    if action == "back":
        await callback.message.edit_text(
            "📚 <b>ÖzVeGas Yardım Menüsü</b>\n\n"
            "Görmek istediğin komut kategorisini seç:",
            reply_markup=help_keyboard(user_id),
            parse_mode="HTML"
        )

    elif action == "user":
        await callback.message.edit_text(
            "👤 <b>Kullanıcı Komutları</b>\n\n"
            "/start - Botu başlat\n"
            "/help - Yardım menüsü\n"
            "/profile - Profilini görüntüle\n"
            "/games - Oyunları listele\n"
            "/bonus - Günlük bonus bilgisi\n"
            "/bonuscevir - Bonus çarkını çevir\n"
            "/support - Destek talebi oluştur\n"
            "/borc - Kasadan kredi al\n"
            "/borcver - Yanıtladığın kullanıcıya kredi gönder\n"
            "/borclarim - Borçlarını görüntüle\n"
            "/borcodeme - Borcunu öde\n"
            "/iptal - Devam eden işlemi iptal et",
            reply_markup=back_keyboard(user_id),
            parse_mode="HTML"
        )

    elif action == "games":
        await callback.message.edit_text(
            "🎮 <b>Oyun Komutları</b>\n\n"
            "/slots - Slot oyunu\n"
            "/roulette - Rulet oyunu\n"
            "/blackjack - Blackjack oyunu\n"
            "/mines - Mayın oyunu\n"
            "/rocket - Roket oyunu\n"
            "/evenodd - Tek / Çift oyunu\n\n"
            "🔫 <b>Grup Rus Ruleti</b>\n"
            "/kayit - Kullanıcı adını davetler için kaydet\n"
            "/rulet @username - Grupta oyuncuya düello daveti gönder\n"
            "Davet edilen oyuncu kabul ederse grup bahisleri başlar.",
            reply_markup=back_keyboard(user_id),
            parse_mode="HTML"
        )

    elif action == "admin":
        if not is_admin(user_id):
            await callback.answer(
                "⛔ Bu kategoriye erişim yetkin yok.",
                show_alert=True
            )
            return

        await callback.message.edit_text(
            "🛡 <b>Admin Komutları</b>\n\n"
            "/admin - Yönetici paneli\n"
            "/broadcast - Duyuru gönder\n"
            "/credit - Kullanıcıya kredi ekle\n"
            "/ban - Kullanıcıyı engelle\n"
            "/unban - Kullanıcının engelini kaldır\n"
            "/stats - Bot istatistikleri\n"
            "/multiplier - Oyun çarpanını ayarla",
            reply_markup=back_keyboard(user_id),
            parse_mode="HTML"
        )

    await callback.answer()
