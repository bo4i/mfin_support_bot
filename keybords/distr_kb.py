from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

dist_kb =InlineKeyboardMarkup(inline_keyboard=[
    [
    InlineKeyboardButton(text='Веб бюджет', url ='https://keysystems.ru/files/web/INSTALL/SMART2/install/24.2.318.220/BudgetSmart_24.2.318.220.exe')
    ],
    [
    InlineKeyboardButton(text='Свод смарт', url = 'https://keysystems.ru/files/smeta/install/svod-smart/INSTALL/23.1.0.38909/SvodSmart23.Client.Setup_23.1.0.38909_net472.exe')
    ],
    [
    InlineKeyboardButton(text='Проект', url = 'https://keysystems.ru/files/dwh/DWH2/23.0/23.11.61765.0/project.client.setup_23.11.61765.0_net472.exe')
    ],
    [
    InlineKeyboardButton(text='Профили', callback_data= 'profiles')
    ],
    [
    InlineKeyboardButton(text='Назад', callback_data= 'start')
    ]
    ])
profile_kb = InlineKeyboardMarkup(inline_keyboard=[
    [
    InlineKeyboardButton(text='Муниципальный бюджет', callback_data= 'munbudg')
    ],
    [
    InlineKeyboardButton(text='Областной', callback_data='oblbudg')
    ],
    [
    InlineKeyboardButton(text='Главное меню', callback_data= 'start')
    ]
    ])
munyear_kb = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text='2025', url = 'https://ufin48.ru/Show/File/7834?ParentItemId=218')
    ],
        [
        InlineKeyboardButton(text='2024', url = 'https://ufin48.ru/Show/File/7833?ParentItemId=218')
    ],    [
        InlineKeyboardButton(text='2023', url = 'https://ufin48.ru/Show/File/7832?ParentItemId=218')
    ],
    [
    InlineKeyboardButton(text='Главное меню', callback_data= 'start')
    ]
    ])
oblyear_kb = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text='2025', url = 'https://ufin48.ru/Show/File/7655?ParentItemId=218')
    ],
        [
        InlineKeyboardButton(text='2024', url = 'http://ufin48.ru/Show/File/6876?ParentItemId=218')
    ],    [
        InlineKeyboardButton(text='2023', url = 'http://ufin48.ru/Show/File/6877?ParentItemId=218')
    ],
    [
    InlineKeyboardButton(text='Главное меню', callback_data= 'start')
    ]
    ])