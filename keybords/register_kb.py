from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

register =InlineKeyboardMarkup(inline_keyboard=[
[
InlineKeyboardButton(text='Да', callback_data= 'register')
],
[
InlineKeyboardButton(text='Нет', callback_data='start')
]
])