import asyncio
import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta, timezone

import aiohttp
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

# =====================================================================
# 1. КОНФИГУРАЦИЯ И СИСТЕМНЫЕ НАСТРОЙКИ
# =====================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

BOT_TOKEN = "8991533473:AAGhsAChSIVcOsbKjzCbhrSx7DFqGro2lPQ"

MY_TELEGRAM_ID = 5390254050         # Главный владелец
GREYDER_ADMIN_ID = 7508100064      # Админ Грейдерной
KOMMUNIST_ADMIN_ID = 222222222     # Админ Коммунистической

BRANCH_RECIPIENTS = {
    "loc_greyder": {GREYDER_ADMIN_ID, MY_TELEGRAM_ID},
    "loc_kommunist": {KOMMUNIST_ADMIN_ID, MY_TELEGRAM_ID},
}

ALL_ADMIN_IDS = {MY_TELEGRAM_ID, GREYDER_ADMIN_ID, KOMMUNIST_ADMIN_ID}
USERS_DB = set(ALL_ADMIN_IDS)
PENDING_ORDERS = {}

CONFIG_FILE = "config_smartshell.json"
SMARTSHELL_URL = "https://billing.smartshell.gg/api/graphql"


def load_smartshell_config() -> dict:
    if not os.path.exists(CONFIG_FILE):
        defaults = {
            "loc_greyder": {"company_id": 3489, "login": "79968370695", "password": "йфцыув321"},
            "loc_kommunist": {"company_id": 0, "login": "", "password": ""},
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(defaults, f, ensure_ascii=False, indent=2)
        return defaults
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as err:
        logging.error(f"Ошибка загрузки конфигурационного файла {CONFIG_FILE}: {err}")
        return {}


def save_smartshell_config(data: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


SMARTSHELL_DATA = load_smartshell_config()

# =====================================================================
# 2. КАРТЫ ЗАЛОВ
# =====================================================================
GREYDER_ZONES = {
    "VIP Пятерка": ["4", "5", "6", "7", "8"],
    "VIP Четверка": ["9", "10", "11", "12"],
    "VIP Тройка": ["13", "14", "15"],
    "VIP Одиночка 17": ["17"],
    "MVP Solo 1": ["1"],
    "MVP Duo (2, 3)": ["2", "3"],
    "MVP Solo 16": ["16"],
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
    "🎮 Зона PlayStation 5": ["PS5"],
    "🥽 VR Площадки (4 зоны)": ["VR 1", "VR 2", "VR 3", "VR 4"],
}

CLUBS = {
    "loc_greyder": {
        "name": "📍 Грейдерная, 1 (2 этаж)",
        "phone": "+7 960 856 06 14",
        "admin_tg": "@NextGenAst",
        "zones": GREYDER_ZONES,
        "price_photo": "price_greyder.jpg",
        "info_caption": (
            "🏢 <b>Филиал: ул. Грейдерная, 1 (2 этаж)</b>\n\n"
            "💻 <b>Конфигурация оборудования:</b>\n\n"
            "👑 <b>VIP-зона:</b>\n"
            "• Видеокарты: RTX 3060 Ti\n"
            "• Память: 16 GB RAM\n"
            "• Мониторы: 165Hz\n\n"
            "🔥 <b>MVP-зона (Solo / Duo / Trio):</b>\n"
            "• Видеокарты: RTX 3070 Ti / RTX 4070 Ti\n"
            "• Память: 16 GB RAM\n"
            "• Мониторы: 240Hz – 320Hz\n"
            "• Периферия: Фулл беспроводные девайсы\n\n"
            "🎮 <b>Консоли:</b> 2x PlayStation 5\n\n"
            "📄 <i>Прайс-лист прикреплен выше 👆</i>"
        ),
    },
    "loc_kommunist": {
        "name": "📍 Коммунистическая, 7",
        "phone": "89064560613",
        "admin_tg": "@genesisvrast",
        "zones": KOMMUNIST_ZONES,
        "price_photo": "price_kommunist.jpg",
        "info_caption": (
            "🏢 <b>Филиал: ул. Коммунистическая, 7</b>\n\n"
            "💻 <b>Конфигурация оборудования:</b>\n\n"
            "🔹 <b>Обычная зона (Standard):</b>\n"
            "• Видеокарты: RTX 5060 Ti\n"
            "• Память: 16 GB RAM\n"
            "• Мониторы: 180Hz / 240Hz\n\n"
            "👑 <b>VIP-зона:</b>\n"
            "• Видеокарты: RTX 5060 Ti\n"
            "• Память: 32 GB RAM\n"
            "• Мониторы: 280Hz / 360Hz\n\n"
            "🎮 <b>Консоли:</b> PlayStation 5\n"
            "🥽 <b>Виртуальная реальность:</b> 4x VR-площадки\n\n"
            "📄 <i>Прайс-лист прикреплен выше 👆</i>"
        ),
    },
}

# =====================================================================
# 3. SMARTSHELL API КЛИЕНТ
# =====================================================================
def normalize_alias(name: str) -> str:
    s = str(name).strip().upper().replace("№", "").replace(" ", "")
    if "PS5" in s:
        match = re.search(r"\d+", s)
        return f"PS5_{match.group()}" if match else "PS5"
    if "VR" in s:
        match = re.search(r"\d+", s)
        return f"VR_{match.group()}" if match else "VR"
    match = re.search(r"\d+", s)
    return match.group() if match else s


class SmartShellAPI:
    def __init__(self, loc_key: str):
        self.loc_key = loc_key
        self.token = None
        self.token_expire_time = None
        self.hosts_cache = {}

    def _get_credentials(self):
        return SMARTSHELL_DATA.get(self.loc_key, {})

    async def ensure_auth(self, session: aiohttp.ClientSession) -> bool:
        creds = self._get_credentials()
        cid = creds.get("company_id")
        login = creds.get("login")
        password = creds.get("password")

        if not cid or not login or not password:
            return False

        if self.token and self.token_expire_time and datetime.now(timezone.utc) < self.token_expire_time:
            return True

        headers = {"Content-Type": "application/json", "User-Agent": f"company_id={cid}"}
        mutation = """
        mutation Login($input: LoginInput!) {
            login(input: $input) {
                access_token
            }
        }
        """
        variables = {"input": {"login": str(login), "password": str(password), "company_id": int(cid)}}

        try:
            async with session.post(SMARTSHELL_URL, json={"query": mutation, "variables": variables}, headers=headers, timeout=6) as resp:
                if resp.status != 200:
                    return False
                data = await resp.json()
                if "errors" in data or not data.get("data", {}).get("login"):
                    return False

                self.token = data["data"]["login"]["access_token"]
                self.token_expire_time = datetime.now(timezone.utc) + timedelta(hours=10)
                return True
        except Exception as err:
            logging.error(f"Авторизация в SmartShell [{self.loc_key}] завершилась с ошибкой: {err}")
            return False

    async def get_hosts_status(self) -> dict:
        status_map = {}
        creds = self._get_credentials()
        cid = creds.get("company_id")
        if not cid:
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

                headers = {
                    "Content-Type": "application/json",
                    "User-Agent": f"company_id={cid}",
                    "Authorization": f"Bearer {self.token}",
                }
                async with session.post(SMARTSHELL_URL, json={"query": query}, headers=headers, timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        hosts = data.get("data", {}).get("hosts", []) or []
                        for h in hosts:
                            alias_key = normalize_alias(h.get("alias", ""))
                            self.hosts_cache[alias_key] = h.get("id")
                            sessions = h.get("client_sessions", []) or []
                            active = [s for s in sessions if s.get("time_left") and s.get("time_left") > 0]
                            if active:
                                end_dt = datetime.now() + timedelta(seconds=active[0]["time_left"])
                                status_map[alias_key] = f"до ~{end_dt.strftime('%H:%M')}"
                            else:
                                status_map[alias_key] = None
        except Exception as err:
            logging.error(f"Ошибка получения хостов SmartShell: {err}")
        return status_map

    async def create_booking_api(self, places_list: list, client_name: str, client_phone: str, time_info: str) -> tuple[bool, str]:
        creds = self._get_credentials()
        cid = creds.get("company_id")
        if not cid:
            return False, "SmartShell не привязан к этому клубу."

        host_ids = []
        for p in places_list:
            key = normalize_alias(p)
            hid = self.hosts_cache.get(key)
            if not hid:
                await self.get_hosts_status()
                hid = self.hosts_cache.get(key)
            if hid:
                host_ids.append(int(hid))

        if not host_ids:
            return False, "Выбранные ПК не найдены в базе оборудования."

        # Начальная точка: через 20 минут в UTC
        dt_from = datetime.now(timezone.utc) + timedelta(minutes=20)
        dt_to = dt_from + timedelta(hours=2)

        mutation = """
        mutation CreateBooking($input: BookingInput!) {
            createBooking(input: $input) {
                id
                status
            }
        }
        """

        async with aiohttp.ClientSession() as session:
            if not await self.ensure_auth(session):
                return False, "Ошибка авторизации API SmartShell."

            headers = {
                "Content-Type": "application/json",
                "User-Agent": f"company_id={cid}",
                "Authorization": f"Bearer {self.token}",
            }

            # 2 попытки: при ошибке "from must be after" сдвигаем время на то, что требует шелл + 2 минуты
            for attempt in range(2):
                iso_from = dt_from.strftime("%Y-%m-%dT%H:%M:%S.000Z")
                iso_to = dt_to.strftime("%Y-%m-%dT%H:%M:%S.000Z")

                variables = {
                    "input": {
                        "hosts": host_ids,
                        "from": iso_from,
                        "to": iso_to,
                        "comment": f"ТГ-Бот | Клиент: {client_name} | Тел: {client_phone} | {time_info}",
                    }
                }

                try:
                    async with session.post(SMARTSHELL_URL, json={"query": mutation, "variables": variables}, headers=headers, timeout=8) as resp:
                        res = await resp.json()
                        if "errors" in res:
                            err_msg = res["errors"][0].get("message", "Ошибка API")
                            
                            # Автоматический перехват бага валидации времени
                            match = re.search(r"after\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})", err_msg)
                            if match and attempt == 0:
                                parsed_req = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                                dt_from = parsed_req + timedelta(minutes=2)
                                dt_to = dt_from + timedelta(hours=2)
                                logging.info(f"SmartShell запросил сдвиг даты: переотправка с {dt_from}")
                                continue

                            return False, f"❌ Отказ SmartShell: {err_msg}"

                        booking_id = res.get("data", {}).get("createBooking", {}).get("id")
                        status_res = res.get("data", {}).get("createBooking", {}).get("status", "OK")
                        return True, f"✅ Создана бронь в SmartShell: #{booking_id} ({status_res})"
                except Exception as err:
                    logging.error(f"Ошибка запроса createBooking: {err}")
                    return False, f"❌ Исключение при отправке брони: {err}"

        return False, "Не удалось согласовать время брони с сервером SmartShell."


CLIENTS = {
    "loc_greyder": SmartShellAPI("loc_greyder"),
    "loc_kommunist": SmartShellAPI("loc_kommunist"),
}

# =====================================================================
# 4. FSM СОСТОЯНИЯ
# =====================================================================
class BookingStates(StatesGroup):
    location = State()
    zone = State()
    selecting_pcs = State()
    client_name = State()
    date_time = State()
    duration = State()
    phone = State()


class SmartShellSetupStates(StatesGroup):
    choose_branch = State()
    input_cid = State()
    input_login = State()
    input_pass = State()


class FeedbackStates(StatesGroup):
    loc = State()
    text = State()


class BroadcastStates(StatesGroup):
    message = State()


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


def is_super_admin(user: types.User) -> bool:
    return user.id == MY_TELEGRAM_ID


def is_admin(user: types.User) -> bool:
    return user.id in ALL_ADMIN_IDS

# =====================================================================
# 5. КЛАВИАТУРЫ
# =====================================================================
def get_main_keyboard(user: types.User) -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text="⚡ Забронировать ПК / PS5 / VR 📍")],
        [KeyboardButton(text="💻 Железо и Прайс"), KeyboardButton(text="🎁 Акции и Бонусы")],
        [KeyboardButton(text="🎮 Список игр"), KeyboardButton(text="☎️ Контакты и адреса")],
    ]
    if is_admin(user):
        kb.append([KeyboardButton(text="⚙️ Настройки SmartShell"), KeyboardButton(text="📢 Рассылка")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def get_location_select_kb(prefix: str) -> InlineKeyboardMarkup:
    kb = [[InlineKeyboardButton(text=data["name"], callback_data=f"{prefix}_{key}")] for key, data in CLUBS.items()]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def get_club_zones_keyboard(club_key: str, real_status: dict) -> InlineKeyboardMarkup:
    zones = CLUBS[club_key]["zones"]
    buttons = []
    for zone_name, places in zones.items():
        busy_places = [p for p in places if real_status.get(normalize_alias(p)) is not None]
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


def get_multi_pcs_keyboard(club_key: str, zone_name: str, selected_list: list, real_status: dict) -> InlineKeyboardMarkup:
    places = CLUBS[club_key]["zones"][zone_name]
    buttons = []
    for place in places:
        busy_info = real_status.get(normalize_alias(place))
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


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Отменить")]], resize_keyboard=True)

# =====================================================================
# 6. БАЗОВЫЕ КОМАНДЫ
# =====================================================================
@dp.message(CommandStart())
@dp.message(F.text == "🔄 Вернуться в меню")
@dp.message(F.text == "❌ Отменить")
async def cmd_start_or_back(message: types.Message, state: FSMContext):
    await state.clear()
    USERS_DB.add(message.from_user.id)
    await message.answer(
        "👋 <b>Добро пожаловать в сеть клубов!</b>\nВыберите раздел меню:",
        reply_markup=get_main_keyboard(message.from_user),
        parse_mode="HTML",
    )


@dp.callback_query(F.data == "cancel_action")
async def cancel_action_cb(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.message.answer("Действие отменено.", reply_markup=get_main_keyboard(callback.from_user))
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
            reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🔄 Вернуться в меню")]], resize_keyboard=True),
            parse_mode="HTML",
        )
    except Exception:
        await callback.message.answer(
            club["info_caption"],
            reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🔄 Вернуться в меню")]], resize_keyboard=True),
            parse_mode="HTML",
        )
    await callback.answer()


@dp.message(F.text == "☎️ Контакты и адреса")
async def send_contacts(message: types.Message):
    text = "🏢 <b>Наши филиалы:</b>\n\n"
    for _, club in CLUBS.items():
        text += (
            f"<b>{club['name']}</b>\n"
            f"🕒 Режим: 24/7 (круглосуточно)\n"
            f"📞 Телефон: <code>{club['phone']}</code>\n"
            f"💬 TG админа: {club['admin_tg']}\n\n"
        )
    await message.answer(
        text,
        reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🔄 Вернуться в меню")]], resize_keyboard=True),
        parse_mode="HTML",
    )


@dp.message(F.text == "🎁 Акции и Бонусы")
async def send_bonuses(message: types.Message):
    text = (
        "🔥 <b>Акции и Бонусная программа сети:</b>\n\n"
        "🎁 <b>При регистрации:</b> 2 часа игры бесплатно!\n"
        "🤝 <b>Приведи друга:</b> по 100 бонусов каждому на баланс!\n"
        "⭐ <b>Отзыв на 2ГИС / Яндекс.Картах:</b> 150 бонусов!\n"
        "📱 <b>Подписка на Telegram-канал:</b> 100 бонусов!\n"
        "💳 <b>Кешбэк 10%:</b> при пополнении от 1000 рублей!\n"
        "🎂 <b>День Рождения:</b> удвоим баланс (7 дней до и после)!\n\n"
        "💰 <i>1 бонус = 1 рубль. Оплата до 100% игрового времени!</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🤫 Секретная акция", callback_data="secret_promo_info")]])
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
    text = "💬 <b>Популярные установленные игры:</b>\n\n• CS2 / Dota 2 / Fortnite\n• Apex / PUBG / Rust / EFT\n\n<i>Нужна другая игра? Жми кнопку ниже:</i>"
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="💡 Предложить установить игру")], [KeyboardButton(text="🔄 Вернуться в меню")]],
        resize_keyboard=True,
    )
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@dp.message(F.text == "💡 Предложить установить игру")
async def start_game_request(message: types.Message, state: FSMContext):
    await state.set_state(FeedbackStates.loc)
    await message.answer("Выберите филиал:", reply_markup=get_location_select_kb("fbloc"))


@dp.callback_query(F.data.startswith("fbloc_"), FeedbackStates.loc)
async def process_feedback_loc(callback: CallbackQuery, state: FSMContext):
    loc_key = callback.data.replace("fbloc_", "")
    await state.update_data(loc_key=loc_key, location=CLUBS[loc_key]["name"])
    await state.set_state(FeedbackStates.text)
    await callback.message.delete()
    await callback.message.answer(
        f"Выбран клуб: <b>{CLUBS[loc_key]['name']}</b>\nНапишите название игры:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@dp.message(FeedbackStates.text)
async def process_feedback(message: types.Message, state: FSMContext):
    data = await state.get_data()
    loc_key = data.get("loc_key", "loc_greyder")
    await state.clear()

    card = (
        f"🎮 <b>ЗАПРОС НА УСТАНОВКУ ИГРЫ</b>\n\n"
        f"🏢 <b>Филиал:</b> {data.get('location', '')}\n"
        f"👤 <b>От:</b> {message.from_user.full_name} (@{message.from_user.username or message.from_user.id})\n"
        f"📝 <b>Игра:</b> <i>{message.text}</i>"
    )
    for adm in BRANCH_RECIPIENTS.get(loc_key, {MY_TELEGRAM_ID}):
        try:
            await bot.send_message(chat_id=adm, text=card, parse_mode="HTML")
        except Exception:
            pass
    await message.answer("Спасибо! Передали заявку админам филиала 🙌", reply_markup=get_main_keyboard(message.from_user))

# =====================================================================
# 7. ПРОЦЕСС БРОНИРОВАНИЯ
# =====================================================================
@dp.message(F.text == "⚡ Забронировать ПК / PS5 / VR 📍")
async def start_booking(message: types.Message, state: FSMContext):
    await state.set_state(BookingStates.location)
    await message.answer("Выберите филиал для бронирования:", reply_markup=get_location_select_kb("bookloc"))


@dp.callback_query(F.data.startswith("bookloc_"), BookingStates.location)
async def booking_location_chosen(callback: CallbackQuery, state: FSMContext):
    club_key = callback.data.replace("bookloc_", "")
    
    # Сразу получаем реальные статусы из шелла
    client = CLIENTS.get(club_key)
    real_status = await client.get_hosts_status() if client else {}

    await state.update_data(location=CLUBS[club_key]["name"], loc_key=club_key, real_status=real_status)
    await state.set_state(BookingStates.zone)

    await callback.message.edit_text(
        f"<b>{CLUBS[club_key]['name']}</b>\nГде планируете тащить? Выбирайте зону:",
        reply_markup=get_club_zones_keyboard(club_key, real_status),
        parse_mode="HTML",
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("zonebusy_"), BookingStates.zone)
async def zone_busy_alert(callback: CallbackQuery):
    await callback.answer("❌ Вся эта зона сейчас наглухо занята! Выберите другую.", show_alert=True)


@dp.callback_query(F.data == "back_to_zones", BookingStates.selecting_pcs)
async def back_to_zones_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    club_key = data["loc_key"]
    real_status = data.get("real_status", {})
    await state.set_state(BookingStates.zone)
    await callback.message.edit_text(
        f"<b>{CLUBS[club_key]['name']}</b>\nВыберите зону:",
        reply_markup=get_club_zones_keyboard(club_key, real_status),
        parse_mode="HTML",
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("selectzone_"), BookingStates.zone)
async def choose_pc_in_zone(callback: CallbackQuery, state: FSMContext):
    zone_name = callback.data.replace("selectzone_", "")
    data = await state.get_data()
    club_key = data["loc_key"]
    real_status = data.get("real_status", {})

    await state.update_data(zone=zone_name, selected_pcs=[])
    await state.set_state(BookingStates.selecting_pcs)

    await callback.message.edit_text(
        f"Комната: <b>{zone_name}</b>\nЗеленые места свободны. Кликайте на нужные (можно сразу несколько):",
        reply_markup=get_multi_pcs_keyboard(club_key, zone_name, [], real_status),
        parse_mode="HTML",
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("pcbusy_"), BookingStates.selecting_pcs)
async def pc_busy_alert(callback: CallbackQuery, state: FSMContext):
    place_name = callback.data.replace("pcbusy_", "")
    data = await state.get_data()
    real_status = data.get("real_status", {})
    until = real_status.get(normalize_alias(place_name), "занято")
    await callback.answer(f"❌ Место {place_name} сейчас занято ({until})! Выберите зеленое.", show_alert=True)


@dp.callback_query(F.data.startswith("togglepc_"), BookingStates.selecting_pcs)
async def toggle_pc_selection(callback: CallbackQuery, state: FSMContext):
    place_name = callback.data.replace("togglepc_", "")
    data = await state.get_data()
    selected = data.get("selected_pcs", [])

    if place_name in selected:
        selected.remove(place_name)
    else:
        selected.append(place_name)

    await state.update_data(selected_pcs=selected)
    await callback.message.edit_reply_markup(
        reply_markup=get_multi_pcs_keyboard(data["loc_key"], data["zone"], selected, data.get("real_status", {}))
    )
    await callback.answer()


@dp.callback_query(F.data == "finish_pc_selection", BookingStates.selecting_pcs)
async def finish_selection_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("selected_pcs", [])
    if not selected:
        await callback.answer("Выберите хотя бы одно место!", show_alert=True)
        return

    formatted = [f"ПК №{p}" if "PS5" not in p and "VR" not in p else p for p in selected]
    places_str = ", ".join(formatted)

    await state.update_data(pc_number=places_str, raw_places=selected)
    await state.set_state(BookingStates.client_name)

    await callback.message.delete()
    await callback.message.answer(
        f"Заряжаем места ({len(selected)} шт.): <b>{places_str}</b>\n\n👤 <b>На какое имя оформить бронь?</b>",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@dp.message(BookingStates.client_name)
async def booking_client_name(message: types.Message, state: FSMContext):
    await state.update_data(client_name=message.text.strip())
    await state.set_state(BookingStates.date_time)
    await message.answer(
        "🕒 <b>К какому времени подтянетесь?</b> (например: <i>Сегодня к 20:30</i>):",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
    )


@dp.message(BookingStates.date_time)
async def booking_datetime(message: types.Message, state: FSMContext):
    await state.update_data(date_time=message.text.strip())
    await state.set_state(BookingStates.duration)
    await message.answer(
        "⏳ <b>На сколько часов садитесь?</b> (например: <i>3 часа</i> / <i>Пакет Ночь</i>):",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
    )


@dp.message(BookingStates.duration)
async def booking_duration(message: types.Message, state: FSMContext):
    await state.update_data(duration=message.text.strip())
    await state.set_state(BookingStates.phone)
    await message.answer(
        "📞 <b>Оставьте номер телефона для связи:</b>",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
    )


@dp.message(BookingStates.phone)
async def booking_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text.strip())
    data = await state.get_data()
    loc_key = data["loc_key"]
    await state.clear()

    user = message.from_user
    username_str = f"@{user.username}" if user.username else "нет username"

    # Сохраняем в буфер для передачи данных в шелл
    PENDING_ORDERS[user.id] = {
        "loc_key": loc_key,
        "places": data.get("raw_places", []),
        "client_name": data["client_name"],
        "phone": data["phone"],
        "duration": data["duration"],
        "time": data["date_time"],
    }

    await message.answer(
        "🚀 <b>Заявка улетела админу!</b> Сейчас подтвердим и заброним место.",
        reply_markup=get_main_keyboard(user),
        parse_mode="HTML",
    )

    admin_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Принять (и в SmartShell)", callback_data=f"adm_ok_{user.id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"adm_no_{user.id}"),
            ]
        ]
    )
    admin_card = (
        "🚨 <b>НОВАЯ ЗАЯВКА НА БРОНЬ</b>\n\n"
        f"🏢 <b>Филиал:</b> {data['location']}\n"
        f"🎯 <b>Места:</b> {data['zone']} 👉 <b>{data['pc_number']}</b>\n"
        f"👤 <b>Имя для брони:</b> <b>{data['client_name']}</b>\n"
        f"💬 <b>Телеграм:</b> {user.full_name} ({username_str})\n"
        f"📞 <b>Телефон:</b> <code>{data['phone']}</code>\n"
        f"🕒 <b>Время:</b> {data['date_time']}\n"
        f"⏳ <b>Длительность:</b> {data['duration']}"
    )

    for adm in BRANCH_RECIPIENTS.get(loc_key, {MY_TELEGRAM_ID}):
        try:
            await bot.send_message(chat_id=adm, text=admin_card, reply_markup=admin_kb, parse_mode="HTML")
        except Exception as err:
            logging.error(f"Не удалось доставить заявку админу {adm}: {err}")

# =====================================================================
# 8. ДЕЙСТВИЯ АДМИНИСТРАТОРА (МУТАЦИЯ В SMARTSHELL)
# =====================================================================
@dp.callback_query(F.data.startswith("adm_ok_"))
async def admin_approve(callback: CallbackQuery):
    if not is_admin(callback.from_user):
        await callback.answer("⛔ Вы не администратор!", show_alert=True)
        return

    client_id = int(callback.data.split("_")[2])
    order = PENDING_ORDERS.get(client_id)
    ss_status_text = ""

    if order:
        client = CLIENTS.get(order["loc_key"])
        if client:
            ok, log_res = await client.create_booking_api(
                places_list=order["places"],
                client_name=order["client_name"],
                client_phone=order["phone"],
                time_info=f"{order['time']} ({order['duration']})",
            )
            ss_status_text = f"\n\n<b>SmartShell:</b>\n{log_res}"

    new_text = f"{callback.message.text}\n\n🟢 <b>ПРИНЯТА (Админ: {callback.from_user.first_name})</b>{ss_status_text}"
    await callback.message.edit_text(new_text, parse_mode="HTML")

    try:
        await bot.send_message(chat_id=client_id, text="🎉 <b>Ваша бронь подтверждена!</b> Ждем в клубе, приятной игры!", parse_mode="HTML")
    except Exception:
        pass
    await callback.answer("Бронь зафиксирована!")


@dp.callback_query(F.data.startswith("adm_no_"))
async def admin_reject(callback: CallbackQuery):
    if not is_admin(callback.from_user):
        await callback.answer("⛔ Вы не администратор!", show_alert=True)
        return

    client_id = int(callback.data.split("_")[2])
    PENDING_ORDERS.pop(client_id, None)

    await callback.message.edit_text(
        f"{callback.message.text}\n\n🔴 <b>ОТКЛОНЕНА (Админ: {callback.from_user.first_name})</b>",
        parse_mode="HTML",
    )
    try:
        await bot.send_message(chat_id=client_id, text="😔 К сожалению, на выбранное время все места заняты.", parse_mode="HTML")
    except Exception:
        pass
    await callback.answer("Заявка отклонена!")

# =====================================================================
# 9. НАСТРОЙКА SMARTSHELL ИЗ TELEGRAM
# =====================================================================
@dp.message(F.text == "⚙️ Настройки SmartShell")
async def ss_settings_menu(message: types.Message):
    if not is_super_admin(message.from_user):
        await message.answer("⛔ Доступно только главному администратору.")
        return

    text = "⚙️ <b>Параметры интеграции SmartShell:</b>\n\n"
    for key, data in SMARTSHELL_DATA.items():
        name = CLUBS.get(key, {}).get("name", key)
        text += (
            f"🏢 <b>{name}</b>:\n"
            f"• Club ID: <code>{data.get('company_id', 'не задан')}</code>\n"
            f"• Логин: <code>{data.get('login', 'не задан')}</code>\n"
            f"• Пароль: <code>••••••••</code>\n\n"
        )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Настроить Грейдерную", callback_data="setupss_loc_greyder")],
            [InlineKeyboardButton(text="✏️ Настроить Коммунистическую", callback_data="setupss_loc_kommunist")],
            [InlineKeyboardButton(text="🔄 Проверить подключение", callback_data="check_ss_connect")],
        ]
    )
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@dp.callback_query(F.data.startswith("setupss_"))
async def ss_start_branch_setup(callback: CallbackQuery, state: FSMContext):
    if not is_super_admin(callback.from_user):
        return
    loc_key = callback.data.replace("setupss_", "")
    await state.update_data(edit_loc=loc_key)
    await state.set_state(SmartShellSetupStates.input_cid)
    await callback.message.answer(
        f"Настройка для <b>{CLUBS[loc_key]['name']}</b>:\n\nВведите <b>Club ID (Company ID)</b>:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@dp.message(SmartShellSetupStates.input_cid)
async def ss_input_cid(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("ID клуба должен состоять исключительно из цифр:")
        return
    await state.update_data(cid=int(message.text))
    await state.set_state(SmartShellSetupStates.input_login)
    await message.answer("Введите <b>номер телефона</b> (логин):", reply_markup=get_cancel_keyboard(), parse_mode="HTML")


@dp.message(SmartShellSetupStates.input_login)
async def ss_input_login(message: types.Message, state: FSMContext):
    login = re.sub(r"\D", "", message.text)
    await state.update_data(login=login)
    await state.set_state(SmartShellSetupStates.input_pass)
    await message.answer("Введите <b>пароль</b> от SmartShell:", reply_markup=get_cancel_keyboard(), parse_mode="HTML")


@dp.message(SmartShellSetupStates.input_pass)
async def ss_input_pass(message: types.Message, state: FSMContext):
    data = await state.get_data()
    loc_key = data["edit_loc"]
    cid = data["cid"]
    login = data["login"]
    password = message.text.strip()
    await state.clear()

    SMARTSHELL_DATA[loc_key] = {"company_id": cid, "login": login, "password": password}
    save_smartshell_config(SMARTSHELL_DATA)

    if loc_key in CLIENTS:
        CLIENTS[loc_key].token = None

    await message.answer(
        f"✅ Конфиг сохранен в <code>{CONFIG_FILE}</code>. Проверяем связь...",
        reply_markup=get_main_keyboard(message.from_user),
        parse_mode="HTML",
    )
    async with aiohttp.ClientSession() as session:
        if await CLIENTS[loc_key].ensure_auth(session):
            hosts = await CLIENTS[loc_key].get_hosts_status()
            await message.answer(f"🎉 <b>Связь установлена!</b> Доступно хостов: {len(hosts)}", parse_mode="HTML")
        else:
            await message.answer("⚠️ Не удалось авторизоваться. Проверьте ID, логин и пароль.", parse_mode="HTML")


@dp.callback_query(F.data == "check_ss_connect")
async def ss_test_all(callback: CallbackQuery):
    if not is_super_admin(callback.from_user):
        return
    await callback.message.answer("⏳ Проверка подключения ко всем базам...")
    report = []
    async with aiohttp.ClientSession() as session:
        for loc_key, client in CLIENTS.items():
            name = CLUBS[loc_key]["name"]
            if await client.ensure_auth(session):
                hosts = await client.get_hosts_status()
                report.append(f"🟢 <b>{name}</b>: Успешно (ПК: {len(hosts)})")
            else:
                report.append(f"🔴 <b>{name}</b>: Ошибка доступа")
    await callback.message.answer("\n\n".join(report), parse_mode="HTML")
    await callback.answer()

# =====================================================================
# 10. РАССЫЛКА
# =====================================================================
@dp.message(F.text == "📢 Рассылка")
async def start_broadcast(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user):
        return
    await state.set_state(BroadcastStates.message)
    await message.answer("📢 Введите текст для общей рассылки:", reply_markup=get_cancel_keyboard())


@dp.message(BroadcastStates.message)
async def send_broadcast(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user):
        return
    await state.clear()
    sent = 0
    for uid in USERS_DB:
        try:
            await bot.send_message(chat_id=uid, text=message.text, parse_mode="HTML")
            sent += 1
            await asyncio.sleep(0.04)
        except Exception:
            pass
    await message.answer(f"✅ Доставлено: <b>{sent}</b> пользователям.", reply_markup=get_main_keyboard(message.from_user), parse_mode="HTML")

# =====================================================================
# 11. ТОЧКА ВХОДА
# =====================================================================
async def main():
    logging.info("Инициализация и запуск бота...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
