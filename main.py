from aiogram import Bot, Dispatcher, F, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Message, CallbackQuery
import asyncio
from dotenv import load_dotenv
import os
from aiogram.filters import Command



from utils.commands import set_commands
from handlers.start import start_bot, get_start, get_start_again
from handlers.newapp import create_application,create_problem, send_notification, accept_application
from handlers.dist import choose_dist, choose_profile, choose_munyear, choose_oblyear
from handlers.register import start_register, register_name, register_phone, register_organization
from handlers.profile import my_profile
from utils.database_request import Database_request
from state.register import RegisterState
from state.application import ApplicationState
#загрузка окружения .env из операционной системы
load_dotenv()
token = os.getenv('TOKEN')
bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

#Стартовое меню
dp.startup.register(start_bot)
#Отработка команды /start
dp.message.register(get_start, Command(commands= 'start'))
dp.callback_query.register(get_start_again, F.data == 'start')
dp.message.register(my_profile,Command(commands='profile'))

#Обработчик раздела создать заявку
dp.callback_query.register(create_application, F.data == 'new_application')
dp.message.register(create_problem, ApplicationState.regApp)
dp.message.register(send_notification, ApplicationState.Notification)
dp.callback_query.register(accept_application, F.data == 'accept')
dp.callback_query.register(get_start_again, F.data == 'refuse')
#Обработчик регистрации пользователя
dp.callback_query.register(start_register, F.data == 'register')
dp.message.register(register_name,RegisterState.regName)
dp.message.register(register_phone,RegisterState.regPhone)
dp.message.register(register_organization,RegisterState.regOrg)

#Обработчик раздела дистрибутивы
dp.callback_query.register(choose_dist,F.data == 'distr' )
dp.callback_query.register(choose_profile,F.data == 'profiles')
dp.callback_query.register(choose_oblyear,F.data== 'munbudg')
dp.callback_query.register(choose_munyear,F.data== 'oblbudg')

#Запуск бота
async def start():
    await set_commands(bot)
    try:
        await dp.start_polling(bot, skip_updates = True)
    finally:
        await bot.session.close()

if __name__ == '__main__':
    try:
            asyncio.run(start())
    except:
            print('Бот остановлен')

