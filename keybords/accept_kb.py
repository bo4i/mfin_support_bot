from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

accept =InlineKeyboardMarkup(inline_keyboard=[
[
InlineKeyboardButton(text='Принять', callback_data='accept')
],
[
InlineKeyboardButton(text='Отказаться', callback_data= 'refuse')
]
])