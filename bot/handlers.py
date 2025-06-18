import sys
import traceback
import re
import datetime
import pytz
import json
import os
import asyncio
from collections import defaultdict

from aiogram import Bot, Dispatcher, types, executor
from my_config import TELEGRAM_BOT_TOKEN
from services.speech_to_text import speech_to_text
from services.reminder_parser import parse_reminder
from services.db_service import (
    add_reminder,
    init_db,
    get_all_reminders_for_user,
    get_due_reminders,
    mark_reminder_sent
)

ADMIN_ID = 570278582  # твой Telegram ID

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher(bot)

months = [
    "янв", "фев", "мар", "апр", "май", "июн",
    "июл", "авг", "сен", "окт", "ноя", "дек"
]

ISO_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?")

def is_valid_iso(dt_str):
    return bool(dt_str and ISO_REGEX.match(dt_str))

def log(msg):
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def dt_to_str(dt):
    return f"{dt.day} {months[dt.month - 1]} в {dt:%H:%M}"

def pretty_reminder(parsed):
    event_dt = datetime.datetime.fromisoformat(parsed['remind_at'])
    remind_before = parsed.get('remind_before', 0) or 0
    remind_dt = event_dt - datetime.timedelta(minutes=remind_before)
    event_str = dt_to_str(event_dt)
    remind_str = dt_to_str(remind_dt)

    if remind_before >= 60:
        hours = remind_before // 60
        minutes = remind_before % 60
        before_str = f"{hours} ч." + (f" {minutes} мин." if minutes else "")
    elif remind_before > 0:
        before_str = f"{remind_before} мин."
    else:
        before_str = "без доп. оповещения"

    text = parsed['text']
    EMOJI_TEXT = "💬"
    if any(word in text.lower() for word in ["тренировка", "спорт", "футбол", "баскетбол"]):
        EMOJI_TEXT = "🏀"
    elif any(word in text.lower() for word in ["поесть", "кушать", "ужин", "завтрак", "обед"]):
        EMOJI_TEXT = "🍽️"
    elif any(word in text.lower() for word in ["размяться", "разминка"]):
        EMOJI_TEXT = "🤸‍♂️"

    EMOJI_TIME = "🕒"
    EMOJI_ARROW = "➡️"

    return (
        f"{EMOJI_TIME} <b>{event_str}</b>\n"
        f"{EMOJI_TEXT} <b>{text}</b>\n"
        f"Напомнить: <b>{remind_str}</b> {EMOJI_ARROW} <i>({before_str} до события)</i>"
    )

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    log(f"/start от {message.from_user.id}")
    await message.reply(
        "Привет! Отправь мне текст или голосовое, чтобы создать напоминание.\n\n"
        "/list — посмотреть все твои активные и прошедшие напоминания."
    )

@dp.message_handler(commands=['list'])
async def cmd_list(message: types.Message):
    log(f"/list от {message.from_user.id}")
    reminders = get_all_reminders_for_user(message.from_user.id)
    if not reminders:
        await message.reply("У тебя нет напоминаний.")
        return

    now_dt = datetime.datetime.now(pytz.timezone("Europe/Moscow"))
    now = now_dt.date()
    tomorrow = now + datetime.timedelta(days=1)

    future = []
    past = []

    for reminder_id, remind_at, text, remind_before, status in reminders:
        if not is_valid_iso(remind_at):
            log(f"⛔️ Битое напоминание {reminder_id} (remind_at={remind_at}), пропускаю")
            continue
        event_dt = datetime.datetime.fromisoformat(remind_at)
        if status == "active" and event_dt.date() >= now:
            future.append((event_dt, text, remind_before))
        else:
            past.append((event_dt, text, remind_before))

    calendar = defaultdict(list)
    for event_dt, text, remind_before in future:
        day = event_dt.date()
        if day == now:
            key = f"Сегодня ({day.strftime('%d %b')})"
        elif day == tomorrow:
            key = f"Завтра ({day.strftime('%d %b')})"
        else:
            weekday = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'][day.weekday()]
            key = f"{day.strftime('%d %b')} ({weekday})"
        calendar[key].append((event_dt, text, remind_before))

    def date_from_key(key):
        if "Сегодня" in key:
            return now
        if "Завтра" in key:
            return tomorrow
        match = re.search(r'(\d{2}) (\w{3})', key)
        if match:
            d, m = match.groups()
            m_dict = {
                'янв': 1, 'фев': 2, 'мар': 3, 'апр': 4, 'май': 5, 'июн': 6,
                'июл': 7, 'авг': 8, 'сен': 9, 'окт': 10, 'ноя': 11, 'дек': 12
            }
            m_num = m_dict.get(m.lower(), 1)
            return datetime.date(now.year, m_num, int(d))
        return now + datetime.timedelta(days=1000)

    msg = "📅 <b>Твои напоминания:</b>\n\n"
    if future:
        for key in sorted(calendar.keys(), key=date_from_key):
            msg += f"<b>{key}</b>\n"
            for event_dt, text, _ in sorted(calendar[key], key=lambda x: x[0]):
                time_str = event_dt.strftime('%H:%M')
                text_fmt = text.strip().capitalize()
                msg += f"<code>{time_str}</code> — {text_fmt}\n"
            msg += "\n"
    else:
        msg += "<i>Нет будущих напоминаний.</i>\n\n"

    if past:
        msg += "⏳ <b>Прошедшие:</b>\n"
        for event_dt, text, _ in sorted(past, key=lambda x: x[0]):
            date_str = event_dt.strftime('%d %b %H:%M')
            text_fmt = text.strip().capitalize()
            msg += f"<i>{date_str} — {text_fmt}</i>\n"
        msg += "\n"
    else:
        msg += "<i>Прошедших напоминаний нет.</i>\n"

    await message.reply(msg, parse_mode="HTML")

@dp.message_handler(content_types=types.ContentType.TEXT)
async def handle_text(message: types.Message):
    log(f"Текст от {message.from_user.id}: {message.text}")
    now_iso = datetime.datetime.now(pytz.timezone("Europe/Moscow")).isoformat()
    try:
        parsed = json.loads(parse_reminder(message.text, now_iso))
        if not parsed.get("remind_at") or not is_valid_iso(parsed["remind_at"]):
            log(f"⛔️ Не удалось определить дату/время для напоминания (получено: {parsed.get('remind_at')})")
            await message.reply("Ошибка: не удалось определить дату/время для напоминания. Попробуй переформулировать запрос!")
            return
        add_reminder(
            user_id=message.from_user.id,
            remind_at=parsed["remind_at"],
            remind_before=parsed.get("remind_before", 0),
            text=parsed["text"]
        )
        log(f"✅ Напоминание добавлено: {parsed}")
        reply = pretty_reminder(parsed)
        await message.reply(reply, parse_mode="HTML")
    except Exception as e:
        log(f"❌ Ошибка в обработке текста: {e}")
        await notify_admin(f"❌ Ошибка в обработке текстового сообщения: {e}")
        await message.reply("Ошибка при обработке напоминания: " + str(e))

@dp.message_handler(content_types=types.ContentType.VOICE)
async def handle_voice(message: types.Message):
    log(f"Голосовое от {message.from_user.id}")
    try:
        file_info = await bot.get_file(message.voice.file_id)
        file = await bot.download_file(file_info.file_path)
        audio_path = "temp_voice.ogg"
        with open(audio_path, "wb") as f:
            f.write(file.read())
        text = speech_to_text(audio_path, language="ru")
        os.remove(audio_path)
        now_iso = datetime.datetime.now(pytz.timezone("Europe/Moscow")).isoformat()
        parsed = json.loads(parse_reminder(text, now_iso))
        if not parsed.get("remind_at") or not is_valid_iso(parsed["remind_at"]):
            log(f"⛔️ Не удалось определить дату/время для напоминания (получено: {parsed.get('remind_at')})")
            await message.reply("Ошибка: не удалось определить дату/время для напоминания. Попробуй сказать чуть точнее!")
            return
        add_reminder(
            user_id=message.from_user.id,
            remind_at=parsed["remind_at"],
            remind_before=parsed.get("remind_before", 0),
            text=parsed["text"]
        )
        log(f"✅ Напоминание добавлено из голосового: {parsed}")
        reply = pretty_reminder(parsed)
        await message.reply(f"Голос расшифрован: {text}\n\n{reply}", parse_mode="HTML")
    except Exception as e:
        log(f"❌ Ошибка в обработке голосового: {e}")
        await notify_admin(f"❌ Ошибка в обработке голосового сообщения: {e}")
        await message.reply("Ошибка при обработке голосового: " + str(e))

async def notify_admin(msg):
    try:
        await bot.send_message(ADMIN_ID, f"[Бот] {msg}", parse_mode="HTML")
    except Exception as err:
        log(f"Ошибка отправки админу: {err}")

async def check_and_send_reminders():
    while True:
        now = datetime.datetime.now(pytz.timezone("Europe/Moscow")).replace(second=0, microsecond=0)
        now_iso = now.isoformat()
        reminders = get_due_reminders(now_iso)
        log(f"Проверка рассылки напоминаний... Найдено: {len(reminders)}")
        for r in reminders:
            reminder_id, user_id, remind_at, text = r
            if not is_valid_iso(remind_at):
                log(f"❗️ У напоминания {reminder_id} битое поле remind_at={remind_at}, пропускаем")
                mark_reminder_sent(reminder_id)
                continue
            try:
                await bot.send_message(
                    user_id,
                    f"<b>Напоминание:</b>\n<b>{text}</b>\n🕒 <b>{dt_to_str(datetime.datetime.fromisoformat(remind_at))}</b>",
                    parse_mode="HTML"
                )
                mark_reminder_sent(reminder_id)
                log(f"✅ Напоминание отправлено user {user_id} ({reminder_id})")
            except Exception as e:
                log(f"❌ Ошибка при отправке напоминания {reminder_id}: {e}")
                await notify_admin(f"❌ Ошибка при отправке напоминания: {e}")
        await asyncio.sleep(30)

if __name__ == "__main__":
    try:
        print("Инициализируем БД и запускаем бота...")
        init_db()
        loop = asyncio.get_event_loop()
        loop.create_task(check_and_send_reminders())
        loop.run_until_complete(notify_admin("✅ Бот был (ре)запущен и готов к работе!"))
        executor.start_polling(dp, skip_updates=True)
    except Exception as e:
        log(f"=== ОШИБКА В ЗАПУСКЕ ===\n{e}")
        import asyncio
        asyncio.run(notify_admin(f"❌ Критическая ошибка в запуске: {e}"))
        traceback.print_exc()
        input("Нажми Enter для выхода...")
