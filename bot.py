import asyncio
import logging
import sys
import aiohttp
import json
from datetime import datetime, timedelta

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
# 1. ЛОГИРОВАНИЕ И БАЗОВЫЕ НАСТРОЙКИ
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

BOT_TOKEN = "8991533473:AAGhsAChSIVcOsbKjzCbhrSx7DFqGro2lPQ"

# Числовые Telegram ID для уведомлений
MY_TELEGRAM_ID = 5390254050         # Владелец (@M1lfohks)
GREYDER_ADMIN_ID = 7508100064      # Админ Грейдерной (@NextGenAst)
KOMMUNIST_ADMIN_ID = 222222222     # Админ Коммунистической (@genesisvrast)

BRANCH_RECIPIENTS = {
    "loc_greyder": {GREYDER_ADMIN_ID, MY_TELEGRAM_ID},
    "loc_kommunist": {KOMMUNIST_ADMIN_ID, MY_TELEGRAM_ID},
}

ALL_ADMIN_IDS = {MY_TELEGRAM_ID, GREYDER_ADMIN_ID, KOMMUNIST_ADMIN_ID}
USERS_DB = set(ALL_ADMIN_IDS)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ==========================================
# 2. ИНТЕГРАЦИЯ С SMARTSHELL API
# ==========================================
SMARTSHELL_URL = "https://billing.smartshell.gg/api/graphql"

class SmartShellAPI:
    def __init__(self, company_id: int, login_phone: str, password: str):
        self.company_id = company_id
        self.login_phone = login_phone
        self.password = password
        self.token = None
        self.token_expire_time = None
        self.headers = {
            "Content-Type": "application/json",
            "User-Agent": f"company_id={self.company_id}"
        }

    async def ensure_auth(self, session: aiohttp.ClientSession) -> bool:
        """Авторизация и сохранение JWT-токена"""
        now = datetime.now()
        if self.token and self.token_expire_time and now < self.token_expire_time:
            return True

        mutation = """
        mutation Login($input: LoginInput!) {
            login(input: $input) {
                access_token
            }
        }
        """
        variables = {
            "input": {
                "login": self.login_phone,
                "password": self.password,
                "company_id": int(self.company_id)
            }
        }

        try:
            async with session.post(SMARTSHELL_URL, json={"query": mutation, "variables": variables}, headers=self.headers, timeout=5) as resp:
                if resp.status != 200:
                    logging.error(f"SmartShell Login HTTP Error {resp.status}")
                    return False
                data = await resp.json()
                if "errors" in data:
                    logging.error(f"SmartShell Login GraphQL Error: {data['errors']}")
                    return False

                self.token = data["data"]["login"]["access_token"]
                self.headers["Authorization"] = f"Bearer {self.token}"
                # Считаем токен валидным в течение 12 часов
                self.token_expire_time = datetime.now() + timedelta(hours=12)
                logging.info(f"SmartShell: токен успешно обновлен для company_id={self.company_id}")
                return True
        except Exception as e:
            logging.error(f"SmartShell connection exception: {e}")
            return False

    async def get_hosts_status(self) -> dict:
        """Возвращает словарь: {alias_места: "до HH:MM" или None}"""
        status_map = {}
        if not self.company_id or not self.login_phone:
            return status_map

        query = """
        query GetHosts {
            hosts {
                id
                alias
                client_sessions {
                    id
                    status
                    time_left
                }
            }
        }
        """
        try:
            async with aiohttp.ClientSession() as session:
                if not await self.ensure_auth(session):
                    return status_map

                async with session.post(SMARTSHELL_URL, json={"query": query}, headers=self.headers, timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        hosts = data.get("data", {}).get("hosts", []) or []
                        for h in hosts:
                            alias = str(h.get("alias", "")).strip()
                            sessions = h.get("client_sessions", []) or []
                            # Находим сессию с активным таймером
                            active = [s for s in sessions if s.get("time_left") and s.get("time_left") > 0]
                            if active:
                                sec_left = active[0]["time_left"]
                                end_dt = datetime.now() + timedelta(seconds=sec_left)
                                status_map[alias] = f"до ~{end_dt.strftime('%H:%M')}"
                            else:
                                status_map[alias] = None
        except Exception as e:
            logging.error(f"Ошибка получения хостов SmartShell: {e}")

        return status_map

# Клиенты SmartShell по филиалам
SMARTSHELL_CLIENTS = {
    "loc_greyder": SmartShellAPI(3489, "79968370695", "йфцыув321"),
    "loc_kommunist": SmartShellAPI(0, "", "")  # Впишете данные когда будет доступ
}

# ==========================================
# 3. СТРУКТУРА МЕСТ ПО ТОЧКАМ
# ==========================================
GREYDER_ZONES = {
    "VIP Пятерка": ["4", "5", "6", "7", "8"],
    "VIP Четверка": ["9", "10", "11", "12"],
    "MVP Trio (Тройка)": ["13", "14", "15"],
    "MVP Duo (Двойка)": ["2", "3"],
    "MVP Solo 1": ["16"],
    "MVP Solo 2": ["17"],
    "🎮 Зона PlayStation 5": ["PS5 №1", "PS5 №2"],
}

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

CLUBS = {
    "loc_greyder": {
        "name": "📍 Грейдерная, 1 (2 этаж)",
        "phone": "+7 960 856 06 14",
        "admin_tg": "@NextGenAst",
        "zones": GREYDER_ZONES,
        "price_photo": "price_greyder.jpg",
        "info_caption": (
            "🏢 <b>Филиал на ул. Грейдерная, 1 (2 этаж)</b>\n\n"
            "💻 <b>Конфигурация оборудования:</b>\n\n"
            "👑 <b>VIP-зона:</b>\n"
            "• Видеокарты: RTX 3060 Ti\n"
            "• Оперативная память: 16 GB RAM\n"
            "• Мониторы: 165Hz\n\n"
            "🔥 <b>MVP-зона (Solo / Duo / Trio):</b>\n"
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

def is_admin(user: types.User) -> bool:
    return user.id in ALL_ADMIN_IDS

# Состояния FSM
class BookingStates(StatesGroup):
    location = State()
    zone = State()
    selecting_pcs = State()
    date_time = State()
    duration = State()
    phone = State()

class FeedbackStates(StatesGroup):
    loc = State()
    text = State()

class BroadcastStates(StatesGroup):
    message = State()

# ==========================================
# 4. ДИНАМИЧЕСКИЕ КЛАВИАТУРЫ (ПО SMARTSHELL)
# ==========================================
def get_main_keyboard(user: types.User) -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text="⚡ Забронировать ПК / PS5 / VR 📍")],
        [KeyboardButton(text="💻 Железо и Прайс"), KeyboardButton(text="🎁 Акции и Бонусы")],
        [KeyboardButton(text="🎮 Список игр"), KeyboardButton(text="☎️ Контакты и адреса")],
    ]
    if is_admin(user):
        kb.append([KeyboardButton(text="📢 Сделать рассылку")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_location_select_kb(action_prefix: str) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text=data["name"], callback_data=f"{action_prefix}_{key}")]
        for key, data in CLUBS.items()
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

# Клавиатура зон с проверкой занятости по данным SmartShell
def get_club_zones_keyboard(club_key: str, real_status: dict) -> InlineKeyboardMarkup:
    club = CLUBS[club_key]
    zones = club["zones"]
    
    buttons = []
    for zone_name, places in zones.items():
        # Считаем сколько мест занято в шелле
        busy_places = [p for p in places if real_status.get(p) is not None]
        
        if len(busy_places) == len(places):
            btn_text = f"🔒 {zone_name} (занята)"
            callback = f"zonebusy_{zone_name}"
        else:
            free_count = len(places) - len(busy_places)
            btn_text = f"🟢 {zone_name} (свободно: {free_count}/{len(places)})"
            callback = f"selectzone_{zone_name}"
            
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=callback)])
        
    buttons.append([InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_action")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Клавиатура конкретных мест внутри зоны со статусом из SmartShell
def get_multi_pcs_keyboard(club_key: str, zone_name: str, selected_list: list, real_status: dict) -> InlineKeyboardMarkup:
    club = CLUBS[club_key]
    places = club["zones"][zone_name]
    
    buttons = []
    for place in places:
        busy_info = real_status.get(place)
        prefix = "ПК" if "PS5" not in place and "VR" not in place else ""
        label = f"{prefix} {place}".strip()
        
        if busy_info:
            btn_text = f"🔴 {label} ({busy_info})"
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
# 5. ОСНОВНЫЕ ОБРАБОТЧИКИ
# ==========================================
@dp.message(CommandStart())
@dp.message(F.text == "🔄 Вернуться в меню")
@dp.message(F.text == "❌ Отменить")
async def cmd_start_or_back(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    USERS_DB.add(user_id)

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
        logging.error(f"Ошибка фото: {e}")
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
    
    recipients = BRANCH_RECIPIENTS.get(loc_key, {MY_TELEGRAM_ID})
    for adm_chat_id in recipients:
        try:
            await bot.send_message(chat_id=adm_chat_id, text=card, parse_mode="HTML")
        except Exception as e:
            logging.error(f"Не удалось доставить запрос на игру {adm_chat_id}: {e}")

    await message.answer("Спасибо! Передали заявку админам филиала 🙌", reply_markup=get_main_keyboard(user))

# ==========================================
# 6. БРОНИРОВАНИЕ С ЖИВЫМ API SMARTSHELL
# ==========================================
@dp.message(F.text == "⚡ Забронировать ПК / PS5 / VR 📍")
async def start_booking(message: types.Message, state: FSMContext):
    await state.set_state(BookingStates.location)
    await message.answer("Выберите филиал для бронирования:", reply_markup=get_location_select_kb("bookloc"))

# 1. Запрос статусов из SmartShell и показ зон
@dp.callback_query(F.data.startswith("bookloc_"), BookingStates.location)
async def booking_location_chosen(callback: CallbackQuery, state: FSMContext):
    club_key = callback.data.replace("bookloc_", "")
    await callback.message.edit_text("⏳ <i>Синхронизируем доступность ПК со SmartShell...</i>", parse_mode="HTML")

    # Опрашиваем SmartShell
    ss_client = SMARTSHELL_CLIENTS.get(club_key)
    real_status = await ss_client.get_hosts_status() if ss_client else {}
    
    await state.update_data(location=CLUBS[club_key]["name"], loc_key=club_key, real_status=real_status)
    await state.set_state(BookingStates.zone)
    
    await callback.message.edit_text(
        f"<b>{CLUBS[club_key]['name']}</b>\nВыберите свободную зону, PS5 или VR:",
        reply_markup=get_club_zones_keyboard(club_key, real_status),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("zonebusy_"), BookingStates.zone)
async def zone_busy_alert(callback: CallbackQuery):
    await callback.answer("❌ Вся эта зона сейчас занята гостями в клубе!", show_alert=True)

@dp.callback_query(F.data == "back_to_zones", BookingStates.selecting_pcs)
async def back_to_zones_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    club_key = data["loc_key"]
    real_status = data.get("real_status", {})
    await state.set_state(BookingStates.zone)
    await callback.message.edit_text(
        f"<b>{CLUBS[club_key]['name']}</b>\nВыберите зону:",
        reply_markup=get_club_zones_keyboard(club_key, real_status),
        parse_mode="HTML"
    )
    await callback.answer()

# 2. Выбор мест в комнате (со статусами SmartShell)
@dp.callback_query(F.data.startswith("selectzone_"), BookingStates.zone)
async def choose_pc_in_zone(callback: CallbackQuery, state: FSMContext):
    zone_name = callback.data.replace("selectzone_", "")
    data = await state.get_data()
    club_key = data["loc_key"]
    real_status = data.get("real_status", {})
    
    await state.update_data(zone=zone_name, selected_pcs=[])
    await state.set_state(BookingStates.selecting_pcs)
    
    await callback.message.edit_text(
        f"Выбрано: <b>{zone_name}</b>\nЗеленые места свободны. Нажмите на нужные (можно выбрать несколько):",
        reply_markup=get_multi_pcs_keyboard(club_key, zone_name, [], real_status),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("pcbusy_"), BookingStates.selecting_pcs)
async def pc_busy_alert(callback: CallbackQuery, state: FSMContext):
    place_name = callback.data.replace("pcbusy_", "")
    data = await state.get_data()
    real_status = data.get("real_status", {})
    until = real_status.get(place_name, "занято")
    await callback.answer(f"❌ Место {place_name} сейчас занято ({until})!", show_alert=True)

@dp.callback_query(F.data.startswith("togglepc_"), BookingStates.selecting_pcs)
async def toggle_pc_selection(callback: CallbackQuery, state: FSMContext):
    place_name = callback.data.replace("togglepc_", "")
    data = await state.get_data()
    club_key = data["loc_key"]
    zone_name = data["zone"]
    real_status = data.get("real_status", {})
    selected = data.get("selected_pcs", [])
    
    if place_name in selected:
        selected.remove(place_name)
    else:
        selected.append(place_name)
        
    await state.update_data(selected_pcs=selected)
    await callback.message.edit_reply_markup(
        reply_markup=get_multi_pcs_keyboard(club_key, zone_name, selected, real_status)
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
        "🚨 <b>НОВАЯ ЗАЯВКА НА БРОНЬ (SmartShell)</b>\n\n"
        f"🏢 <b>Филиал:</b> {data['location']}\n"
        f"🎯 <b>Места:</b> {data['zone']} 👉 <b>{data['pc_number']}</b>\n"
        f"👤 <b>Клиент:</b> {user.full_name} ({username_str})\n"
        f"📞 <b>Телефон:</b> <code>{data['phone']}</code>\n"
        f"🕒 <b>Время:</b> {data['date_time']}\n"
        f"⏳ <b>Длительность:</b> {data['duration']}"
    )
    
    recipients = BRANCH_RECIPIENTS.get(loc_key, {MY_TELEGRAM_ID})
    logging.info(f"👉 Отправка брони {loc_key} на ID: {recipients}")

    for adm_chat_id in recipients:
        try:
            await bot.send_message(chat_id=adm_chat_id, text=admin_card, reply_markup=admin_kb, parse_mode="HTML")
            logging.info(f"✅ Доставлено админу ID={adm_chat_id}")
        except Exception as e:
            logging.error(f"❌ Ошибка отправки админу ID={adm_chat_id}: {e}")

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
# 8. РАССЫЛКА
# ==========================================
@dp.message(F.text == "📢 Сделать рассылку")
async def start_broadcast(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user):
        return
    await state.set_state(BroadcastStates.message)
    await message.answer("📢 Напишите текст рассылки для всех пользователей:", reply_markup=get_cancel_keyboard())

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
            logging.error(f"Ошибка рассылки {uid}: {e}")

    menu = get_main_keyboard(message.from_user)
    await message.answer(f"✅ Рассылка доставлена: <b>{sent_count}</b> чел.", reply_markup=menu, parse_mode="HTML")

# ==========================================
# 9. ЗАПУСК БОТА
# ==========================================
async def main():
    logging.info("Бот успешно запущен со SmartShell API.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
