import os
import telebot
import requests

# Получаем токен из настроек Render
TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

# Список платформ для проверки никнейма
SOCIAL_NETWORKS = {
    "GitHub": "https://github.com/{}",
    "Twitter/X": "https://twitter.com/{}",
    "Instagram": "https://www.instagram.com/{}",
    "Reddit": "https://www.reddit.com/user/{}",
    "Pikabu": "https://pikabu.co/@{}",
    "Habr": "https://habr.com/ru/users/{}/"
}

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(telebot.types.KeyboardButton("🔍 Начать поиск"))
    bot.send_message(
        message.chat.id,
        "👋 Привет! Я твой многоцелевой OSINT-бот.\n\n"
        "Введи никнейм для проверки по открытым источникам.",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text == "🔍 Начать поиск")
def ask_query(message):
    bot.send_message(message.chat.id, "Введите **никнейм** (без @) для поиска:")

@bot.message_handler(func=lambda message: True)
def process_query(message):
    query = message.text.strip().lstrip('@')
    
    # Игнорируем нажатие кнопки поиска, чтобы не дублировать
    if query == "🔍 Начать поиск":
        return

    status_msg = bot.send_message(message.chat.id, f"⏳ Ищу информацию по объекту: `{query}`...", parse_mode="Markdown")
    
    report = [f"📊 **Отчет по результатам поиска:** `{query}`\n", "🌐 **Поиск по открытым платформам:**"]
    
    for platform, url_template in SOCIAL_NETWORKS.items():
        target_url = url_template.format(query)
        try:
            response = requests.get(target_url, timeout=5, allow_redirects=True)
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

if __name__ == "__main__":
    bot.infinity_polling()
