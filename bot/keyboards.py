
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton
)

from settings import ADMINS


def main_menu(user_id: int = None):
    buttons = [
        ["👤 Profil", "🎮 Oyunlar"],
        ["🎁 Bonuslar", "🛠 Destek"]
    ]

    if user_id and user_id in ADMINS:
        buttons.append(["🛠 Admin Paneli"])

    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=text) for text in row]
            for row in buttons
        ],
        resize_keyboard=True
    )


def admin_menu():
    buttons = [
        ["📢 Duyuru Gönder", "🪙 Sanal Kredi Ekle"],
        ["🚫 Kullanıcıyı Engelle", "🔓 Engeli Kaldır"],
        ["📊 İstatistikler", "🎮 Oyun Çarpanları"],
        ["🚪 Admin Panelinden Çık"]
    ]

    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=text) for text in row]
            for row in buttons
        ],
        resize_keyboard=True
    )


def mines_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="3"),
                KeyboardButton(text="5"),
                KeyboardButton(text="7")
            ],
            [
                KeyboardButton(text="9"),
                KeyboardButton(text="10"),
                KeyboardButton(text="🔙 Geri")
            ]
        ],
        resize_keyboard=True
    )


def games_menu():
    buttons = [
        ["🎲 Çift / Tek", "💎 Slot Makinesi"],
        ["🎰 Rulet", "🃏 Blackjack", "💣 Mayınlar"],
        ["🚀 Roket"],
        ["🔙 Geri"]
    ]

    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=text) for text in row]
            for row in buttons
        ],
        resize_keyboard=True
    )


def roulette_bet_types_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🔢 Sayı"),
                KeyboardButton(text="🎨 Renk")
            ],
            [
                KeyboardButton(text="📊 Aralık"),
                KeyboardButton(text="🔙 Geri")
            ]
        ],
        resize_keyboard=True
    )


def roulette_colors_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🔴 Kırmızı"),
                KeyboardButton(text="⚫ Siyah")
            ],
            [
                KeyboardButton(text="🟢 Yeşil"),
                KeyboardButton(text="🔙 Geri")
            ]
        ],
        resize_keyboard=True
    )


def roulette_ranges_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="1️⃣-1️⃣2️⃣"),
                KeyboardButton(text="1️⃣3️⃣-2️⃣4️⃣")
            ],
            [
                KeyboardButton(text="2️⃣5️⃣-3️⃣6️⃣"),
                KeyboardButton(text="🔙 Geri")
            ]
        ],
        resize_keyboard=True
    )


def roulette_numbers_kb():
    buttons = [
        [KeyboardButton(text=str(i)) for i in range(0, 13)],
        [KeyboardButton(text=str(i)) for i in range(13, 25)],
        [KeyboardButton(text=str(i)) for i in range(25, 37)],
        [KeyboardButton(text="🔙 Geri")]
    ]

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True
    )


def even_odd_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="Çift"),
                KeyboardButton(text="Tek")
            ],
            [KeyboardButton(text="🔙 Geri")]
        ],
        resize_keyboard=True
    )


def bet_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="50"),
                KeyboardButton(text="100"),
                KeyboardButton(text="200")
            ],
            [
                KeyboardButton(text="500"),
                KeyboardButton(text="1000")
            ],
            [KeyboardButton(text="🔙 Geri")]
        ],
        resize_keyboard=True
    )


def bonuses_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎁 Bonus Çarkı")],
            [KeyboardButton(text="🔙 Geri")]
        ],
        resize_keyboard=True
    )


def top_up_menu():
    return back_button()


def back_button():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🔙 Geri")]],
        resize_keyboard=True
    )


def profile_menu():
    return back_button()
