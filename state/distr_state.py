from aiogram.fsm.state import StatesGroup, State

class DistrState(StatesGroup):
    mainDist = State()
    profilesState = State()
    yearState = State ()