from aiogram import Bot
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
import os

from utils.database_request import Database_request
from utils.database_user import Database


from keybords.accept_kb import accept
from keybords.register_kb import register
from state.application import ApplicationState

admin_id = os.getenv('ADMIN_ID')
admin_1 = os.getenv('ADMIN_1')
async def create_application(message: Message, state: FSMContext, bot: Bot):
    db = Database(os.getenv('DATABASE_NAME'))
    user = db.select_users_id(message.from_user.id)
    if(user):
        await bot.send_message(message.from_user.id, f'Опишите свою проблему')
        await state.set_state(ApplicationState.regApp)      

    else:
        await bot.send_message(message.from_user.id, f'Пройти регистрацию', reply_markup=register)

async def create_problem(message: Message, state: FSMContext, bot: Bot):
    await bot.send_message(message.from_user.id, f'Мы записали вашу проблему, ожидайте!')
    await state.update_data(regproblem= message.text)
    reg_data = await state.get_data()
    reg_problem = reg_data.get('regproblem')
    db_request = Database_request(os.getenv('DATABASE_REQUEST'))
    db_request.add_problem(reg_problem, message.from_user.id)
    problem = db_request.select_problem(message.from_user.id)
    await state.clear()
    await bot.send_message(admin_id, text= f' новую заявку: \n {problem}', reply_markup=accept)
    #await bot.send_message(admin_1, text= f' новую заявку: \n {problem}', reply_markup=accept)
async def accept_application(message:Message, bot: Bot):
    db_request = Database_request(os.getenv('DATABASE_REQUEST'))
    db_request.edit_status()
    
    await bot.send_message(admin_id, text = f'Вы приняли заявку')

async def send_notification(message:Message, state: FSMContext, bot: Bot):
    db_request = Database_request(os.getenv('DATABASE_REQUEST'))
    db_users = Database(os.getenv('DATABASE_NAME'))


