import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.exc import IntegrityError
from dotenv import load_dotenv
import os
from aiogram.fsm.storage.base import StorageKey
# Загрузка переменных окружения из .env файла
load_dotenv()

# --- Конфигурация бота ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения. Создайте файл .env с BOT_TOKEN=ВАШ_ТОКЕН_БОТА")

# ID администраторов (замените на реальные ID пользователей Telegram)
# Эти ID будут использоваться для инициализации таблицы Admin
IT_ADMIN_IDS = [721618593]  # Пример: ID IT-админов
AHO_ADMIN_IDS = [721618593] # Пример: ID АХО-админов
# Список всех предопределенных организаций для выбора
PREDEFINED_ORGANIZATIONS = [
    "Министерство финансов Липецкой области",
    "ОКУ «Центра бухгалтерского учета» г.Липецк",
    # Добавьте сюда другие предопределенные организации, если они появятся
]

# Список организаций, для которых нужен номер кабинета (используем set для быстрого поиска)
ORGANIZATIONS_NEEDING_OFFICE_NUMBER = set([
    "Министерство финансов Липецкой области",
    "ОКУ «Центра бухгалтерского учета» г.Липецк"
])

# --- Настройка логирования ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Настройка базы данных SQLAlchemy ---
DATABASE_URL = "sqlite:///./bot.db"
engine = create_engine(DATABASE_URL)
Base = declarative_base()


# Модели базы данных
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, unique=True)  # ID пользователя Telegram
    full_name = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    organization = Column(String, nullable=True)
    office_number = Column(String, nullable=True)  # Поле для номера кабинета
    registered = Column(Boolean, default=False)  # Флаг регистрации
    role = Column(String, default='user')  # 'user', 'it_admin', 'aho_admin'

    requests = relationship("Request", back_populates="creator")

    def __repr__(self):
        return f"<User(id={self.id}, full_name='{self.full_name}', registered={self.registered})>"


class Request(Base):
    __tablename__ = 'requests'
    id = Column(Integer, primary_key=True, autoincrement=True)  # Уникальный ID заявки
    user_id = Column(Integer, ForeignKey('users.id'))  # ID пользователя, создавшего заявку
    request_type = Column(String)  # 'IT', 'AHO'
    description = Column(String)
    urgency = Column(String)  # 'ASAP' (Как можно скорее), 'DATE' (Указать дату)
    due_date = Column(String, nullable=True)  # Желаемая дата выполнения (если выбрана 'DATE')
    status = Column(String, default='Принято')  # 'Принято', 'Принято к исполнению', 'Выполнено', 'Уточнение'
    assigned_admin_id = Column(Integer, nullable=True)  # ID администратора, принявшего заявку
    created_at = Column(DateTime, default=datetime.now)  # Дата и время создания заявки
    completed_at = Column(DateTime, nullable=True)  # Дата и время выполнения заявки
    admin_message_id = Column(Integer, nullable=True)  # ID сообщения администратору для обновления

    creator = relationship("User", back_populates="requests")

    def __repr__(self):
        return f"<Request(id={self.id}, type='{self.request_type}', status='{self.status}')>"


class Admin(Base):
    __tablename__ = 'admins'
    id = Column(Integer, primary_key=True, unique=True)  # ID администратора Telegram
    admin_type = Column(String)  # 'IT_ADMIN', 'AHO_ADMIN'

    def __repr__(self):
        return f"<Admin(id={self.id}, type='{self.admin_type}')>"


# Создание таблиц в базе данных
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Функция для получения сессии БД
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Состояния для FSM ---
class RegistrationStates(StatesGroup):
    waiting_for_full_name = State() #Состояние для ввода имени
    waiting_for_phone_number = State() #Состояние для ввода телефона
    waiting_for_organization_choice = State()  # Состояние для выбора организации
    waiting_for_manual_organization_input = State()  # Состояние для ручного ввода организации
    waiting_for_office_number = State() #Состояние для ввода номера кабинета


class NewRequestStates(StatesGroup):
    waiting_for_description = State() #Состояние для ввода заявки
    waiting_for_urgency = State() #Состояние для указания срочности
    waiting_for_date = State() #Состояние для ввода даты
    request_type = State()  # 'IT' or 'AHO'


class ClarificationState(StatesGroup):
    # Состояния для двустороннего диалога уточнения
    # Обе стороны будут находиться в соответствующем состоянии, пока диалог активен
    admin_active_dialogue = State()
    user_active_dialogue = State()


# --- Клавиатуры ---

# Главное меню
def get_main_menu_keyboard(user_role: str) -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="Создать ИТ-заявку"), KeyboardButton(text="Создать АХО-заявку")],
        [KeyboardButton(text="Портал бюджетной системы Липецкой области", url="https://ufin48.ru/")],
    ]
    if user_role == 'user':
        keyboard.append([KeyboardButton(text="Мои заявки")])
    elif user_role in ['it_admin', 'aho_admin']:
        keyboard.append([KeyboardButton(text="Мои принятые заявки")])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=False)


# Выбор срочности заявки
def get_urgency_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="Как можно скорее", callback_data="urgency_asap")],
        [InlineKeyboardButton(text="Указать дату", callback_data="urgency_date")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# Кнопки для администратора при новой заявке
def get_admin_new_request_keyboard(request_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="Принять", callback_data=f"admin_accept_{request_id}")],
        [InlineKeyboardButton(text="Отправить уточнение", callback_data=f"admin_clarify_start_{request_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# Кнопка "Выполнено" для администратора
def get_admin_done_keyboard(request_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="Выполнено", callback_data=f"admin_done_{request_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# Кнопки для администратора во время активного диалога уточнения
def get_admin_clarify_active_keyboard(request_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="Завершить уточнение", callback_data=f"admin_clarify_end_{request_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# Кнопки для администратора после завершения диалога уточнения (только "Принять")
def get_admin_post_clarification_keyboard(request_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="Принять", callback_data=f"admin_accept_{request_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# Кнопки для пользователя в разделе "Мои заявки"
def get_user_request_actions_keyboard(request_id: int, status: str) -> InlineKeyboardMarkup:
    buttons = []
    if status != "Выполнено":
        buttons.append([InlineKeyboardButton(text="Отметить как выполнено", callback_data=f"user_done_{request_id}")])
    buttons.append([InlineKeyboardButton(text="Задать уточнение", callback_data=f"user_clarify_start_{request_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# Кнопки для пользователя во время активного диалога уточнения
def get_user_clarify_active_keyboard(request_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="Завершить уточнение", callback_data=f"user_clarify_end_{request_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# Клавиатура для выбора организации
def get_organization_selection_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    for i, org in enumerate(PREDEFINED_ORGANIZATIONS):
        # Используем индекс в callback_data для сокращения длины
        buttons.append([InlineKeyboardButton(text=org, callback_data=f"org_idx_{i}")])
    buttons.append([InlineKeyboardButton(text="Указать название самостоятельно", callback_data="org_other")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# --- Хендлеры ---

# Инициализация роутеров
router = Dispatcher()


# --- Хендлер команды /start ---
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    db = next(get_db())
    user = db.query(User).filter(User.id == message.from_user.id).first()

    # Очищаем все активные состояния при /start
    await state.clear()

    if not user:
        new_user = User(id=message.from_user.id)
        db.add(new_user)
        try:
            db.commit()
            db.refresh(new_user)
            logger.info(f"Новый пользователь {message.from_user.id} добавлен в БД.")
        except IntegrityError:
            db.rollback()
            logger.warning(
                f"Пользователь {message.from_user.id} уже существует, но не был найден в начале сессии. Продолжаем.")
            user = db.query(User).filter(User.id == message.from_user.id).first()
            if not user:
                await message.answer("Произошла ошибка при инициализации пользователя. Попробуйте еще раз.")
                return

        await message.answer(
            "Добро пожаловать! Для использования бота необходимо зарегистрироваться. Укажите ваше ФИО:")
        await state.set_state(RegistrationStates.waiting_for_full_name)
    elif not user.registered:
        await message.answer("Вы не завершили регистрацию. Пожалуйста, укажите ваше ФИО:")
        await state.set_state(RegistrationStates.waiting_for_full_name)
    else:
        await message.answer("С возвращением! Главное меню:", reply_markup=get_main_menu_keyboard(user.role))
        await state.clear()


# --- Хендлеры регистрации ---
@router.message(RegistrationStates.waiting_for_full_name)
async def process_full_name(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("Пожалуйста, введите ваше ФИО текстом.")
        return
    await state.update_data(full_name=message.text)
    await message.answer("Отлично! Теперь укажите ваш номер телефона:")
    await state.set_state(RegistrationStates.waiting_for_phone_number)


@router.message(RegistrationStates.waiting_for_phone_number)
async def process_phone_number(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("Пожалуйста, введите ваш номер телефона текстом.")
        return
    await state.update_data(phone_number=message.text)
    try:
        await message.answer("Пожалуйста, выберите вашу организацию из списка или введите название самостоятельно:",
                             reply_markup=get_organization_selection_keyboard())
        await state.set_state(RegistrationStates.waiting_for_organization_choice)
    except Exception as e:
        logger.error(f"Ошибка при отправке клавиатуры выбора организации: {e}")
        await message.answer("Произошла ошибка при запросе организации. Пожалуйста, попробуйте еще раз.")
        await state.clear()  # Очищаем состояние, чтобы пользователь мог начать заново


# Хендлер для выбора организации из инлайн-клавиатуры
@router.callback_query(RegistrationStates.waiting_for_organization_choice, F.data.startswith("org_idx_"))
async def process_organization_selection(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.answer()
    org_index = int(callback_query.data.split('_')[2])

    if 0 <= org_index < len(PREDEFINED_ORGANIZATIONS):
        organization_name = PREDEFINED_ORGANIZATIONS[org_index]
        await state.update_data(organization=organization_name)

        # Редактируем сообщение, чтобы убрать клавиатуру и показать выбранную организацию
        try:
            await callback_query.message.edit_text(f"Вы выбрали: {organization_name}")

            if organization_name in ORGANIZATIONS_NEEDING_OFFICE_NUMBER:
                await callback_query.message.answer("Пожалуйста, укажите номер кабинета:")
                await state.set_state(RegistrationStates.waiting_for_office_number)
            else:
                await complete_registration(callback_query.message, state)  # Завершаем регистрацию
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения после выбора организации: {e}")
            await callback_query.message.answer(
                "Произошла ошибка при обработке выбора организации. Пожалуйста, попробуйте еще раз.")
            await state.clear()
    else:
        await callback_query.message.answer("Произошла ошибка при выборе организации. Пожалуйста, попробуйте снова.")
        await state.clear()


# Хендлер для кнопки "Указать название самостоятельно"
@router.callback_query(RegistrationStates.waiting_for_organization_choice, F.data == "org_other")
async def process_other_organization_selection(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.answer()
    try:
        # Редактируем сообщение, чтобы убрать клавиатуру и запросить ручной ввод
        await callback_query.message.edit_text("Пожалуйста, введите название вашей организации вручную:")
        await state.set_state(RegistrationStates.waiting_for_manual_organization_input)
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения после выбора 'Указать название самостоятельно': {e}")
        await callback_query.message.answer(
            "Произошла ошибка при запросе ручного ввода организации. Пожалуйста, попробуйте еще раз.")
        await state.clear()


# Хендлер для ручного ввода организации
@router.message(RegistrationStates.waiting_for_manual_organization_input)
async def process_manual_organization_input(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("Пожалуйста, введите название вашей организации текстом.")
        return

    organization_name = message.text.strip()
    await state.update_data(organization=organization_name)

    # Если ручной ввод, номер кабинета не запрашивается
    await complete_registration(message, state)


@router.message(RegistrationStates.waiting_for_office_number)
async def process_office_number(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("Пожалуйста, введите номер кабинета текстом.")
        return
    await state.update_data(office_number=message.text)
    await complete_registration(message, state)


async def complete_registration(message: Message, state: FSMContext):
    user_data = await state.get_data()
    db = next(get_db())
    user = db.query(User).filter(User.id == message.from_user.id).first()

    if user:
        user.full_name = user_data.get('full_name')
        user.phone_number = user_data.get('phone_number')
        user.organization = user_data.get('organization')
        # Убедимся, что office_number устанавливается только если он был запрошен и введен
        user.office_number = user_data.get('office_number') if 'office_number' in user_data else None
        user.registered = True
        db.commit()
        logger.info(f"Пользователь {user.id} успешно зарегистрирован.")
        await message.answer("Регистрация завершена! Теперь вы можете создавать заявки.",
                             reply_markup=get_main_menu_keyboard(user.role))
        await state.clear()
    else:
        await message.answer(
            "Произошла ошибка при сохранении данных. Пожалуйста, попробуйте начать регистрацию заново (/start).")
        await state.clear()


# --- Хендлеры создания заявок ---
@router.message(F.text == "Создать ИТ-заявку")
@router.message(F.text == "Создать АХО-заявку")
async def start_new_request(message: Message, state: FSMContext):
    db = next(get_db())
    user = db.query(User).filter(User.id == message.from_user.id).first()

    if not user or not user.registered:
        await message.answer(
            "Вы не зарегистрированы или регистрация не завершена. Пожалуйста, начните с команды /start.")
        return

    request_type = "IT" if message.text == "Создать ИТ-заявку" else "AHO"
    await state.update_data(request_type=request_type)
    await message.answer(f"Опишите вашу проблему для {request_type}-заявки:")
    await state.set_state(NewRequestStates.waiting_for_description)


@router.message(NewRequestStates.waiting_for_description)
async def process_description(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("Пожалуйста, введите описание проблемы текстом.")
        return
    await state.update_data(description=message.text)
    await message.answer("Как срочно необходимо выполнить заявку?", reply_markup=get_urgency_keyboard())
    await state.set_state(NewRequestStates.waiting_for_urgency)


@router.callback_query(NewRequestStates.waiting_for_urgency, F.data.in_({"urgency_asap", "urgency_date"}))
async def process_urgency_callback(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.answer()  # Убираем "часики" с кнопки
    if callback_query.data == "urgency_asap":
        await state.update_data(urgency="ASAP")
        await save_request(callback_query.message, state, callback_query.from_user.id, bot=callback_query.bot)
    elif callback_query.data == "urgency_date":
        await state.update_data(urgency="DATE")
        await callback_query.message.answer(
            "Укажите желаемую дату и время выполнения заявки (например, 2025-12-31 10:00):")
        await state.set_state(NewRequestStates.waiting_for_date)


@router.message(NewRequestStates.waiting_for_date)
async def process_date(message: Message, state: FSMContext):
    try:
        datetime.strptime(message.text, "%Y-%m-%d %H:%M")
        await state.update_data(due_date=message.text)
        await save_request(message, state, message.from_user.id, bot=message.bot)
    except ValueError:
        await message.answer(
            "Неверный формат даты и времени. Пожалуйста, используйте формат ГГГГ-ММ-ДД ЧЧ:ММ (например, 2025-12-31 10:00).")


async def save_request(message: Message, state: FSMContext, user_id: int, bot: Bot):
    user_data = await state.get_data()
    request_type = user_data.get('request_type')
    description = user_data.get('description')
    urgency = user_data.get('urgency')
    due_date = user_data.get('due_date') if urgency == "DATE" else None

    db = next(get_db())
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        await message.answer("Произошла ошибка: пользователь не найден. Пожалуйста, попробуйте начать заново (/start).")
        await state.clear()
        return

    new_request = Request(
        user_id=user_id,
        request_type=request_type,
        description=description,
        urgency=urgency,
        due_date=due_date,
        status="Принято"
    )
    db.add(new_request)
    db.commit()
    db.refresh(new_request)  # Обновляем объект, чтобы получить сгенерированный ID

    await message.answer("Ваша заявка успешно создана и будет рассмотрена.")
    await state.clear()

    # Уведомление администраторов
    await notify_admins(db, new_request, user, bot)
    logger.info(f"Заявка ID:{new_request.id} от пользователя {user.id} создана и отправлена администраторам.")


async def notify_admins(db_session, request: Request, user: User, bot: Bot):
    # Определяем тип администраторов для уведомления
    admin_type_filter = 'IT_ADMIN' if request.request_type == 'IT' else 'AHO_ADMIN'

    # Получаем ID администраторов из таблицы Admin
    admin_ids_to_notify = [admin.id for admin in
                           db_session.query(Admin).filter(Admin.admin_type == admin_type_filter).all()]

    user_details = f"📞 Телефон: {user.phone_number}\n🏢 Организация: {user.organization}"
    if user.office_number:
        user_details += f"\n🚪 Кабинет: {user.office_number}"

    request_info = (
        f"🚨 Новая заявка ({request.request_type}) от {user.full_name} 🚨\n"
        f"{user_details}\n"
        f"📝 Описание: {request.description}\n"
        f"⏰ Срочность: {'Как можно скорее' if request.urgency == 'ASAP' else f'К {request.due_date}'}\n"
        f"🆔 Заявка ID: {request.id}"
    )

    keyboard = get_admin_new_request_keyboard(request.id)

    for admin_id in admin_ids_to_notify:
        try:
            sent_message = await bot.send_message(chat_id=admin_id, text=request_info, reply_markup=keyboard)
            # Сохраняем ID сообщения, отправленного администратору, для последующего редактирования
            request.admin_message_id = sent_message.message_id
            db_session.commit()
            logger.info(f"Уведомление о заявке {request.id} отправлено администратору {admin_id}.")
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление администратору {admin_id} о заявке {request.id}: {e}")


# --- Хендлеры действий администраторов ---
@router.callback_query(F.data.startswith("admin_accept_"))
async def admin_accept_request(callback_query: CallbackQuery, bot: Bot):
    await callback_query.answer()
    request_id = int(callback_query.data.split('_')[2])
    admin_id = callback_query.from_user.id

    db = next(get_db())
    request = db.query(Request).filter(Request.id == request_id).first()
    admin_user = db.query(User).filter(User.id == admin_id).first()

    if not request:
        await callback_query.message.answer("Заявка не найдена.")
        return

    if request.status != "Принято":
        await callback_query.message.answer(f"Эта заявка уже имеет статус: {request.status}.")
        return

    request.status = "Принято к исполнению"
    request.assigned_admin_id = admin_id
    db.commit()
    logger.info(f"Заявка ID:{request.id} принята к исполнению администратором {admin_id}.")

    # Обновляем сообщение администратору
    try:
        await callback_query.message.edit_text(
            f"{callback_query.message.text}\n\n✅ Статус: Принято к исполнению ({admin_user.full_name})",
            reply_markup=None  # Убираем кнопки после принятия
        )
    except Exception as e:
        logger.error(f"Не удалось обновить сообщение администратору для заявки {request.id}: {e}")

    # Уведомляем пользователя
    user_full_name = admin_user.full_name if admin_user else "Неизвестный администратор"
    try:
        await bot.send_message(
            chat_id=request.user_id,
            text=f"Ваша заявка ID:{request.id} ({request.description[:50]}...) принята к исполнению.\n"
                 f"Исполнитель: {user_full_name}."
        )
    except Exception as e:
        logger.error(f"Не удалось уведомить пользователя {request.user_id} о принятии заявки {request.id}: {e}")


@router.callback_query(F.data.startswith("admin_clarify_start_"))
async def admin_clarify_start(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    await callback_query.answer()
    request_id = int(callback_query.data.split('_')[3])
    admin_id = callback_query.from_user.id

    db = next(get_db())
    request = db.query(Request).filter(Request.id == request_id).first()

    if not request:
        await callback_query.message.answer("Заявка не найдена.")
        return

    if request.status == "Выполнено":
        await callback_query.message.answer("Эта заявка уже выполнена.")
        return

    # Сохраняем данные для диалога уточнения в состоянии администратора
    await state.update_data(
        target_user_id=request.user_id,
        request_id=request_id,
        original_admin_message_id=callback_query.message.message_id
    )
    await state.set_state(ClarificationState.admin_active_dialogue)

    # Устанавливаем состояние для пользователя, чтобы он мог отвечать
    # Создаем новый StorageKey для прямого чата с пользователем
    user_state = FSMContext(storage=state.storage,
                            key=StorageKey(bot_id=bot.id, chat_id=request.user_id, user_id=request.user_id))
    await user_state.update_data(
        target_admin_id=admin_id,  # Сохраняем ID администратора, чтобы пользователь знал, кому отвечать
        request_id=request_id
    )
    await user_state.set_state(ClarificationState.user_active_dialogue)

    # Обновляем статус заявки и назначаем администратора, если это первое уточнение
    if not request.assigned_admin_id:  # Если админ еще не был назначен
        request.assigned_admin_id = admin_id
    request.status = "Уточнение"
    db.commit()
    logger.info(f"Администратор {admin_id} начал уточнение для заявки {request.id}. Статус: Уточнение.")

    # Уведомляем пользователя о начале диалога
    try:
        await bot.send_message(
            chat_id=request.user_id,
            text=f"Администратор начал диалог по вашей заявке ID:{request.id} ({request.description[:50]}...).\n"
                 "Вы можете отправлять сообщения в ответ."
        )
    except Exception as e:
        logger.error(f"Не удалось уведомить пользователя {request.user_id} о начале диалога уточнения: {e}")

    await callback_query.message.answer(
        "Вы начали диалог уточнения с пользователем. Отправляйте сообщения. "
        "Для завершения диалога нажмите кнопку:",
        reply_markup=get_admin_clarify_active_keyboard(request_id)
    )


# Хендлер для сообщений от администратора во время активного диалога уточнения
@router.message(StateFilter(ClarificationState.admin_active_dialogue))
async def process_admin_clarification_message(message: Message, state: FSMContext, bot: Bot):
    if not message.text:
        # Не выводим сообщение, если это не текст (например, стикер, фото)
        # await message.answer("Пожалуйста, введите сообщение текстом.")
        return

    state_data = await state.get_data()
    target_user_id = state_data.get('target_user_id')
    request_id = state_data.get('request_id')

    if not target_user_id or not request_id:
        await message.answer(
            "Произошла ошибка в диалоге уточнения. Пожалуйста, попробуйте начать снова или используйте /start.")
        await state.clear()
        return

    db = next(get_db())
    request = db.query(Request).filter(Request.id == request_id).first()

    try:
        # Отправляем сообщение пользователю
        await bot.send_message(
            chat_id=target_user_id,
            text=f"💬 От администратора по заявке ID:{request.id} ({request.description[:50] if request else '...'})\n\n"
                 f"{message.text}"
        )
        # Удалено: await message.answer("Сообщение отправлено.") - чтобы не дублировать сообщения
    except Exception as e:
        await message.answer("Не удалось отправить сообщение пользователю. Возможно, он заблокировал бота.")
        logger.error(f"Не удалось отправить сообщение пользователю {target_user_id} для заявки {request.id}: {e}")


@router.callback_query(F.data.startswith("admin_clarify_end_"))
async def admin_clarify_end(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    await callback_query.answer()
    request_id = int(callback_query.data.split('_')[3])
    admin_id = callback_query.from_user.id

    state_data = await state.get_data()
    target_user_id = state_data.get('target_user_id')
    original_admin_message_id = state_data.get('original_admin_message_id')

    db = next(get_db())
    request = db.query(Request).filter(Request.id == request_id).first()
    user_creator = db.query(User).filter(User.id == request.user_id).first()  # Fetch the user who created the request

    # Очищаем состояние администратора
    await state.clear()
    await callback_query.message.answer("Диалог уточнения завершен.")

    # Очищаем состояние пользователя, если он был в этом диалоге
    if target_user_id:
        user_state = FSMContext(storage=state.storage,
                                key=StorageKey(bot_id=bot.id, chat_id=target_user_id, user_id=target_user_id))
        current_user_state = await user_state.get_state()
        user_state_data = await user_state.get_data()
        if current_user_state == ClarificationState.user_active_dialogue and user_state_data.get(
                'request_id') == request_id:
            await user_state.clear()
            logger.info(f"Состояние пользователя {target_user_id} очищено после завершения диалога администратором.")
            try:
                await bot.send_message(
                    chat_id=target_user_id,
                    text=f"Мы поняли вашу проблему по заявке ID:{request.id} ({request.description[:50] if request else '...'}), ожидайте ее выполнение."
                )
            except Exception as e:
                logger.error(f"Не удалось уведомить пользователя {target_user_id} о завершении диалога: {e}")

    # Обновляем статус заявки на "Принято к исполнению"
    if request:
        request.status = "Принято к исполнению"
        db.commit()
        logger.info(
            f"Статус заявки {request.id} изменен с 'Уточнение' на 'Принято к исполнению' после завершения диалога.")

        # Реконструируем сообщение для администратора с обновленным статусом
        user_details = f"📞 Телефон: {user_creator.phone_number}\n🏢 Организация: {user_creator.organization}"
        if user_creator.office_number:
            user_details += f"\n🚪 Кабинет: {user_creator.office_number}"

        request_info = (
            f"🚨 Заявка ({request.request_type}) от {user_creator.full_name} 🚨\n"
            f"{user_details}\n"
            f"📝 Описание: {request.description}\n"
            f"⏰ Срочность: {'Как можно скорее' if request.urgency == 'ASAP' else f'К {request.due_date}'}\n"
            f"🆔 Заявка ID: {request.id}\n\n"
            f"✅ Статус: {request.status}"  # Обновленный статус
        )
        # После завершения уточнения и перехода в "Принято к исполнению", кнопки убираются
        # (или можно показать кнопку "Выполнено", если администратор уже принял ее к исполнению)
        keyboard = get_admin_done_keyboard(request.id)  # Теперь сразу предлагаем завершить

        if original_admin_message_id:
            try:
                await bot.edit_message_text(
                    chat_id=callback_query.message.chat.id,
                    message_id=original_admin_message_id,
                    text=request_info,
                    reply_markup=keyboard
                )
                logger.info(f"Сообщение администратору для заявки {request.id} обновлено после завершения диалога.")
            except Exception as e:
                logger.error(
                    f"Не удалось обновить сообщение администратору после завершения диалога для заявки {request.id}: {e}")
    else:
        logger.warning(f"Заявка {request_id} не найдена при попытке завершить диалог уточнения.")


@router.message(F.text == "Мои принятые заявки")
async def show_assigned_requests(message: Message):
    db = next(get_db())
    admin_id = message.from_user.id
    admin_user = db.query(User).filter(User.id == admin_id).first()

    if not admin_user or admin_user.role not in ['it_admin', 'aho_admin']:
        await message.answer("У вас нет доступа к этой функции.")
        return

    two_days_ago = datetime.now() - timedelta(days=2)

    requests = db.query(Request).filter(
        Request.assigned_admin_id == admin_id,
        (Request.status != "Выполнено") | (Request.completed_at >= two_days_ago)  # Фильтрация по дате для выполненных
    ).order_by(Request.created_at.desc()).all()

    if not requests:
        await message.answer("У вас пока нет принятых к исполнению заявок или недавно выполненных.")
        return

    for req in requests:
        user = db.query(User).filter(User.id == req.user_id).first()
        user_info = f"{user.full_name}, {user.organization}, {user.phone_number}"
        if user and user.office_number:
            user_info += f", каб. {user.office_number}"

        request_text = (
            f"--- Заявка ID: {req.id} ({req.request_type}) ---\n"
            f"От: {user_info}\n"
            f"Описание: {req.description}\n"
            f"Срочность: {'Как можно скорее' if req.urgency == 'ASAP' else f'К {req.due_date}'}\n"
            f"Статус: {req.status}"
        )

        keyboard_to_show = None
        if req.status == "Принято":
            keyboard_to_show = get_admin_new_request_keyboard(req.id)  # Принять/Отправить уточнение
        elif req.status == "Принято к исполнению":
            keyboard_to_show = get_admin_done_keyboard(req.id)  # Выполнено
        elif req.status == "Уточнение":
            keyboard_to_show = get_admin_clarify_active_keyboard(req.id)  # Завершить уточнение
        # Для выполненных заявок (в рамках 2 дней) кнопки не отображаются

        await message.answer(request_text, reply_markup=keyboard_to_show)


@router.callback_query(F.data.startswith("admin_done_"))
async def admin_done_request(callback_query: CallbackQuery, bot: Bot):
    await callback_query.answer()
    request_id = int(callback_query.data.split('_')[2])
    admin_id = callback_query.from_user.id

    db = next(get_db())
    request = db.query(Request).filter(Request.id == request_id).first()
    admin_user = db.query(User).filter(User.id == admin_id).first()

    if not request:
        await callback_query.message.answer("Заявка не найдена.")
        return

    if request.assigned_admin_id != admin_id:
        await callback_query.message.answer("Вы не являетесь исполнителем этой заявки.")
        return

    if request.status == "Выполнено":
        await callback_query.message.answer("Эта заявка уже отмечена как выполненная.")
        return

    request.status = "Выполнено"
    request.completed_at = datetime.now()  # Устанавливаем время выполнения
    db.commit()
    logger.info(f"Заявка ID:{request.id} отмечена как 'Выполнено' администратором {admin_id}.")

    # Обновляем сообщение администратору
    try:
        await callback_query.message.edit_text(
            f"{callback_query.message.text}\n\n✅ Статус: Выполнено",
            reply_markup=None  # Убираем кнопки после выполнения
        )
    except Exception as e:
        logger.error(f"Не удалось обновить сообщение администратору для заявки {request.id}: {e}")

    # Уведомляем пользователя
    try:
        await bot.send_message(
            chat_id=request.user_id,
            text=f"🎉 Ваша заявка ID:{request.id} ({request.description[:50]}...) исполнена!"
        )
    except Exception as e:
        logger.error(f"Не удалось уведомить пользователя {request.user_id} о выполнении заявки {request.id}: {e}")


# --- Хендлеры действий пользователей ---
@router.message(F.text == "Мои заявки")
async def show_user_requests(message: Message):
    db = next(get_db())
    user_id = message.from_user.id
    user = db.query(User).filter(User.id == user_id).first()

    if not user or not user.registered:
        await message.answer(
            "Вы не зарегистрированы или регистрация не завершена. Пожалуйста, начните с команды /start.")
        return

    two_days_ago = datetime.now() - timedelta(days=2)

    requests = db.query(Request).filter(
        Request.user_id == user_id,
        (Request.status != "Выполнено") | (Request.completed_at >= two_days_ago)  # Фильтрация по дате для выполненных
    ).order_by(Request.created_at.desc()).all()

    if not requests:
        await message.answer("У вас пока нет созданных заявок.")
        return

    for req in requests:
        admin_info = ""
        if req.assigned_admin_id:
            admin_user = db.query(User).filter(User.id == req.assigned_admin_id).first()
            if admin_user:
                admin_info = f"Исполнитель: {admin_user.full_name}\n"

        response_text = (
            f"--- Заявка ID: {req.id} ({req.request_type}) ---\n"
            f"Описание: {req.description}\n"
            f"Срочность: {'Как можно скорее' if req.urgency == 'ASAP' else f'К {req.due_date}'}\n"
            f"Статус: {req.status}\n"
            f"{admin_info}"
            f"Создана: {req.created_at.strftime('%Y-%m-%d %H:%M')}\n"
        )
        if req.status == "Выполнено" and req.completed_at:
            response_text += f"Выполнена: {req.completed_at.strftime('%Y-%m-%d %H:%M')}\n"

        # Добавляем кнопки, если заявка не выполнена или выполнена недавно
        if req.status != "Выполнено" or (
                req.status == "Выполнено" and req.completed_at and req.completed_at >= two_days_ago):
            await message.answer(response_text, reply_markup=get_user_request_actions_keyboard(req.id, req.status))
        else:
            await message.answer(response_text)


@router.callback_query(F.data.startswith("user_done_"))
async def user_mark_done_request(callback_query: CallbackQuery, bot: Bot):
    await callback_query.answer()
    request_id = int(callback_query.data.split('_')[2])
    user_id = callback_query.from_user.id

    db = next(get_db())
    request = db.query(Request).filter(Request.id == request_id, Request.user_id == user_id).first()

    if not request:
        await callback_query.message.answer("Заявка не найдена или вы не являетесь ее создателем.")
        return

    if request.status == "Выполнено":
        await callback_query.message.answer("Эта заявка уже отмечена как выполненная.")
        return

    request.status = "Выполнено"
    request.completed_at = datetime.now()  # Устанавливаем время выполнения
    db.commit()
    logger.info(f"Заявка ID:{request.id} отмечена пользователем {user_id} как 'Выполнено'.")

    # Обновляем сообщение пользователя
    try:
        await callback_query.message.edit_text(
            f"{callback_query.message.text}\n\n✅ Статус: Выполнено",
            reply_markup=None  # Убираем кнопки после выполнения
        )
    except Exception as e:
        logger.error(f"Не удалось обновить сообщение пользователя для заявки {request.id}: {e}")

    # Уведомляем администратора, если заявка была принята
    if request.assigned_admin_id:
        try:
            admin_user = db.query(User).filter(User.id == request.assigned_admin_id).first()
            if admin_user:
                await bot.send_message(
                    chat_id=request.assigned_admin_id,
                    text=f"🎉 Пользователь {request.creator.full_name} отметил заявку ID:{request.id} как выполненную!"
                )
        except Exception as e:
            logger.error(
                f"Не удалось уведомить администратора {request.assigned_admin_id} о выполнении заявки {request.id} пользователем: {e}")


@router.callback_query(F.data.startswith("user_clarify_start_"))
async def user_clarify_start(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    await callback_query.answer()
    request_id = int(callback_query.data.split('_')[3])
    user_id = callback_query.from_user.id

    db = next(get_db())
    request = db.query(Request).filter(Request.id == request_id, Request.user_id == user_id).first()

    if not request:
        await callback_query.message.answer("Заявка не найдена или вы не являетесь ее создателем.")
        return

    if not request.assigned_admin_id:
        await callback_query.message.answer("Эта заявка еще не принята администратором. Уточнение невозможно.")
        return

    # Сохраняем данные для диалога уточнения в состоянии пользователя
    await state.update_data(
        target_admin_id=request.assigned_admin_id,
        request_id=request_id,
        original_user_message_id=callback_query.message.message_id
    )
    await state.set_state(ClarificationState.user_active_dialogue)

    # Устанавливаем состояние для администратора, чтобы он мог отвечать
    # Создаем новый StorageKey для прямого чата с администратором
    admin_state = FSMContext(storage=state.storage,
                             key=StorageKey(bot_id=bot.id, chat_id=request.assigned_admin_id,
                                            user_id=request.assigned_admin_id))
    await admin_state.update_data(
        target_user_id=user_id,  # Сохраняем ID пользователя, чтобы администратор знал, кому отвечать
        request_id=request_id
    )
    await admin_state.set_state(ClarificationState.admin_active_dialogue)

    # Уведомляем администратора о начале диалога
    try:
        await bot.send_message(
            chat_id=request.assigned_admin_id,
            text=f"Пользователь {request.creator.full_name} начал диалог по заявке ID:{request.id} ({request.description[:50] if request else '...'}).\n"
                 "Вы можете отправлять сообщения в ответ."
        )
    except Exception as e:
        logger.error(
            f"Не удалось уведомить администратора {request.assigned_admin_id} о начале диалога уточнения от пользователя: {e}")

    await callback_query.message.answer(
        "Вы начали диалог уточнения с администратором. Отправляйте сообщения. "
        "Для завершения диалога нажмите кнопку:",
        reply_markup=get_user_clarify_active_keyboard(request_id)
    )


# Хендлер для сообщений от пользователя во время активного диалога уточнения
@router.message(StateFilter(ClarificationState.user_active_dialogue))
async def process_user_clarification_message(message: Message, state: FSMContext, bot: Bot):
    if not message.text:
        # Не выводим сообщение, если это не текст (например, стикер, фото)
        # await message.answer("Пожалуйста, введите сообщение текстом.")
        return

    state_data = await state.get_data()
    target_admin_id = state_data.get('target_admin_id')
    request_id = state_data.get('request_id')

    if not target_admin_id or not request_id:
        await message.answer(
            "Произошла ошибка в диалоге уточнения. Пожалуйста, попробуйте начать снова или используйте /start.")
        await state.clear()
        return

    db = next(get_db())
    request = db.query(Request).filter(Request.id == request_id).first()
    user = db.query(User).filter(User.id == message.from_user.id).first()

    try:
        # Отправляем сообщение администратору
        await bot.send_message(
            chat_id=target_admin_id,
            text=f"💬 От пользователя {user.full_name} по заявке ID:{request.id} ({request.description[:50] if request else '...'})\n\n"
                 f"{message.text}"
        )
        # Удалено: await message.answer("Сообщение отправлено администратору.") - чтобы не дублировать сообщения
    except Exception as e:
        await message.answer("Не удалось отправить сообщение администратору. Возможно, он заблокировал бота.")
        logger.error(f"Не удалось отправить сообщение администратору {target_admin_id} для заявки {request.id}: {e}")


@router.callback_query(F.data.startswith("user_clarify_end_"))
async def user_clarify_end(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    await callback_query.answer()
    request_id = int(callback_query.data.split('_')[3])
    user_id = callback_query.from_user.id

    state_data = await state.get_data()
    target_admin_id = state_data.get('target_admin_id')
    original_user_message_id = state_data.get('original_user_message_id')

    db = next(get_db())
    request = db.query(Request).filter(Request.id == request_id).first()

    # Очищаем состояние пользователя
    await state.clear()
    await callback_query.message.answer("Диалог уточнения завершен.")

    # Очищаем состояние администратора, если он был в этом диалоге
    if target_admin_id:
        admin_state = FSMContext(storage=state.storage,
                                 key=StorageKey(bot_id=bot.id, chat_id=target_admin_id, user_id=target_admin_id))
        current_admin_state = await admin_state.get_state()
        admin_state_data = await admin_state.get_data()
        if current_admin_state == ClarificationState.admin_active_dialogue and admin_state_data.get(
                'request_id') == request_id:
            await admin_state.clear()
            logger.info(f"Состояние администратора {target_admin_id} очищено после завершения диалога пользователем.")
            try:
                await bot.send_message(
                    chat_id=target_admin_id,
                    text=f"Диалог по заявке ID:{request.id} ({request.description[:50] if request else '...'}) завершен пользователем."
                )
            except Exception as e:
                logger.error(f"Не удалось уведомить администратора {target_admin_id} о завершении диалога: {e}")

    # Обновляем сообщение пользователя, чтобы убрать кнопки
    if original_user_message_id:
        try:
            await bot.edit_message_reply_markup(
                chat_id=callback_query.message.chat.id,
                message_id=original_user_message_id,
                reply_markup=None
            )
        except Exception as e:
            logger.error(
                f"Не удалось обновить сообщение пользователя после завершения диалога для заявки {request.id}: {e}")


@router.message(F.text == "Портал бюджетной системы Липецкой области")
async def send_website_link(message: Message):
    await message.answer("[Портал бюджетной системы Липецкой области](https://ufin48.ru)",
                         parse_mode="MarkdownV2")  # Замените на реальную ссылку


# --- Инициализация администраторов в БД при запуске бота ---
async def on_startup(dispatcher: Dispatcher, bot: Bot):
    db = next(get_db())

    # Добавляем IT-админов
    for admin_id in IT_ADMIN_IDS:
        admin_exists = db.query(Admin).filter(Admin.id == admin_id, Admin.admin_type == 'IT_ADMIN').first()
        if not admin_exists:
            db.add(Admin(id=admin_id, admin_type='IT_ADMIN'))
            # Также убедимся, что они есть в таблице users и имеют соответствующую роль
            user_exists = db.query(User).filter(User.id == admin_id).first()
            if not user_exists:
                db.add(User(id=admin_id, registered=True, role='it_admin', full_name=f"IT Admin {admin_id}",
                            phone_number="N/A", organization="N/A"))
            elif user_exists.role != 'it_admin':
                user_exists.role = 'it_admin'
                user_exists.registered = True  # Считаем админов зарегистрированными
            logger.info(f"IT-администратор {admin_id} добавлен/обновлен.")

    # Добавляем АХО-админов
    for admin_id in AHO_ADMIN_IDS:
        admin_exists = db.query(Admin).filter(Admin.id == admin_id, Admin.admin_type == 'AHO_ADMIN').first()
        if not admin_exists:
            db.add(Admin(id=admin_id, admin_type='AHO_ADMIN'))
            # Также убедимся, что они есть в таблице users и имеют соответствующую роль
            user_exists = db.query(User).filter(User.id == admin_id).first()
            if not user_exists:
                db.add(User(id=admin_id, registered=True, role='aho_admin', full_name=f"AHO Admin {admin_id}",
                            phone_number="N/A", organization="N/A"))
            elif user_exists.role != 'aho_admin':
                user_exists.role = 'aho_admin'
                user_exists.registered = True  # Считаем админов зарегистрированными
            logger.info(f"АХО-администратор {admin_id} добавлен/обновлен.")

    db.commit()
    db.close()
    logger.info("Администраторы успешно инициализированы в БД.")


# --- Главная функция запуска бота ---
async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    # Регистрация всех хендлеров
    dp.message.register(cmd_start, CommandStart())

    # Регистрация хендлеров регистрации
    dp.message.register(process_full_name, RegistrationStates.waiting_for_full_name)
    dp.message.register(process_phone_number, RegistrationStates.waiting_for_phone_number)

    # Хендлеры для выбора организации
    dp.callback_query.register(process_organization_selection, RegistrationStates.waiting_for_organization_choice,
                               F.data.startswith("org_idx_"))
    dp.callback_query.register(process_other_organization_selection, RegistrationStates.waiting_for_organization_choice,
                               F.data == "org_other")
    dp.message.register(process_manual_organization_input, RegistrationStates.waiting_for_manual_organization_input)

    dp.message.register(process_office_number, RegistrationStates.waiting_for_office_number)

    # Регистрация хендлеров создания заявок
    dp.message.register(start_new_request, F.text.in_({"Создать ИТ-заявку", "Создать АХО-заявку"}))
    dp.message.register(process_description, NewRequestStates.waiting_for_description)
    dp.callback_query.register(process_urgency_callback, NewRequestStates.waiting_for_urgency,
                               F.data.in_({"urgency_asap", "urgency_date"}))
    dp.message.register(process_date, NewRequestStates.waiting_for_date)

    # Регистрация хендлеров действий администраторов
    dp.callback_query.register(admin_accept_request, F.data.startswith("admin_accept_"))
    dp.callback_query.register(admin_clarify_start, F.data.startswith("admin_clarify_start_"))
    dp.message.register(process_admin_clarification_message, ClarificationState.admin_active_dialogue)
    dp.callback_query.register(admin_clarify_end, F.data.startswith("admin_clarify_end_"))
    dp.message.register(show_assigned_requests, F.text == "Мои принятые заявки")
    dp.callback_query.register(admin_done_request, F.data.startswith("admin_done_"))

    # Регистрация хендлеров действий пользователей
    dp.message.register(show_user_requests, F.text == "Мои заявки")
    dp.callback_query.register(user_mark_done_request, F.data.startswith("user_done_"))
    dp.callback_query.register(user_clarify_start, F.data.startswith("user_clarify_start_"))
    dp.message.register(process_user_clarification_message, ClarificationState.user_active_dialogue)
    dp.callback_query.register(user_clarify_end, F.data.startswith("user_clarify_end_"))
    dp.message.register(send_website_link, F.text == "Портал бюджетной системы Липецкой области")

    # Запуск функции инициализации при старте бота
    dp.startup.register(lambda: on_startup(dp, bot))

    # Запуск бота
    logger.info("Бот запущен. Начинаю опрос...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())