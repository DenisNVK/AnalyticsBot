from groq import Groq
from config import GROQ_API_KEY, MODEL
from code_executor import execute_code, get_data_info, set_dataframe
from security import is_safe_code, check_dataframe_injection
import pandas as pd
import json

client = Groq(api_key=GROQ_API_KEY)

SYSTEM_PROMPT = """Ты — аналитик данных. У тебя есть доступ к функции execute_python_code.

ОБЯЗАТЕЛЬНЫЕ ШАГИ — выполни ВСЕ без исключения:

ШАГ 1 — ОПИСАНИЕ ДАТАСЕТА:
Вызови execute_python_code с кодом, который выводит:
- Форму датасета (df.shape)
- Названия и типы колонок (df.dtypes)
- Количество пропусков по каждой колонке (df.isnull().sum())
- Первые 5 строк (df.head())
- Описательную статистику (df.describe())

ШАГ 2 — ГРАФИК (ОБЯЗАТЕЛЕН):
Вызови execute_python_code и построй график. Если пользователь дал инструкцию — построй график,
релевантный его запросу. Если инструкции нет — построй гистограммы распределений или тепловую карту корреляций.
Обязательно вызови plt.tight_layout() и plt.savefig() в конце кода.

ШАГ 3 — АНАЛИЗ:
Если пользователь дал инструкцию — выполни именно её.
Если инструкции нет — обнаружь выбросы (IQR) и найди корреляции между числовыми колонками.
Вызови execute_python_code для анализа.

ШАГ 4 — ВЫВОДЫ:
В финальном текстовом ответе напиши:
- Краткое описание датасета (что за данные, сколько строк/колонок)
- Ключевые числа и метрики
- Результаты выполнения инструкции пользователя (если была)
- Минимум 3 бизнес-вывода на основе результатов кода

Ограничения:
- Не используй os, subprocess, open, eval, exec
- DataFrame доступен как 'df'
- Для графиков используй только plt.savefig() — НЕ plt.show()
- Не копируй весь код в финальный текстовый ответ
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "execute_python_code",
            "description": "Выполняет Python код для анализа данных. Код должен использовать pandas (как pd) и matplotlib (как plt). DataFrame доступен как 'df'. Результат выполнения и график будут возвращены.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python код для выполнения. Пример: 'print(df.columns)' или 'print(df.describe())'"
                    },
                },
                "required": ["code"],
            },
        },
    }
]


def analyze_data(file_path: str, user_instruction: str = None) -> tuple[str, str | None]:
    if file_path.endswith('.csv'):
        df = pd.read_csv(file_path)
    else:
        df = pd.read_excel(file_path)

    # Проверяем содержимое датасета на инъекции
    if check_dataframe_injection(df):
        return "⛔ Датасет отклонён: обнаружены подозрительные данные в ячейках.", None

    set_dataframe(df, file_path)
    data_info = get_data_info()

    if user_instruction:
        query = f"""Информация о датасете:
{data_info}

Инструкция пользователя: {user_instruction}

Выполни все обязательные шаги из системного промпта, учитывая инструкцию пользователя."""
    else:
        query = f"""Информация о датасете:
{data_info}

Выполни все обязательные шаги из системного промпта."""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": query}
    ]

    final_image = None
    final_text = ""

    for iteration in range(5):
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.2,
        )

        message = response.choices[0].message

        if message.tool_calls:
            messages.append(message)

            for tool_call in message.tool_calls:
                if tool_call.function.name == "execute_python_code":
                    code = json.loads(tool_call.function.arguments).get("code", "")

                    if not code.strip():
                        result = "⚠️ Пустой код — пропускаю."
                        img_base64 = None
                    elif not is_safe_code(code):
                        result = "⛔ Код отклонён системой безопасности: содержит запрещённые операции."
                        img_base64 = None
                    else:
                        result, img_base64 = execute_code(code)

                    if img_base64:
                        final_image = img_base64

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result
                    })
        else:
            final_text = message.content
            break

    if not final_text:
        final_text = "Анализ завершён. Результаты выше."

    return final_text, final_image