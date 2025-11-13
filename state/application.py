from aiogram.fsm.state import StatesGroup, State

class ApplicationState(StatesGroup):
    regApp = State()
    regImage = State()
    Notification = State()
