from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

application_key = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Оставить заявку", callback_data="leave_request")],
            [InlineKeyboardButton(text="Не оставлять заявку", callback_data="cancel_request")]
        ])

owners_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Общаться с ботом")],
        [KeyboardButton(text="Просмотр заявок")],
        [KeyboardButton(text="Просмотр разрешённых пользователей")],
        [KeyboardButton(text="Просмотр чёрного списка")]],
    resize_keyboard=True,
    one_time_keyboard=True
)