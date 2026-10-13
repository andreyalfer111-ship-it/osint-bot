import os
import sqlite3
import telebot
import requests
import re

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("Не найден токен бота! Проверьте переменные окружения BOT_TOKEN.")

bot = telebot.TeleBot(TOKEN)

# Инициализация локальной базы данных SQLite (сохраняется прямо на диске Render)
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

# Список платформ для проверки никнеймов
SOCIAL_NETWORKS = {
    "GitHub": "https://github.com/{}",
    "Twitter/X": "https://twitter.com/{}",
    "Instagram": "https://www.instagram.com/{}",
    "Reddit": "https://www.reddit.com/user/{}",
    "TikTok": "https://www.tiktok.com/@{}",
    "Pikabu": "https://pikabu.co/@{}",
    "Habr": "https://habr.com/ru/users/{}/",
    "Steam": "https://steamcommunity.com/id/{}"
}

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = telebot.types.InlineKeyboardMarkup()
    btn1 = telebot.types.InlineKeyboardButton("🔍 Поиск по никнейму", callback_data="mode_username")
    btn2 = telebot.types.InlineKeyboardButton("📞 Анализ телефона", callback_data="mode_phone")
    btn3 = telebot.types.InlineKeyboardButton("🌐 Проверка сайта/домена", callback_data="mode_domain")
    btn4 = telebot.types.InlineKeyboardButton("📜 Моя история", callback_data="mode_history")
    markup.add(btn1, btn2)
    markup.add(btn3)
    markup.add(btn4)
    
    bot.send_message(
        message.chat.id,
        "👋 **Добро пожаловать в Ultimate OSINT Bot!**\n\n"
        "Все инструменты разведки собраны в одном месте.\n"
        "Выберите нужный режим в меню ниже:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == "mode_username":
        bot.send_message(call.message.chat.id, "👤 Введите **никнейм** (без @) для сканирования платформ:")
        bot.register_next_step_handler(call.message, process_username_search)
    elif call.data == "mode_phone":
        bot.send_message(call.message.chat.id, "📞 Введите **номер телефона** (например, +79991234567):")
        bot.register_next_step_handler(call.message, process_phone_search)
    elif call.data == "mode_domain":
        bot.send_message(call.message.chat.id, "🌐 Введите **домен или URL** сайта (например, example.com):")
        bot.register_next_step_handler(call.message, process_domain_search)
    elif call.data == "mode_history":
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
            bot.send_message(user_id, "📜 Ваша история запросов пока пуста.")
            return
            
        report = ["📜 **Последние 5 запросов в системе:**\n"]
        for r_type, r_text, r_time in rows:
            report.append(f"• [{r_time}] **{r_type}**: `{r_text}`")
            
        bot.send_message(user_id, "\n".join(report), parse_mode="Markdown")
    except Exception:
        bot.send_message(user_id, "❌ Не удалось загрузить историю.")

# Модуль 1: Никнеймы
def process_username_search(message):
    query = message.text.strip().lstrip('@')
    user = message.from_user.username or str(message.from_user.id)
    save_to_history(message.chat.id, user, "Никнейм", query)
    
    status_msg = bot.send_message(message.chat.id, f"⏳ Сканирую платформы для: `{query}`...", parse_mode="Markdown")
    report = [f"📊 **Отчет по никнейму:** `{query}`\n", "🌐 **Результаты соцсетей:**"]
    
    for platform, url_template in SOCIAL_NETWORKS.items():
        target_url = url_template.format(query)
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(target_url, headers=headers, timeout=4, allow_redirects=True)
            if response.status_code == 200:
                report.append(f"• {platform}: [Найдено]({target_url})")
            else:
                report.append(f"• {platform}: Не найдено")
        except Exception:
            report.append(f"• {platform}: Ошибка запроса")

    bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=status_msg.message_id,
        text="\n".join(report),
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

# Модуль 2: Телефон
def process_phone_search(message):
    phone = re.sub(r'\D', '', message.text)
    user = message.from_user.username or str(message.from_user.id)
    save_to_history(message.chat.id, user, "Телефон", f"+{phone}")
    
    if not phone:
        bot.send_message(message.chat.id, "❌ Некорректный номер.")
        return
        
    report = [f"📞 **Анализ телефона:** `+{phone}`\n"]
    if phone.startswith('7') and len(phone) == 11:
        report.append(f"• Регион: Россия / Казахстан (+7)")
        report.append(f"• Код оператора: `{phone[1:4]}`")
    elif phone.startswith('380') and len(phone) == 12:
        report.append(f"• Регион: Украина (+380)")
    else:
        report.append("• Стандарт: Международный формат.")

    bot.send_message(message.chat.id, "\n".join(report), parse_mode="Markdown")

# Модуль 3: Домены
def process_domain_search(message):
    domain = message.text.strip().replace("https://", "").replace("http://", "").split("/")[0]
    user = message.from_user.username or str(message.from_user.id)
    save_to_history(message.chat.id, user, "Домен", domain)
    
    status_msg = bot.send_message(message.chat.id, f"⏳ Анализирую домен: `{domain}`...", parse_mode="Markdown")
    target_url = f"https://{domain}"
    report = [f"🌐 **Отчет по домену:** `{domain}`\n"]
    
    try:
        response = requests.get(target_url, timeout=5, allow_redirects=True)
        report.append(f"• Код ответа: `{response.status_code}`")
        report.append(f"• Финальный URL: {response.url}")
        server = response.headers.get('Server', 'Не определен')
        report.append(f"• Веб-сервер: {server}")
        if 'cloudflare' in server.lower():
            report.append("• 🛡️ Защита: Cloudflare активна.")
    except Exception:
        report.append("• Ошибка: Домен недоступен или заблокирован.")

    bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=status_msg.message_id,
        text="\n".join(report),
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

if __name__ == "__main__":
    bot.infinity_polling()
