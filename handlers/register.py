from aiogram import Bot
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
import os
import re
from state.register import RegisterState
from utils.database_user import Database
from keybords.launch import start

async def start_register(message: Message, state: FSMContext, bot: Bot):
    await bot.send_message(message.from_user.id, f'▫️Укажите свое имя')
    await state.set_state(RegisterState.regName)
async def register_name(message: Message, state: FSMContext, bot: Bot):
    await bot.send_message(message.from_user.id, f' Приятно познакомиться, {message.text}\n Укажите контактный номер для обратной связи ')
    await state.update_data(regname= message.text)
    await state.set_state(RegisterState.regPhone)

async def register_phone(message: Message, state: FSMContext, bot: Bot):
    if(re.findall('^\+?[7][-\(]?\d{3}\)?-?\d{3}-?\d{2}-?\d{2}$', message.text)):
        await state.update_data(regphone = message.text)
        await bot.send_message(message.from_user.id, f'Ваш номер телефона, {message.text}\n▫️А теперь укажите организацию')
        await state.set_state(RegisterState.regOrg)
        
    else:
        await bot.send_message(message.from_user.id, f'Номер указан в неверном формате\nПопробуй еще раз')

async def register_organization(message: Message, state: FSMContext, bot: Bot):
    await state.update_data(regorg = message.text)
    reg_data = await state.get_data()
    reg_name = reg_data.get('regname')
    reg_phone = reg_data.get('regphone')
    register_organization = reg_data.get('regorg')
    await bot.send_message(message.from_user.id, f' {reg_name}, ваш номер телефона:{reg_phone}\n ваша организация: {register_organization}', reply_markup=start)
    db = Database(os.getenv('DATABASE_NAME'))
    db.add_users(reg_name, reg_phone, register_organization, message.from_user.id, message.from_user.username)
    await state.clear()