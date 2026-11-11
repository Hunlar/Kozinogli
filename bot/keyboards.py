
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton
)

from settings import ADMINS


def create_keyboard(buttons):
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=text)
                for text in row
            ]
            for row in buttons
        ],
        resize_keyboard=True
    )


# --------------------------------------------------
# ANA MENÜ
# --------------------------------------------------

def main_menu(user_id: int = None):

    buttons = [
        ["👤 Profil", "🎮 Oyunlar"],
        ["🎁 Bonuslar", "🛠 Destek"]
    ]

    if user_id and user_id in ADMINS:
        buttons.append(["🛠 Admin Paneli"])

    return create_keyboard(buttons)


# --------------------------------------------------
# ADMIN MENÜSÜ
# --------------------------------------------------

def admin_menu():

    buttons = [
        ["📢 Duyuru Gönder", "🪙 Sanal Kredi Ekle"],
        ["🚫 Kullanıcıyı Engelle", "🔓 Engeli Kaldır"],
        ["📊 İstatistikler", "🎮 Oyun Çarpanları"],
        ["🚪 Admin Panelinden Çık"]
    ]

    return create_keyboard(buttons)


# --------------------------------------------------
# OYUN MENÜSÜ
# --------------------------------------------------

def games_menu():

    buttons = [
        ["🎲 Çift / Tek", "💎 Slot Makinesi"],
        ["🎰 Rulet", "🃏 Blackjack", "💣 Mayınlar"],
        ["🚀 Roket"],
        ["🔙 Geri"]
    ]

    return create_keyboard(buttons)


# --------------------------------------------------
# MAYINLAR
# --------------------------------------------------

def mines_keyboard():

    buttons = [
        ["3", "5", "7"],
        ["9", "10", "🔙 Geri"]
    ]

    return create_keyboard(buttons)


# --------------------------------------------------
# RULET
# --------------------------------------------------

def roulette_bet_types_kb():

    buttons = [
        ["🔢 Sayı", "🎨 Renk"],
        ["📊 Aralık", "🔙 Geri"]
    ]

    return create_keyboard(buttons)


def roulette_colors_kb():

    buttons = [
        ["🔴 Kırmızı", "⚫ Siyah"],
        ["🟢 Yeşil", "🔙 Geri"]
    ]

    return create_keyboard(buttons)


def roulette_ranges_kb():

    buttons = [
        ["1️⃣-1️⃣2️⃣", "1️⃣3️⃣-2️⃣4️⃣"],
        ["2️⃣5️⃣-3️⃣6️⃣", "🔙 Geri"]
    ]

    return create_keyboard(buttons)


def roulette_numbers_kb():

    buttons = [
        [str(i) for i in range(0, 13)],
        [str(i) for i in range(13, 25)],
        [str(i) for i in range(25, 37)],
        ["🔙 Geri"]
    ]

    return create_keyboard(buttons)


# --------------------------------------------------
# ÇİFT / TEK
# --------------------------------------------------

def even_odd_kb():

    buttons = [
        ["Çift", "Tek"],
        ["🔙 Geri"]
    ]

    return create_keyboard(buttons)


# --------------------------------------------------
# BAHİS MENÜSÜ
# --------------------------------------------------

def bet_kb():

    buttons = [
        ["50", "100", "200"],
        ["500", "1000"],
        ["🔙 Geri"]
    ]

    return create_keyboard(buttons)


# --------------------------------------------------
# BONUS MENÜSÜ
# --------------------------------------------------

def bonuses_menu():

    buttons = [
        ["🎁 Bonus Çarkı"],
        ["🔙 Geri"]
    ]

    return create_keyboard(buttons)


# --------------------------------------------------
# GENEL GERİ BUTONU
# --------------------------------------------------

def back_button():

    return create_keyboard([
        ["🔙 Geri"]
    ])


# --------------------------------------------------
# PROFİL
# --------------------------------------------------

def profile_menu():

    return back_button()


# --------------------------------------------------
# BAKİYE MENÜSÜ
# --------------------------------------------------

def top_up_menu():

    return back_button()
