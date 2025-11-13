from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

start =InlineKeyboardMarkup(inline_keyboard=[
[
InlineKeyboardButton(text='Создать заявку', callback_data='new_application')
],
[
InlineKeyboardButton(text='Дистрибутивы', callback_data= 'distr')
],
[
InlineKeyboardButton(text='Портал бюджетной системы Липецкой области', url = 'https://ufin48.ru/')
],
[
InlineKeyboardButton(text='Вход в подсистему казначейского исполнения бюджета Липецкой области (Веб Бюджет)', url = 'https://it.ufin48.ru/next25obl/')
]
])