from aiogram import Bot
from aiogram.types import Message

async def my_profile(message:Message, bot: Bot):
    await bot.send_message(message.from_user.id, f'Здесь будет указаны заполненные данные')