import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

# ==========================================
# 1. НАСТРОЙКА ЛОГИРОВАНИЯ И ТОКЕНОВ
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

BOT_TOKEN = "8991533473:AAGhsAChSIVcOsbKjzCbhrSx7DFqGro2lPQ"

# Числовой ID владельца (из @userinfobot)
MY_TELEGRAM_ID = 5390254050  

SUPER_ADMIN_USERNAME = "m1lfohks"

# Закрепление админов за точками (в нижнем регистре без @)
BRANCH_ADMINS = {
    "loc_greyder": {"nextgenast"},
    "loc_kommunist": {"genesisvrast"}
}

# Все админы системы
ALL_ADMIN_USERNAMES = {SUPER_ADMIN_USERNAME, "nextgenast", "genesisvrast"}

USERS_DB = {MY_TELEGRAM_ID}
# Словарь для связи юзернейма и числового chat_id: {"username": chat_id}
ACTIVE_ADMIN_CHATS = {}

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ==========================================
# 2. СТРУКТУРА МЕСТ ПО ТОЧКАМ
# ==========================================

# Грейдерная, 1 (2 этаж)
GREYDER_ZONES = {
    "VIP Пятерка": ["4", "5", "6", "7", "8"],
    "VIP Четверка": ["9", "10", "11", "12"],
    "MVP Trio (Тройка)": ["13", "14", "15"],
    "MVP Duo (Двойка)": ["2", "3"],
    "MVP Solo 1": ["16"],
    "MVP Solo 2": ["17"],
    "🎮 Зона PlayStation 5": ["PS5 №1", "PS5 №2"],
}

# Коммунистическая, 7
KOMMUNIST_ZONES = {
    "Bootcamp 1 (ПК 6-12)": ["6", "7", "8", "9", "10", "11", "12"],
    "Четверка (ПК 2-5)": ["2", "3", "4", "5"],
    "Двойка (ПК 13, 14)": ["13", "14"],
    "Тройка (ПК 15-17)": ["15", "16", "17"],
    "VIP Одиночка 1 (ПК 1)": ["1"],
    "VIP Одиночка 2 (ПК 18)": ["18"],
    "Bootcamp 2 (ПК 19-23)": ["19", "20", "21", "22", "23"],
    "Bootcamp 3 (ПК 24-28)": ["24", "25", "26", "27", "28"],
    "🎮 Зона PlayStation 5": ["PS5 №1"],
    "🥽 VR Площадки (4 зоны)": ["VR №1", "VR №2", "VR №3", "VR №4"],
}

PC_STATUS_GREYDER = {place: None for places in GREYDER_ZONES.values() for place in places}
PC_STATUS_KOMMUNIST = {place: None for places in KOMMUNIST_ZONES.values() for place in places}

# ==========================================
# 3. ДАННЫЕ ФИЛИАЛОВ И ЖЕЛЕЗО
# ==========================================
CLUBS = {
    "loc_greyder": {
        "name": "📍 Грейдерная, 1 (2 этаж)",
        "phone": "89608560614",
        "admin_tg": "@NextGenAst",
        "zones": GREYDER_ZONES,
        "pc_status": PC_STATUS_GREYDER,
        "price_photo": "price_greyder.jpg",
        "info_caption": (
            "🏢 <b>Филиал на ул. Грейдерная, 1 (2 этаж)</b>\n\n"
            "💻 <b>Конфигурация оборудования:</b>\n\n"
            "👑 <b>VIP-зона:</b>\n"
            "• Видеокарты: RTX 3060 Ti\n"
            "• Оперативная память: 16 GB RAM\n"
            "• Мониторы: 165Hz\n\n"
            "🔥 <b>MVP-зона (Solo / Duo):</b>\n"
            "• Видеокарты: RTX 3070 Ti / RTX 4070 Ti\n"
            "• Оперативная память: 16 GB RAM\n"
            "• Мониторы: 240Hz – 320Hz\n"
            "• Периферия: Фулл беспроводные девайсы\n\n"
            "🎮 <b>Консоли:</b> 2x PlayStation 5\n\n"
            "📄 <i>Прайс-лист прикреплен на фото выше 👆</i>"
        ),
    },
    "loc_kommunist": {
        "name": "📍 Коммунистическая, 7",
        "phone": "89064560613",
        "admin_tg": "@genesisvrast",
        "zones": KOMMUNIST_ZONES,
        "pc_status": PC_STATUS_KOMMUNIST,
        "price_photo": "price_kommunist.jpg",
        "info_caption": (
            "🏢 <b>Филиал на ул. Коммунистическая, 7</b>\n\n"
            "💻 <b>Конфигурация оборудования:</b>\n\n"
            "🔹 <b>Обычная зона (Standard):</b>\n"
            "• Видеокарты: RTX 5060 Ti\n"
            "• Память: 16 GB RAM\n"
            "• Мониторы: 180Hz / 240Hz\n\n"
            "👑 <b>VIP-зона:</b>\n"
            "• Видеокарты: RTX 5060 Ti\n"
            "• Память: 32 GB RAM\n"
            "• Мониторы: 280Hz / 360Hz\n\n"
            "🎮 <b>Консоли:</b> 1x PlayStation 5\n"
            "🥽 <b>Виртуальная реальность:</b> 4x VR-площадки\n\n"
            "📄 <i>Прайс-лист прикреплен на фото выше 👆</i>"
        ),
    }
}

def is_super_admin(user: types.User) -> bool:
    if user.id == MY_TELEGRAM_ID:
        return True
    return bool(user.username and user.username.lower() == SUPER_ADMIN_USERNAME)

def is_admin(user: types.User) -> bool:
    if is_super_admin(user):
        return True
    return bool(user.username and user.username.lower() in ALL_ADMIN_USERNAMES)

# Функция поиска получателей уведомлений для конкретной точки
def get_target_admin_chats(loc_key: str) -> set:
    target_chats = set()
    # Всегда отправляем главному
    if MY_TELEGRAM_ID:
        target_chats.add(MY_TELEGRAM_ID)
    if SUPER_ADMIN_USERNAME in ACTIVE_ADMIN_CHATS:
        target_chats.add(ACTIVE_ADMIN_CHATS[SUPER_ADMIN_USERNAME])
        
    # Добавляем админов конкретного филиала
    branch_admins = BRANCH_ADMINS.get(loc_key, set())
    for adm_user in branch_admins:
        if adm_user in ACTIVE_ADMIN_CHATS:
            target_chats.add(ACTIVE_ADMIN_CHATS[adm_user])
            
    return target_chats

# Состояния FSM
class BookingStates(StatesGroup):
    location = State()
    zone = State()
    selecting_pcs = State()
    date_time = State()
    duration = State()
    phone = State()

class AdminSetPCStates(StatesGroup):
    loc = State()
    pc = State()
    until_time = State()

class FeedbackStates(StatesGroup):
    loc = State()
    text = State()

class BroadcastStates(StatesGroup):
    message = State()

class ManageAdminStates(StatesGroup):
    add_branch = State()
    add_username = State()
    del_username = State()

# ==========================================
# 4. КЛАВИАТУРЫ
# ==========================================

def get_main_keyboard(user: types.User) -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text="⚡ Забронировать ПК / PS5 / VR 📍")],
        [KeyboardButton(text="💻 Железо и Прайс"), KeyboardButton(text="🎁 Акции и Бонусы")],
        [KeyboardButton(text="🎮 Список игр"), KeyboardButton(text="☎️ Контакты и адреса")],
    ]
    if is_admin(user):
        kb.append([KeyboardButton(text="🔒 Админ-панель")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_location_select_kb(action_prefix: str) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text=data["name"], callback_data=f"{action_prefix}_{key}")]
        for key, data in CLUBS.items()
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_club_zones_keyboard(club_key: str) -> InlineKeyboardMarkup:
    club = CLUBS[club_key]
    zones = club["zones"]
    pc_status = club["pc_status"]
    
    buttons = []
    for zone_name, places in zones.items():
        busy_places = [p for p in places if pc_status[p] is not None]
        
        if len(busy_places) == len(places):
            max_until = max([pc_status[p] for p in places])
            btn_text = f"🔒 {zone_name} (занята до {max_until})"
            callback = f"zonebusy_{zone_name}"
        else:
            free_count = len(places) - len(busy_places)
            btn_text = f"🟢 {zone_name} (свободно: {free_count}/{len(places)})"
            callback = f"selectzone_{zone_name}"
            
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=callback)])
        
    buttons.append([InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_action")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_multi_pcs_keyboard(club_key: str, zone_name: str, selected_list: list) -> InlineKeyboardMarkup:
    club = CLUBS[club_key]
    places = club["zones"][zone_name]
    pc_status = club["pc_status"]
    
    buttons = []
    for place in places:
        until = pc_status[place]
        prefix = "ПК" if "PS5" not in place and "VR" not in place else ""
        label = f"{prefix} {place}".strip()
        
        if until:
            btn_text = f"🔴 {label} (до {until})"
            callback = f"pcbusy_{place}"
        elif place in selected_list:
            btn_text = f"✅ {label} (ВЫБРАН)"
            callback = f"togglepc_{place}"
        else:
            btn_text = f"🟢 {label}"
            callback = f"togglepc_{place}"
            
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=callback)])
        
    bottom_row = []
    if selected_list:
        bottom_row.append(InlineKeyboardButton(text=f"👉 Готово ({len(selected_list)} мест)", callback_data="finish_pc_selection"))
    bottom_row.append(InlineKeyboardButton(text="◀️ Назад к зонам", callback_data="back_to_zones"))
    buttons.append(bottom_row)
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_back_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🔄 Вернуться в меню")]], resize_keyboard=True)

def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Отменить")]], resize_keyboard=True)

# ==========================================
# 5. ОСНОВНЫЕ ОБРАБОТЧИКИ МЕНЮ
# ==========================================

@dp.message(CommandStart())
@dp.message(F.text == "🔄 Вернуться в меню")
@dp.message(F.text == "❌ Отменить")
async def cmd_start_or_back(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    username = message.from_user.username.lower() if message.from_user.username else ""
    
    USERS_DB.add(user_id)
    
    # Фиксируем активного админа для отправки брони в ЛС
    if is_admin(message.from_user):
        if username:
            ACTIVE_ADMIN_CHATS[username] = user_id
        if user_id == MY_TELEGRAM_ID:
            ACTIVE_ADMIN_CHATS[SUPER_ADMIN_USERNAME] = user_id
        logging.info(f"Администратор подключен: @{username} (ID: {user_id})")

    menu = get_main_keyboard(message.from_user)
    await message.answer(
        "👋 <b>Добро пожаловать в сеть игровых клубов!</b>\nВыберите раздел меню:",
        reply_markup=menu,
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "cancel_action")
async def cancel_action_cb(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    menu = get_main_keyboard(callback.from_user)
    await callback.message.answer("Действие отменено.", reply_markup=menu)
    await callback.answer()

@dp.message(F.text == "💻 Железо и Прайс")
async def choose_location_info(message: types.Message):
    await message.answer("Выберите филиал:", reply_markup=get_location_select_kb("info"))

@dp.callback_query(F.data.startswith("info_"))
async def send_club_info(callback: CallbackQuery):
    club_key = callback.data.replace("info_", "")
    club = CLUBS[club_key]
    await callback.message.delete()
    try:
        await callback.message.answer_photo(
            photo=FSInputFile(club["price_photo"]),
            caption=club["info_caption"],
            reply_markup=get_back_keyboard(),
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Ошибка отправки фото: {e}")
        await callback.message.answer(club["info_caption"], reply_markup=get_back_keyboard(), parse_mode="HTML")
    await callback.answer()

@dp.message(F.text == "☎️ Контакты и адреса")
async def send_contacts(message: types.Message):
    text = "🏢 <b>Наши адреса и контакты:</b>\n\n"
    for _, club in CLUBS.items():
        text += (
            f"<b>{club['name']}</b>\n"
            f"🕒 Режим работы: 24/7\n"
            f"📞 Телефон: <code>{club['phone']}</code>\n"
            f"💬 Telegram админа: {club['admin_tg']}\n\n"
        )
    await message.answer(text, reply_markup=get_back_keyboard(), parse_mode="HTML")

@dp.message(F.text == "🎁 Акции и Бонусы")
async def send_bonuses(message: types.Message):
    text = (
        "🔥 <b>Акции и Бонусная программа сети:</b>\n\n"
        "🎁 <b>При регистрации:</b> 2 часа игры бесплатно!\n"
        "🤝 <b>Приведи друга:</b> получите по 100 бонусов на баланс каждому!\n"
        "⭐ <b>Отзыв на 2ГИС и Яндекс.Картах:</b> 150 бонусов на баланс!\n"
        "📱 <b>Подписка на Telegram-канал:</b> 100 бонусов на баланс!\n"
        "💳 <b>Кешбэк 10%:</b> при пополнении от 1000 рублей!\n"
        "🎂 <b>День Рождения:</b> удвоим баланс (действует 7 дней ДО и 7 дней ПОСЛЕ ДР)!\n\n"
        "💰 <i>1 бонус = 1 рубль. Оплачивайте бонусами до 100% времени!</i>"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🤫 Секретная акция", callback_data="secret_promo_info")]]
    )
    await message.answer(text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "secret_promo_info")
async def secret_promo_cb(callback: CallbackQuery):
    text = (
        "🕵️ <b>СЕКРЕТНАЯ ОХОТА НА АДМИНА</b>\n\n"
        "📸 <b>Пришли фото спящего админа в наш ТГ-канал</b> — получи <b>500 бонусов</b> прямо на баланс!\n\n"
        "<i>Администратор тоже человек, но бдительность превыше всего 😉</i>"
    )
    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()

@dp.message(F.text == "🎮 Список игр")
async def send_games(message: types.Message):
    text = (
        "💬 <b>Популярные установленные игры:</b>\n\n"
        "• Counter-Strike 2\n• Dota 2\n• Fortnite\n• Apex Legends\n• PUBG / Rust\n• Escape from Tarkov\n\n"
        "<i>Нужна другая игра? Нажмите кнопку ниже:</i>"
    )
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="💡 Предложить установить игру")], [KeyboardButton(text="🔄 Вернуться в меню")]],
        resize_keyboard=True
    )
    await message.answer(text, reply_markup=kb, parse_mode="HTML")

@dp.message(F.text == "💡 Предложить установить игру")
async def start_game_request(message: types.Message, state: FSMContext):
    await state.set_state(FeedbackStates.loc)
    await message.answer("Выберите филиал, куда требуется установить игру:", reply_markup=get_location_select_kb("fbloc"))

@dp.callback_query(F.data.startswith("fbloc_"), FeedbackStates.loc)
async def process_feedback_loc(callback: CallbackQuery, state: FSMContext):
    loc_key = callback.data.replace("fbloc_", "")
    await state.update_data(loc_key=loc_key, location=CLUBS[loc_key]["name"])
    await state.set_state(FeedbackStates.text)
    await callback.message.delete()
    await callback.message.answer(
        f"Выбран клуб: <b>{CLUBS[loc_key]['name']}</b>\nНапишите название игры:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.message(FeedbackStates.text)
async def process_feedback(message: types.Message, state: FSMContext):
    data = await state.get_data()
    loc_key = data.get("loc_key", "loc_greyder")
    location_name = data.get("location", "")
    await state.clear()
    
    user = message.from_user
    username_str = f"@{user.username}" if user.username else f"ID {user.id}"

    card = (
        f"🎮 <b>ЗАПРОС НА УСТАНОВКУ ИГРЫ</b>\n\n"
        f"🏢 <b>Филиал:</b> {location_name}\n"
        f"👤 <b>От:</b> {user.full_name} ({username_str})\n"
        f"📝 <b>Игра:</b> <i>{message.text}</i>"
    )
    
    # Отправка строго ответственным админам этого филиала
    recipients = get_target_admin_chats(loc_key)
    for adm_chat_id in recipients:
        try:
            await bot.send_message(chat_id=adm_chat_id, text=card, parse_mode="HTML")
        except Exception:
            pass

    await message.answer("Спасибо! Передали заявку админам филиала 🙌", reply_markup=get_main_keyboard(user))

# ==========================================
# 6. БРОНИРОВАНИЕ С РАЗДЕЛЕНИЕМ ПО ТОЧКАМ
# ==========================================

@dp.message(F.text == "⚡ Забронировать ПК / PS5 / VR 📍")
async def start_booking(message: types.Message, state: FSMContext):
    await state.set_state(BookingStates.location)
    await message.answer("Выберите филиал для бронирования:", reply_markup=get_location_select_kb("bookloc"))

@dp.callback_query(F.data.startswith("bookloc_"), BookingStates.location)
async def booking_location_chosen(callback: CallbackQuery, state: FSMContext):
    club_key = callback.data.replace("bookloc_", "")
    await state.update_data(location=CLUBS[club_key]["name"], loc_key=club_key)
    await state.set_state(BookingStates.zone)
    
    await callback.message.edit_text(
        f"<b>{CLUBS[club_key]['name']}</b>\nВыберите свободную зону, PS5 или VR:",
        reply_markup=get_club_zones_keyboard(club_key),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("zonebusy_"), BookingStates.zone)
async def zone_busy_alert(callback: CallbackQuery):
    await callback.answer("❌ Вся эта зона полностью занята! Выберите другую.", show_alert=True)

@dp.callback_query(F.data == "back_to_zones", BookingStates.selecting_pcs)
async def back_to_zones_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    club_key = data["loc_key"]
    await state.set_state(BookingStates.zone)
    await callback.message.edit_text(
        f"<b>{CLUBS[club_key]['name']}</b>\nВыберите зону:",
        reply_markup=get_club_zones_keyboard(club_key),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("selectzone_"), BookingStates.zone)
async def choose_pc_in_zone(callback: CallbackQuery, state: FSMContext):
    zone_name = callback.data.replace("selectzone_", "")
    data = await state.get_data()
    club_key = data["loc_key"]
    
    await state.update_data(zone=zone_name, selected_pcs=[])
    await state.set_state(BookingStates.selecting_pcs)
    
    await callback.message.edit_text(
        f"Выбрано: <b>{zone_name}</b>\nНажмите на нужные места (можно выбрать несколько):",
        reply_markup=get_multi_pcs_keyboard(club_key, zone_name, []),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("pcbusy_"), BookingStates.selecting_pcs)
async def pc_busy_alert(callback: CallbackQuery, state: FSMContext):
    place_name = callback.data.replace("pcbusy_", "")
    data = await state.get_data()
    club_key = data["loc_key"]
    until = CLUBS[club_key]["pc_status"][place_name]
    await callback.answer(f"❌ Место {place_name} занято до {until}!", show_alert=True)

@dp.callback_query(F.data.startswith("togglepc_"), BookingStates.selecting_pcs)
async def toggle_pc_selection(callback: CallbackQuery, state: FSMContext):
    place_name = callback.data.replace("togglepc_", "")
    data = await state.get_data()
    club_key = data["loc_key"]
    zone_name = data["zone"]
    selected = data.get("selected_pcs", [])
    
    if place_name in selected:
        selected.remove(place_name)
    else:
        selected.append(place_name)
        
    await state.update_data(selected_pcs=selected)
    await callback.message.edit_reply_markup(
        reply_markup=get_multi_pcs_keyboard(club_key, zone_name, selected)
    )
    await callback.answer()

@dp.callback_query(F.data == "finish_pc_selection", BookingStates.selecting_pcs)
async def finish_selection_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("selected_pcs", [])
    
    if not selected:
        await callback.answer("Выберите хотя бы одно место!", show_alert=True)
        return
        
    formatted_places = []
    for p in selected:
        prefix = "ПК №" if "PS5" not in p and "VR" not in p else ""
        formatted_places.append(f"{prefix}{p}")
        
    places_str = ", ".join(formatted_places)
    await state.update_data(pc_number=places_str)
    await state.set_state(BookingStates.date_time)
    
    await callback.message.delete()
    await callback.message.answer(
        f"Выбрано мест ({len(selected)} шт.): <b>{places_str}</b>\n\nНапишите дату и время брони (например: <i>Сегодня в 19:30</i>):",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.message(BookingStates.date_time)
async def booking_datetime(message: types.Message, state: FSMContext):
    await state.update_data(date_time=message.text)
    await state.set_state(BookingStates.duration)
    await message.answer("На сколько часов бронь? (например: <i>3 часа</i> / <i>Ночной пакет</i>):", reply_markup=get_cancel_keyboard(), parse_mode="HTML")

@dp.message(BookingStates.duration)
async def booking_duration(message: types.Message, state: FSMContext):
    await state.update_data(duration=message.text)
    await state.set_state(BookingStates.phone)
    await message.answer("Укажите номер телефона для связи:", reply_markup=get_cancel_keyboard(), parse_mode="HTML")

@dp.message(BookingStates.phone)
async def booking_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    data = await state.get_data()
    loc_key = data["loc_key"]
    await state.clear()

    user = message.from_user
    username_str = f"@{user.username}" if user.username else "нет username"

    await message.answer("✅ <b>Заявка отправлена администраторам филиала!</b>\nОжидайте подтверждения.", reply_markup=get_main_keyboard(user), parse_mode="HTML")

    admin_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Принять", callback_data=f"adm_ok_{user.id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"adm_no_{user.id}")
            ]
        ]
    )
    admin_card = (
        "🚨 <b>НОВАЯ ЗАЯВКА НА БРОНЬ</b>\n\n"
        f"🏢 <b>Филиал:</b> {data['location']}\n"
        f"🎯 <b>Места:</b> {data['zone']} 👉 <b>{data['pc_number']}</b>\n"
        f"👤 <b>Клиент:</b> {user.full_name} ({username_str})\n"
        f"📞 <b>Телефон:</b> <code>{data['phone']}</code>\n"
        f"🕒 <b>Время:</b> {data['date_time']}\n"
        f"⏳ <b>Длительность:</b> {data['duration']}"
    )
    
    logging.info(f"Заявка оформлена: {data['location']}, {data['pc_number']}")

    # Маршрутизация: отправляем только ответственным админам данной точки
    recipients = get_target_admin_chats(loc_key)
    logging.info(f"Отправка заявки филиала {loc_key} получателям: {recipients}")
    
    for adm_chat_id in recipients:
        try:
            await bot.send_message(chat_id=adm_chat_id, text=admin_card, reply_markup=admin_kb, parse_mode="HTML")
        except Exception as e:
            logging.error(f"Ошибка отправки админу {adm_chat_id}: {e}")

# ==========================================
# 7. ДЕЙСТВИЯ АДМИНИСТРАТОРА
# ==========================================

@dp.callback_query(F.data.startswith("adm_ok_"))
async def admin_approve(callback: CallbackQuery):
    if not is_admin(callback.from_user):
        await callback.answer("⛔ Вы не администратор!", show_alert=True)
        return

    client_id = int(callback.data.split("_")[2])
    admin_name = callback.from_user.first_name
    await callback.message.edit_text(f"{callback.message.text}\n\n🟢 <b>ПРИНЯТА (Админ: {admin_name})</b>", parse_mode="HTML")
    try:
        await bot.send_message(chat_id=client_id, text="🎉 <b>Ваша бронь подтверждена!</b> Ждем вас в клубе.", parse_mode="HTML")
    except Exception as e:
        logging.error(f"Не удалось доставить подтверждение: {e}")
    await callback.answer("Подтверждено!")

@dp.callback_query(F.data.startswith("adm_no_"))
async def admin_reject(callback: CallbackQuery):
    if not is_admin(callback.from_user):
        await callback.answer("⛔ Вы не администратор!", show_alert=True)
        return

    client_id = int(callback.data.split("_")[2])
    admin_name = callback.from_user.first_name
    await callback.message.edit_text(f"{callback.message.text}\n\n🔴 <b>ОТКЛОНЕНА (Админ: {admin_name})</b>", parse_mode="HTML")
    try:
        await bot.send_message(chat_id=client_id, text="😔 К сожалению, на выбранное время мест нет.", parse_mode="HTML")
    except Exception as e:
        logging.error(f"Не удалось доставить отказ: {e}")
    await callback.answer("Отклонено!")

# ==========================================
# 8. ПАНЕЛЬ УПРАВЛЕНИЯ КЛУБОМ
# ==========================================

@dp.message(F.text == "🔒 Админ-панель")
async def admin_panel(message: types.Message):
    if not is_admin(message.from_user):
        return

    buttons = [
        [InlineKeyboardButton(text="🕹 Управление местами (Грейдерная)", callback_data="adm_manage_loc_greyder")],
        [InlineKeyboardButton(text="🕹 Управление местами (Коммунистическая)", callback_data="adm_manage_loc_kommunist")],
        [InlineKeyboardButton(text="📢 Сделать рассылку", callback_data="adm_broadcast")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="adm_stats")]
    ]
    if is_super_admin(message.from_user):
        buttons.append([InlineKeyboardButton(text="👑 Управление админами", callback_data="adm_manage_team")])

    await message.answer("🛠 <b>Панель управления сетью:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")

@dp.callback_query(F.data.startswith("adm_manage_loc_"))
async def adm_manage_pcs_list(callback: CallbackQuery):
    if not is_admin(callback.from_user):
        return

    club_key = callback.data.replace("adm_manage_", "")
    club = CLUBS[club_key]
    pc_status = club["pc_status"]

    buttons = []
    row = []
    for place in sorted(pc_status.keys(), key=lambda x: (x.isdigit(), int(x) if x.isdigit() else x)):
        status_icon = f"🔴 {place} ({pc_status[place]})" if pc_status[place] else f"🟢 {place}"
        row.append(InlineKeyboardButton(text=status_icon, callback_data=f"admpcset_{club_key}_{place}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([InlineKeyboardButton(text="🔄 Сбросить ВСЕ брони точки", callback_data=f"adm_reset_all_{club_key}")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="cancel_action")])

    await callback.message.edit_text(
        f"🕹 <b>Управление местами ({club['name']}):</b>\nНажмите на ПК / PS5 / VR для изменения статуса:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("admpcset_"))
async def adm_toggle_pc(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user):
        return
    _, club_key, place_name = callback.data.split("_", 2)
    pc_status = CLUBS[club_key]["pc_status"]
    
    if pc_status[place_name] is not None:
        pc_status[place_name] = None
        await callback.answer(f"✅ {place_name} теперь свободно!")
        callback.data = f"adm_manage_{club_key}"
        await adm_manage_pcs_list(callback)
    else:
        await state.set_state(AdminSetPCStates.until_time)
        await state.update_data(loc=club_key, pc=place_name)
        await callback.message.answer(
            f"Укажите время, до которого занято <b>{place_name}</b> ({CLUBS[club_key]['name']})\nНапример: <code>21:30</code>:",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()

@dp.message(AdminSetPCStates.until_time)
async def adm_save_pc_time(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user):
        return
    data = await state.get_data()
    club_key = data["loc"]
    place_name = data["pc"]
    until_time = message.text.strip()
    
    CLUBS[club_key]["pc_status"][place_name] = until_time
    await state.clear()
    
    await message.answer(
        f"🔴 <b>{place_name}</b> ({CLUBS[club_key]['name']}) помечено занятым до <b>{until_time}</b>!",
        reply_markup=get_main_keyboard(message.from_user),
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("adm_reset_all_"))
async def adm_reset_all(callback: CallbackQuery):
    if not is_admin(callback.from_user):
        return
    club_key = callback.data.replace("adm_reset_all_", "")
    for place in CLUBS[club_key]["pc_status"]:
        CLUBS[club_key]["pc_status"][place] = None
    await callback.answer("✅ Все места точки освобождены!", show_alert=True)
    callback.data = f"adm_manage_{club_key}"
    await adm_manage_pcs_list(callback)

# Управление командой админов
@dp.callback_query(F.data == "adm_manage_team")
async def manage_team_menu(callback: CallbackQuery):
    if not is_super_admin(callback.from_user):
        return
    
    text = "👑 <b>Администраторы по филиалам:</b>\n\n"
    text += f"⭐️ <b>Главный владелец:</b> @{SUPER_ADMIN_USERNAME}\n"
    text += "📍 <b>Грейдерная, 1:</b> " + ", ".join([f"@{u}" for u in BRANCH_ADMINS["loc_greyder"]]) + "\n"
    text += "📍 <b>Коммунистическая, 7:</b> " + ", ".join([f"@{u}" for u in BRANCH_ADMINS["loc_kommunist"]]) + "\n"
    
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Назначить админа", callback_data="adm_add_start")],
            [InlineKeyboardButton(text="➖ Снять админа", callback_data="adm_del_start")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="cancel_action")]
        ]
    )
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "adm_add_start")
async def add_admin_choose_branch(callback: CallbackQuery, state: FSMContext):
    if not is_super_admin(callback.from_user):
        return
    await state.set_state(ManageAdminStates.add_branch)
    await callback.message.edit_text("Выберите филиал для нового администратора:", reply_markup=get_location_select_kb("admsetloc"))
    await callback.answer()

@dp.callback_query(F.data.startswith("admsetloc_"), ManageAdminStates.add_branch)
async def add_admin_ask_user(callback: CallbackQuery, state: FSMContext):
    branch_key = callback.data.replace("admsetloc_", "")
    await state.update_data(target_branch=branch_key)
    await state.set_state(ManageAdminStates.add_username)
    await callback.message.answer(
        f"Введите юзернейм нового админа для <b>{CLUBS[branch_key]['name']}</b> (без @):",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.message(ManageAdminStates.add_username)
async def add_admin_finish(message: types.Message, state: FSMContext):
    if not is_super_admin(message.from_user):
        return
    data = await state.get_data()
    branch_key = data["target_branch"]
    new_user = message.text.replace("@", "").strip().lower()
    
    BRANCH_ADMINS[branch_key].add(new_user)
    ALL_ADMIN_USERNAMES.add(new_user)
    await state.clear()
    
    await message.answer(
        f"✅ Пользователь <b>@{new_user}</b> назначен администратором точки <b>{CLUBS[branch_key]['name']}</b>!",
        reply_markup=get_main_keyboard(message.from_user),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "adm_del_start")
async def del_admin_start(callback: CallbackQuery, state: FSMContext):
    if not is_super_admin(callback.from_user):
        return
    await state.set_state(ManageAdminStates.del_username)
    await callback.message.answer("Введите юзернейм админа для снятия прав (без @):", reply_markup=get_cancel_keyboard())
    await callback.answer()

@dp.message(ManageAdminStates.del_username)
async def del_admin_finish(message: types.Message, state: FSMContext):
    if not is_super_admin(message.from_user):
        return
    del_user = message.text.replace("@", "").strip().lower()
    if del_user == SUPER_ADMIN_USERNAME:
        await message.answer("❌ Нельзя снять главного владельца!")
    else:
        for b in BRANCH_ADMINS:
            BRANCH_ADMINS[b].discard(del_user)
        ALL_ADMIN_USERNAMES.discard(del_user)
        ACTIVE_ADMIN_CHATS.pop(del_user, None)
        await message.answer(f"🗑 Пользователь <b>@{del_user}</b> удален из администраторов.", parse_mode="HTML")
        
    await state.clear()
    await message.answer("Главное меню:", reply_markup=get_main_keyboard(message.from_user))

@dp.callback_query(F.data == "adm_stats")
async def show_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user):
        return
    active_adm_str = ", ".join([f"@{u}" for u in ACTIVE_ADMIN_CHATS.keys()]) if ACTIVE_ADMIN_CHATS else "нет"
    await callback.message.answer(
        f"📊 <b>Статистика сети:</b>\n\n"
        f"👥 Всего пользователей бота: <b>{len(USERS_DB)}</b> чел.\n"
        f"🟢 Админов онлайн в ЛС: <b>{len(ACTIVE_ADMIN_CHATS)}</b> ({active_adm_str})",
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "adm_broadcast")
async def start_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user):
        return
    await state.set_state(BroadcastStates.message)
    await callback.message.answer("📢 Напишите текст рассылки для всех пользователей:", reply_markup=get_cancel_keyboard())
    await callback.answer()

@dp.message(BroadcastStates.message)
async def send_broadcast(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user):
        return
    await state.clear()
    sent_count = 0
    for uid in USERS_DB:
        try:
            await bot.send_message(chat_id=uid, text=message.text, parse_mode="HTML")
            sent_count += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            logging.error(f"Ошибка рассылки юзеру {uid}: {e}")

    menu = get_main_keyboard(message.from_user)
    await message.answer(f"✅ Рассылка доставлена: <b>{sent_count}</b> чел.", reply_markup=menu, parse_mode="HTML")

# ==========================================
# 9. ЗАПУСК БОТА
# ==========================================
async def main():
    logging.info("Бот успешно запущен и готов к работе.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
