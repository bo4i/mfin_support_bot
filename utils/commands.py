from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeDefault


async def set_commands(bot: Bot):
    commands = [
        BotCommand(
            command='start',
            description = 'Запускаем бота'
        ), 
        BotCommand(
            command='help',
            description= 'Помощь'
        ), 
        BotCommand(
            command='profile',
            description= 'Информация о вашем профиле'
        )
    ]
    await bot.set_my_commands(commands, BotCommandScopeDefault())