import os
import sqlite3
import telebot
import requests
import re

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("Не найден токен бота!")

bot = telebot.TeleBot(TOKEN)

# Инициализация базы данных для истории
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

# Главное меню с удобными кнопками
def get_main_menu():
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    btn1 = telebot.types.InlineKeyboardButton("👤 Поиск по нику", callback_data="menu_username")
    btn2 = telebot.types.InlineKeyboardButton("🌐 Веб-упоминания", callback_data="menu_websearch")
    btn3 = telebot.types.InlineKeyboardButton("📞 Анализ телефона", callback_data="menu_phone")
    btn4 = telebot.types.InlineKeyboardButton("🌐 Проверка домена", callback_data="menu_domain")
    btn5 = telebot.types.InlineKeyboardButton("👁️ Инспектор медиа / Forward", callback_data="menu_inspector")
    btn6 = telebot.types.InlineKeyboardButton("📜 История запросов", callback_data="menu_history")
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6)
    return markup

# Кнопка возврата в меню
def get_back_markup():
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("🔙 Главное меню", callback_data="menu_back"))
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(
        message.chat.id,
        "🛡️ **ULTIMATE OSINT COMMAND CENTER**\n\n"
        "Добро пожаловать в единый центр комплексной разведки.\n"
        "Выберите необходимый инструмент в меню ниже:",
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
            text="🛡️ **ULTIMATE OSINT COMMAND CENTER**\n\nГлавное меню:",
            reply_markup=get_main_menu(),
            parse_mode="Markdown"
        )
    elif call.data == "menu_username":
        msg = bot.send_message(chat_id, "👤 Введите **никнейм** для проверки по базам и API:", reply_markup=get_back_markup())
        bot.register_next_step_handler(msg, process_username_search)
    elif call.data == "menu_websearch":
        msg = bot.send_message(chat_id, "🌐 Введите **имя, фразу или ник** для поиска открытых упоминаний в сети:", reply_markup=get_back_markup())
        bot.register_next_step_handler(msg, process_web_search)
    elif call.data == "menu_phone":
        msg = bot.send_message(chat_id, "📞 Введите **номер телефона** (например, +79991234567):", reply_markup=get_back_markup())
        bot.register_next_step_handler(msg, process_phone_search)
    elif call.data == "menu_domain":
        msg = bot.send_message(chat_id, "🌐 Введите **домен** сайта (например, example.com):", reply_markup=get_back_markup())
        bot.register_next_step_handler(msg, process_domain_search)
    elif call.data == "menu_inspector":
        bot.send_message(
            chat_id, 
            "👁️ **Режим инспектора активен!**\n\n"
            "Просто отправьте мне в чат:\n"
            "• Пересланное сообщение от любого пользователя\n"
            "• Фотографию или видео-кружок\n"
            "• Контакт\n\n"
            "Я вытащу все скрытые метаданные и Telegram ID.",
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
            bot.send_message(user_id, "📜 История запросов пуста.", reply_markup=get_back_markup())
            return
            
        report = ["📜 **Последние 5 запросов:**\n"]
        for r_type, r_text, r_time in rows:
            report.append(f"• `{r_time}` | **{r_type}**: `{r_text}`")
            
        bot.send_message(user_id, "\n".join(report), parse_mode="Markdown", reply_markup=get_back_markup())
    except Exception:
        bot.send_message(user_id, "❌ Ошибка чтения истории.", reply_markup=get_back_markup())

# 1. Поиск по нику
def process_username_search(message):
    if message.text and message.text.startswith('/'):
        return
    query = message.text.strip().lstrip('@')
    user = message.from_user.username or str(message.from_user.id)
    save_to_history(message.chat.id, user, "Никнейм", query)
    
    status_msg = bot.send_message(message.chat.id, f"🔍 Анализирую никнейм `{query}`...")
    report = [f"📊 **Отчет по нику:** `{query}`\n"]
    
    try:
        r = requests.get(f"https://api.github.com/users/{query}", headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        if r.status_code == 200:
            data = r.json()
            report.append(f"🟢 **GitHub**: Найден (`{data.get('name', 'Без имени')}`), репозиториев: {data.get('public_repos', 0)}")
        else:
            report.append(f"🔴 **GitHub**: Не найден")
    except Exception:
        pass

    bot.send_message(message.chat.id, "\n".join(report), parse_mode="Markdown", reply_markup=get_back_markup())

# 2. Модуль веб-поиска упоминаний (открытые источники)
def process_web_search(message):
    if message.text and message.text.startswith('/'):
        return
    query = message.text.strip()
    user = message.from_user.username or str(message.from_user.id)
    save_to_history(message.chat.id, user, "Веб-поиск", query)
    
    status_msg = bot.send_message(message.chat.id, f"🌐 Ищу упоминания `{query}` в открытых источниках...")
    
    # Используем публичный поисковый шлюз для анализа упоминаний
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        # Запрос через открытый API поиска DuckDuckGo Lite
        res = requests.get(f"https://lite.duckduckgo.com/lite/", data={"q": query}, headers=headers, timeout=6)
        
        report = [f"🌐 **Результаты поиска упоминаний:** `{query}`\n"]
        if res.status_code == 200:
            # Парсим базовые ссылки из выдачи лит-версии
            matches = re.findall(r'class="result-link".*?href="(.*?)".*?>(.*?)</a>', res.text)
            if matches:
                report.append("• **Найденные открытые страницы:**")
                for link, title in matches[:4]:
                    clean_title = re.sub(r'<.*?>', '', title)
                    report.append(f"  - [{clean_title}]({link})")
            else:
                report.append("• Прямых открытых совпадений в поисковом индексе не обнаружено.")
        else:
            report.append("• Ошибка подключения к поисковому шлюзу.")
            
        bot.send_message(message.chat.id, "\n".join(report), parse_mode="Markdown", disable_web_page_preview=True, reply_markup=get_back_markup())
    except Exception:
        bot.send_message(message.chat.id, "❌ Не удалось выполнить веб-поиск.", reply_markup=get_back_markup())

# 3. Анализ телефона
def process_phone_search(message):
    if message.text and message.text.startswith('/'):
        return
    phone = re.sub(r'\D', '', message.text)
    user = message.from_user.username or str(message.from_user.id)
    save_to_history(message.chat.id, user, "Телефон", f"+{phone}")
    
    if not phone:
        bot.send_message(message.chat.id, "❌ Некорректный номер.", reply_markup=get_back_markup())
        return
        
    report = [f"📞 **Анализ телефона:** `+{phone}`\n"]
    if phone.startswith('7') and len(phone) == 11:
        report.append(f"• Страна: Россия / Казахстан (+7)")
        report.append(f"• Код оператора: `{phone[1:4]}`")
    else:
        report.append("• Стандарт: Международный формат.")

    bot.send_message(message.chat.id, "\n".join(report), parse_mode="Markdown", reply_markup=get_back_markup())

# 4. Проверка домена
def process_domain_search(message):
    if message.text and message.text.startswith('/'):
        return
    domain = message.text.strip().replace("https://", "").replace("http://", "").split("/")[0]
    user = message.from_user.username or str(message.from_user.id)
    save_to_history(message.chat.id, user, "Домен", domain)
    
    try:
        r = requests.get(f"https://{domain}", timeout=5, allow_redirects=True)
        server = r.headers.get('Server', 'Не определен')
        text = (
            f"🌐 **Отчет по домену:** `{domain}`\n\n"
            f"• Статус код: `{r.status_code}`\n"
            f"• Веб-сервер: `{server}`\n"
            f"• Защита Cloudflare: {'Активна 🛡️' B if 'cloudflare' in server.lower() else 'Нет'}"
        )
        bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=get_back_markup())
    except Exception:
        bot.send_message(message.chat.id, f"❌ Домен `{domain}` недоступен.", reply_markup=get_back_markup())

# 5. Инспектор медиа и пересылок (работает автоматически в режиме инспектора)
@bot.message_handler(content_types=['photo', 'video', 'video_note', 'contact', 'document'])
def handle_media(message):
    report = ["🔍 **Анализ объекта (Инспектор):**\n"]
    
    if message.forward_from:
        f_user = message.forward_from
        report.append(f"• 👤 **Автор (Forward):** {f_user.first_name} (@{f_user.username or 'нет'})")
        report.append(f"• 🆔 **Telegram ID:** `{f_user.id}`")

    if message.content_type == 'photo':
        report.append("• 📷 **Тип:** Фотография")
        report.append(f"• 🔑 `file_id`: `{message.photo[-1].file_id}`")
    elif message.content_type == 'video_note':
        report.append("• ⭕ **Тип:** Видео-кружок (Video Note)")
        report.append(f"• ⏱ Длительность: {message.video_note.duration} сек.")
    elif message.content_type == 'contact':
        c = message.contact
        report.append(f"• 📞 **Тип:** Контакт")
        report.append(f"• Имя: {c.first_name}")
        report.append(f"• Телефон: `+{c.phone_number}`")

    bot.send_message(message.chat.id, "\n".join(report), parse_mode="Markdown", reply_markup=get_back_markup())

@bot.message_handler(func=lambda m: m.forward_from is not None)
def handle_forwarded_text(message):
    f_user = message.forward_from
    text = (
        f"📨 **Анализ пересланного сообщения:**\n\n"
        f"• Имя: {f_user.first_name}\n"
        f"• Юзернейм: @{f_user.username if f_user.username else 'отсутствует'}\n"
        f"• Telegram ID: `{f_user.id}`\n"
        f"• Тип аккаунта: {'Бот' if f_user.is_bot else 'Пользователь'}"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=get_back_markup())

if __name__ == "__main__":
    bot.infinity_polling()
