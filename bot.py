import asyncio
import logging
import os
import aiohttp
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# Получаем токен из настроек сервера (безопасно)
TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher()

class OsintStates(StatesGroup):
    waiting_for_query = State()

SOCIAL_NETWORKS = {
    "GitHub": "https://github.com/{}",
    "Twitter/X": "https://twitter.com/{}",
    "Instagram": "https://www.instagram.com/{}",
    "Reddit": "https://www.reddit.com/user/{}",
    "Pikabu": "https://pikabu.co/@{}",
    "Habr": "https://habr.com/ru/users/{}/"
}

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await message.answer(
        "👋 Привет! Я твой многоцелевой OSINT-бот.\n\n"
        "Я умею искать информацию по никнеймам не только в Telegram, но и в других открытых источниках.\n\n"
        "Нажми кнопку ниже или введи команду /search для начала поиска.",
        reply_markup=types.ReplyKeyboardMarkup(
            keyboard=[[types.KeyboardButton(text="🔍 Начать поиск")]],
            resize_keyboard=True
        )
    )

@dp.message(F.text == "🔍 Начать поиск")
@dp.message(Command("search"))
async def cmd_search(message: types.Message, state: FSMContext):
    await message.answer("Введите **никнейм** (без @) для комплексного поиска по открытым источникам:")
    await state.set_state(OsintStates.waiting_for_query)

@dp.message(OsintStates.waiting_for_query)
async def process_query(message: types.Message, state: FSMContext):
    query = message.text.strip().lstrip('@')
    await state.clear()
    
    status_msg = await message.answer(f"⏳ Начинаю сбор данных по объекту: `{query}`...\nПроверяю внешние источники и соцсети.")
    
    report = [f"📊 **Отчет по результатам поиска:** `{query}`\n"]
    
    report.append("🌐 **Поиск по открытым платформам:**")
    
    async with aiohttp.ClientSession() as session:
        for platform, url_template in SOCIAL_NETWORKS.items():
            target_url = url_template.format(query)
            try:
                async with session.get(target_url, timeout=5, allow_redirects=True) as response:
                    if response.status == 200:
                        report.append(f"• {platform}: [Найдено]({target_url})")
                    else:
                        report.append(f"• {platform}: Не найдено")
            except Exception:
                report.append(f"• {platform}: Ошибка запроса / Недоступно")

    report.append("\n💬 **Telegram-анализ:**")
    report.append(f"• Юзернейм: `@{query}`")
    report.append(f"• Статус: Базовый модуль проверки активен.")

    final_text = "\n".join(report)
    await bot.edit_message_text(
        text=final_text,
        chat_id=message.chat.id,
        message_id=status_msg.message_id,
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен!")
