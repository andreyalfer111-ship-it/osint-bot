import os
import telebot
import requests
import re

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("Не найден токен бота! Проверьте переменные окружения BOT_TOKEN.")

bot = telebot.TeleBot(TOKEN)

# 1. Расширенный список платформ для проверки никнеймов
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
    markup.add(btn1, btn2)
    markup.add(btn3)
    
    bot.send_message(
        message.chat.id,
        "👋 **Добро пожаловать в OSINT Max Bot!**\n\n"
        "Этот инструмент выполняет комплексную разведку по открытым источникам.\n"
        "Выберите интересующий вас режим ниже:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == "mode_username":
        bot.send_message(call.message.chat.id, "👤 Введите **никнейм** (без @) для комплексного поиска по соцсетям:")
        bot.register_next_step_handler(call.message, process_username_search)
    elif call.data == "mode_phone":
        bot.send_message(call.message.chat.id, "📞 Введите **номер телефона** (например, +79991234567) для базового анализа:")
        bot.register_next_step_handler(call.message, process_phone_search)
    elif call.data == "mode_domain":
        bot.send_message(call.message.chat.id, "🌐 Введите **домен или URL** сайта (например, example.com):")
        bot.register_next_step_handler(call.message, process_domain_search)

# Модуль 1: Поиск по никнеймам
def process_username_search(message):
    query = message.text.strip().lstrip('@')
    status_msg = bot.send_message(message.chat.id, f"⏳ Сканирую платформы для никнейма: `{query}`...", parse_mode="Markdown")
    
    report = [f"📊 **Отчет по никнейму:** `{query}`\n", "🌐 **Результаты проверки соцсетей:**"]
    
    for platform, url_template in SOCIAL_NETWORKS.items():
        target_url = url_template.format(query)
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            response = requests.get(target_url, headers=headers, timeout=4, allow_redirects=True)
            if response.status_code == 200:
                report.append(f"• {platform}: [Найдено]({target_url})")
            else:
                report.append(f"• {platform}: Не найдено")
        except Exception:
            report.append(f"• {platform}: Ошибка запроса")

    final_text = "\n".join(report)
    bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=status_msg.message_id,
        text=final_text,
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

# Модуль 2: Базовый анализ телефона (регион, оператор по префиксу)
def process_phone_search(message):
    phone = re.sub(r'\D', '', message.text)
    if not phone:
        bot.send_message(message.chat.id, "❌ Некорректный номер. Попробуйте снова через /start")
        return
        
    report = [f"📞 **Анализ номера телефона:** `+{phone}`\n"]
    
    if phone.startswith('7') and len(phone) == 11:
        operator_code = phone[1:4]
        report.append(f"• Страна: Россия / Казахстан (+7)")
        report.append(f"• Код оператора/региона: `{operator_code}`")
        report.append("• Статус: Базовый структурный анализ завершен.")
    elif phone.startswith('380') and len(phone) == 12:
        report.append(f"• Страна: Украина (+380)")
        report.append("• Статус: Базовый структурный анализ завершен.")
    else:
        report.append("• Информация: Международный номер или нестандартный формат.")

    bot.send_message(message.chat.id, "\n".join(report), parse_mode="Markdown")

# Модуль 3: Проверка сайтов / доменов
def process_domain_search(message):
    domain = message.text.strip().replace("https://", "").replace("http://", "").split("/")[0]
    status_msg = bot.send_message(message.chat.id, f"⏳ Проверяю доступность домена: `{domain}`...", parse_mode="Markdown")
    
    target_url = f"https://{domain}"
    report = [f"🌐 **Отчет по домену:** `{domain}`\n"]
    
    try:
        response = requests.get(target_url, timeout=5, allow_redirects=True)
        report.append(f"• Статус-код: `{response.status_code}`")
        report.append(f"• Итоговый URL: {response.url}")
        report.append(f"• Сервер/Защита: {response.headers.get('Server', 'Не определен')}")
        if 'cloudflare' in response.headers.get('Server', '').lower():
            report.append("• 🛡️ Обнаружена защита Cloudflare.")
    except Exception as e:
        report.append(f"• Ошибка соединения: Сайт недоступен или заблокирован.")

    bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=status_msg.message_id,
        text="\n".join(report),
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

if __name__ == "__main__":
    bot.infinity_polling()
