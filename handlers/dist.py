from aiogram import Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from keybords.distr_kb import dist_kb, profile_kb, munyear_kb, oblyear_kb
from state.distr_state import DistrState

async def choose_dist(call: CallbackQuery, state: FSMContext, bot: Bot):
    await call.message.edit_text(f'Выберите, что вам нужно')
    await call.message.edit_reply_markup(reply_markup= dist_kb)
    await state.set_state(DistrState.mainDist)

async def choose_profile(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(f'Выберите нужный профиль!')
    await call.message.edit_reply_markup(reply_markup=profile_kb)
    await state.set_state(DistrState.profilesState)

async def choose_munyear(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(f'Выберите нужный год!')
    await call.message.edit_reply_markup(reply_markup=munyear_kb)
    await state.set_state(DistrState.yearState)


async def choose_oblyear(call: CallbackQuery, state:FSMContext, bot: Bot):
    await call.message.edit_text(f'Выберите нужный год!')
    await call.message.edit_reply_markup(reply_markup=oblyear_kb)
    await state.set_state(DistrState.yearState)