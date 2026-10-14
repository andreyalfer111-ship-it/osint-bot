import os
import sqlite3
import telebot
import requests
import re

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("Не найден токен бота!")

bot = telebot.TeleBot(TOKEN)

# Инициализация базы данных SQLite для истории запросов
def init_db():
    conn = sqlite3.connect("osint_history.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            query_type TEXT,
            query_text TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

def save_to_history(user_id, username, q_type, q_text):
    try:
        conn = sqlite3.connect("osint_history.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO history (user_id, username, query_type, query_text) VALUES (?, ?, ?, ?)",
                       (user_id, username, q_type, q_text))
        conn.commit()
        conn.close()
    except Exception:
        pass

# Платформы для массового поиска по никнейму
SOCIAL_PLATFORMS = {
    "GitHub": "https://github.com/{}",
    "TikTok": "https://www.tiktok.com/@{}",
    "Instagram": "https://www.instagram.com/{}",
    "Twitter/X": "https://twitter.com/{}",
    "Reddit": "https://www.reddit.com/user/{}",
    "Pikabu": "https://pikabu.co/@{}",
    "Habr": "https://habr.com/ru/users/{}/",
    "Steam": "https://steamcommunity.com/id/{}",
    "Telegram": "https://t.me/{}"
}

def get_main_menu():
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    btn1 = telebot.types.InlineKeyboardButton("👤 Поиск по нику", callback_data="menu_username")
    btn2 = telebot.types.InlineKeyboardButton("📞 Поиск по телефону", callback_data="menu_phone")
    btn3 = telebot.types.InlineKeyboardButton("🌐 Анализ IP", callback_data="menu_ip")
    btn4 = telebot.types.InlineKeyboardButton("🌐 Проверка домена", callback_data="menu_domain")
    btn5 = telebot.types.InlineKeyboardButton("📷 Инспектор фото / Ссылка", callback_data="menu_inspector")
    btn6 = telebot.types.InlineKeyboardButton("📜 История", callback_data="menu_history")
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6)
    return markup

def get_back_markup():
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("🔙 Главное меню", callback_data="menu_back"))
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(
        message.chat.id,
        "🛡️ **OSINT COMMAND CENTER**\n\n"
        "Выберите, с чего хотите начать расследование. У вас есть разные точки входа:",
        reply_markup=get_main_menu(),
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id

    if call.data == "menu_back":
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="🛡️ **OSINT COMMAND CENTER**\n\nГлавное меню:",
            reply_markup=get_main_menu(),
            parse_mode="Markdown"
        )
    elif call.data == "menu_username":
        msg = bot.send_message(chat_id, "👤 Введите **никнейм** (цепочка по соцсетям):", reply_markup=get_back_markup())
        bot.register_next_step_handler(msg, process_username_search)
    elif call.data == "menu_phone":
        msg = bot.send_message(chat_id, "📞 Введите **номер телефона** (например, +79991234567):", reply_markup=get_back_markup())
        bot.register_next_step_handler(msg, process_phone_search)
    elif call.data == "menu_ip":
        msg = bot.send_message(chat_id, "🌐 Введите **IP-адрес** для геолокации:", reply_markup=get_back_markup())
        bot.register_next_step_handler(msg, process_ip_search)
    elif call.data == "menu_domain":
        msg = bot.send_message(chat_id, "🌐 Введите **домен** сайта:", reply_markup=get_back_markup())
        bot.register_next_step_handler(msg, process_domain_search)
    elif call.data == "menu_inspector":
        bot.send_message(
            chat_id, 
            "📷 **Инспектор объектов:**\n\n"
            "Отправьте в чат фотографию, перешлите сообщение от пользователя или отправьте контакт, "
            "чтобы извлечь скрытые метаданные и Telegram ID.",
            reply_markup=get_back_markup()
        )
    elif call.data == "menu_history":
        show_history(call.message)

def show_history(message):
    user_id = message.chat.id
    try:
        conn = sqlite3.connect("osint_history.db")
        cursor = conn.cursor()
        cursor.execute("SELECT query_type, query_text, timestamp FROM history WHERE user_id = ? ORDER BY id DESC LIMIT 5", (user_id,))
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            bot.send_message(user_id, "📜 История пуста.", reply_markup=get_back_markup())
            return
            
        report = ["📜 **Последние запросы:**\n"]
        for r_type, r_text, r_time in rows:
            report.append(f"• `{r_time}` | **{r_type}**: `{r_text}`")
            
        bot.send_message(user_id, "\n".join(report), parse_mode="Markdown", reply_markup=get_back_markup())
    except Exception:
        bot.send_message(user_id, "❌ Ошибка чтения истории.", reply_markup=get_back_markup())

def process_username_search(message):
    if not message.text or message.text.startswith('/'):
        return
    query = message.text.strip().lstrip('@')
    user = message.from_user.username or str(message.from_user.id)
    save_to_history(message.chat.id, user, "Никнейм", query)
    
    status_msg = bot.send_message(message.chat.id, f"🔍 Сканирую платформы для ника `{query}`...")
    report = [f"📊 **Карточка по нику:** `{query}`\n", "🌐 **Результаты поиска:**"]
    headers = {"User-Agent": "Mozilla/5.0"}

    for platform, url_template in SOCIAL_PLATFORMS.items():
        target_url = url_template.format(query)
        try:
            response = requests.get(target_url, headers=headers, timeout=3, allow_redirects=True)
            if response.status_code == 200:
                if platform == "Telegram" and "if you have Telegram" in response.text:
                    report.append(f"• {platform}: 🔴 Свободен")
                else:
                    report.append(f"• {platform}: 🟢 [Найден]({target_url})")
            else:
                report.append(f"• {platform}: 🔴 Не найден")
        except Exception:
            report.append(f"• {platform}: ⚪ Ошибка")

    bot.send_message(message.chat.id, "\n".join(report), parse_mode="Markdown", disable_web_page_preview=True, reply_markup=get_back_markup())

def process_phone_search(message):
    if not message.text or message.text.startswith('/'):
        return
    phone = re.sub(r'\D', '', message.text)
    user = message.from_user.username or str(message.from_user.id)
    save_to_history(message.chat.id, user, "Телефон", f"+{phone}")
    
    report = [f"📞 **Карточка телефона:** `+{phone}`\n"]
    if phone.startswith('7') and len(phone) == 11:
        report.append("• Страна: Россия / Казахстан (+7)")
        report.append(f"• Код оператора (DEF): `{phone[1:4]}`")
        report.append(f"• Номер абонента: `{phone[4:]}`")
    else:
        report.append("• Формат: Международный.")
    
    report.append("\n💡 *Подсказка:* Для связки используйте инспектора при пересылке контакта.")
    bot.send_message(message.chat.id, "\n".join(report), parse_mode="Markdown", reply_markup=get_back_markup())

def process_ip_search(message):
    if not message.text or message.text.startswith('/'):
        return
    ip = message.text.strip()
    user = message.from_user.username or str(message.from_user.id)
    save_to_history(message.chat.id, user, "IP", ip)
    
    try:
        r = requests.get(f"http://ip-api.com/json/{ip}", timeout=5)
        data = r.json()
        if data.get("status") == "success":
            country = data.get('country', 'Н/Д')
            city = data.get('city', 'Н/Д')
            isp = data.get('isp', 'Н/Д')
            lat = data.get('lat', '')
            lon = data.get('lon', '')
            
            text = (
                f"🌐 **Карточка IP-адреса:** `{ip}`\n\n"
                f"• Страна: `{country}`\n"
                f"• Город: `{city}`\n"
                f"• Провайдер: `{isp}`\n"
                f"• Координаты: `{lat}, {lon}`"
            )
        else:
            text = f"❌ IP `{ip}` не найден."
        bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=get_back_markup())
    except Exception:
        bot.send_message(message.chat.id, "❌ Ошибка IP-анализа.", reply_markup=get_back_markup())

def process_domain_search(message):
    if not message.text or message.text.startswith('/'):
        return
    domain = message.text.strip().replace("https://", "").replace("http://", "").split("/")[0]
    user = message.from_user.username or str(message.from_user.id)
    save_to_history(message.chat.id, user, "Домен", domain)
    
    try:
        r = requests.get(f"https://{domain}", timeout=5, allow_redirects=True)
        server = r.headers.get('Server', 'Не определен')
        cloudflare = 'Активна 🛡️' if 'cloudflare' in server.lower() else 'Нет'
        text = f"🌐 **Домен:** `{domain}`\n• Статус: `{r.status_code}`\n• Сервер: `{server}`\n• Cloudflare: {cloudflare}"
        bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=get_back_markup())
    except Exception:
        bot.send_message(message.chat.id, "❌ Домен недоступен.", reply_markup=get_back_markup())

@bot.message_handler(content_types=['photo', 'video', 'video_note', 'contact', 'document'])
def handle_media(message):
    report = ["📷 **Карточка объекта (Инспектор):**\n"]
    if message.forward_from:
        u = message.forward_from
        report.append(f"• Имя: `{u.first_name} {u.last_name or ''}`")
        report.append(f"• Юзернейм: `@{u.username or 'нет'}`")
        report.append(f"• Telegram ID: `{u.id}`")
    if message.contact:
        c = message.contact
        report.append(f"• Контакт: `{c.first_name}`")
        report.append(f"• Телефон: `+{c.phone_number}`")
        report.append(f"• User ID: `{c.user_id}`")
    if message.content_type == 'photo':
        report.append(f"• Фото file_id: `{message.photo[-1].file_id}`")
        
    bot.send_message(message.chat.id, "\n".join(report), parse_mode="Markdown", reply_markup=get_back_markup())

@bot.message_handler(func=lambda m: m.forward_from is not None)
def handle_forwarded_text(message):
    u = message.forward_from
    text = (
        f"📋 **Карточка пересланного сообщения:**\n\n"
        f"• Имя: `{u.first_name} {u.last_name or ''}`\n"
        f"• Юзернейм: `@{u.username or 'отсутствует'}`\n"
        f"• Telegram ID: `{u.id}`\n"
        f"• Тип: {'Бот' if u.is_bot else 'Пользователь'}"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=get_back_markup())

if __name__ == "__main__":
    bot.infinity_polling()
