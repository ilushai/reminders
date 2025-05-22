from services.speech_to_text import speech_to_text
from services.reminder_parser import parse_reminder
from services.db_service import init_db, add_reminder, get_due_reminders, set_sent
import datetime
import pytz
import json

if __name__ == "__main__":
    # 1. Инициализация базы
    init_db()

    # 2. Симуляция получения аудио или текста
    user_id = 123456789  # Telegram user_id
    use_audio = False    # Поменяй на True для аудио-теста

    if use_audio:
        audio_path = "sample.m4a"
        text = speech_to_text(audio_path, language="ru")
        print(f"Текст из аудио: {text}")
    else:
        text = "8 мая в 16:00 мне надо записаться к стоматологу на удаление зуба. Напомни за 30 минут до этого."
        print(f"Входящий текст: {text}")

    # 3. Парсим текст в структуру
    now_iso = datetime.datetime.now(pytz.timezone("Europe/Moscow")).isoformat()
    parsed = json.loads(parse_reminder(text, now_iso))

    print("Структура для БД:", parsed)

    # 4. Записываем напоминание в базу
    add_reminder(
        user_id=user_id,
        remind_at=parsed["remind_at"],
        remind_before=parsed["remind_before"],
        text=parsed["text"]
    )
    print("Записано в базу!")

    # 5. Пробуем выбрать напоминания (например, все которые пора отправлять на текущий момент)
    due = get_due_reminders(now_iso)
    print("Напоминания, которые пора отправить:", due)
    for reminder in due:
        print("Пробуем пометить как отправленное:", reminder[0])
        set_sent(reminder[0])
