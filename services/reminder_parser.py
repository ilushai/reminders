# services/reminder_parser.py
import openai
import json
import re
from my_config import OPENAI_API_KEY

openai.api_key = OPENAI_API_KEY

SYSTEM_PROMPT = """
Ты помощник для создания напоминаний.
Парсь входящий текст пользователя и выдай строго JSON со следующими полями:

- remind_at: точная дата и время события в формате ISO (например, 2025-05-30T16:00:00+03:00). Если дата неполная или не понятна — напиши "NEEDS_CLARIFICATION".
- text: что сделать (кратко, без лишних слов), в начале добавь смайлик категории из списка:
  - 🏃‍♂️ спорт
  - 📚 учёба
  - 🛋️ отдых
  - 🍽️ еда
  - 💊 здоровье
  - 💼 работа
  - 🛒 покупки
  - 🚗 транспорт
  - 🎉 событие
  - 💰 финансы
  - 🧹 дом
  - 📅 встреча
- remind_before: за сколько минут до события напомнить (если не указано — 0)
- needs_clarification: true/false — если не удалось однозначно определить дату/время, верни true

Правила:
- Если пользователь говорит "напомни за час", "за 5 минут", "за 30 минут" — укажи remind_before в минутах (1 час = 60 мин).
- Если время указано как "сегодня", "завтра", "послезавтра" — рассчитай конкретную дату, используя текущий момент: {now_iso}
- Если указан только час ("в 15:00"), определи ближайшую дату: если время ещё не наступило — сегодня, если прошло — завтра.
- Если просит “напомнить в 15:00” без дела — text оставь пустым, только смайлик категории не нужен.
- Все значения времени и даты должны быть в часовом поясе +03:00 (Москва).
- Если не хватает данных для точного времени, верни "NEEDS_CLARIFICATION" и needs_clarification: true.

Пример ответа:
{
  "remind_at": "2025-05-30T16:00:00+03:00",
  "text": "💊 Записаться к стоматологу",
  "remind_before": 30,
  "needs_clarification": false
}
"""



def clean_json(raw):
    """Убирает markdown-обёртки, если GPT всё равно их вернёт"""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
    return raw.strip()

def parse_reminder(text, now_iso: str):
    user_prompt = f"Текущий момент: {now_iso}\nПользователь: {text}"
    completion = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        max_tokens=250,
        temperature=0.0,
    )
    content = completion["choices"][0]["message"]["content"]
    return clean_json(content)

if __name__ == "__main__":
    import datetime, pytz
    now_iso = datetime.datetime.now(pytz.timezone("Europe/Moscow")).isoformat()
    test_text = "8 мая в 16:00 мне надо записаться к стоматологу на удаление зуба. Напомни за 30 минут до этого."
    result = parse_reminder(test_text, now_iso)
    print("RAW result from GPT:\n", result)
    parsed = json.loads(result)
    print("Parsed JSON:")
    print(parsed)
