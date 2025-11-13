from aiogram import Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from dotenv import load_dotenv
import os

from keybords.launch import start
load_dotenv()

admin_id = os.getenv('ADMIN_ID')
admin_1 = os.getenv('ADMIN_1')

async def start_bot(bot: Bot):
    await bot.send_message(admin_id, text='Бот запущен')
#    await bot.send_message(admin_1, text='Бот запущен')

async def get_start(message:Message, bot: Bot):
    await bot.send_message(message.from_user.id,'Добро пожаловать в систему оказания технической помощи и поддержки пользователей портала бюджетной системы ЛО ', reply_markup = start)

async def get_start_again(call: CallbackQuery, state:FSMContext, bot: Bot):
    await call.message.edit_text(f'Добро пожаловать в систему оказания технической помощи и поддержки пользователей портала бюджетной системы ЛО ')
    await call.message.edit_reply_markup(reply_markup = start)
