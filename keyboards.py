from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

application_key = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Оставить заявку", callback_data="leave_request")],
            [InlineKeyboardButton(text="Не оставлять заявку", callback_data="cancel_request")]
        ])

owners_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💬 Общаться с ботом")],
        [KeyboardButton(text="📋 Заявки"), KeyboardButton(text="✅ Разрешённые"), KeyboardButton(text="🚫 Чёрный список")],
        [KeyboardButton(text="📤 Загрузить разговор")]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

admitted_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💬 Общаться с ботом")]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

# Кнопка отмены
def get_cancel_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data="cancel_upload")]
    ])