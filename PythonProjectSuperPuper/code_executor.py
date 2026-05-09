import pandas as pd
import matplotlib

matplotlib.use('Agg')  # для сервера
import matplotlib.pyplot as plt
import io
import base64
import traceback
import numpy as np
from io import StringIO

# Глобальная переменная для хранения DataFrame
_current_df = None
_current_filename = None


def set_dataframe(df: pd.DataFrame, filename: str):
    global _current_df, _current_filename
    _current_df = df.copy()
    _current_filename = filename


def execute_code(code: str) -> tuple[str, str | None]:
    """
    Выполняет Python код в ограниченном окружении.
    Возвращает (текстовый_результат, base64_изображение_или_None)
    """
    global _current_df

    # Буфер для захвата print
    import sys
    from io import StringIO

    old_stdout = sys.stdout
    sys.stdout = StringIO()

    result_text = ""
    image_base64 = None

    try:
        # Доступные функции и переменные
        allowed_locals = {
            'df': _current_df,
            'pd': pd,
            'np': np,
            'plt': plt,
            'print': print,
        }

        # Выполняем код
        exec(code, {'__builtins__': __builtins__}, allowed_locals)

        # Обновляем глобальный df (на случай, если код его изменил)
        _current_df = allowed_locals.get('df', _current_df)

        # Сохраняем вывод
        result_text = sys.stdout.getvalue()

        # Проверяем, есть ли созданные matplotlib фигуры
        if plt.get_fignums():
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
            buf.seek(0)
            image_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
            plt.close('all')

        if not result_text.strip() and not image_base64:
            result_text = "✅ Код выполнен успешно (нет вывода)."

    except Exception as e:
        result_text = f"❌ Ошибка выполнения:\n{traceback.format_exc()}"

    finally:
        sys.stdout = old_stdout

    return result_text, image_base64


def get_data_info() -> str:
    """Возвращает информацию о текущем датасете для контекста LLM"""
    global _current_df
    if _current_df is None:
        return "Датасет не загружен"

    buffer = StringIO()
    _current_df.info(buf=buffer)

    info_str = f"""
    📊 Информация о датасете:
    - Форма: {_current_df.shape[0]} строк × {_current_df.shape[1]} столбцов
    - Столбцы: {list(_current_df.columns)}
    - Типы данных: {_current_df.dtypes.to_dict()}
    - Пропуски: {_current_df.isnull().sum().to_dict()}
    - Краткая статистика (первые 5 числовых колонок):
    {_current_df.describe().to_string() if _current_df.select_dtypes(include=['number']).shape[1] > 0 else 'Нет числовых колонок'}
    """
    return info_str