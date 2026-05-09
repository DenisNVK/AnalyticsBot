from dotenv import load_dotenv
load_dotenv()

import logging
import os
import tempfile
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from config import TELEGRAM_TOKEN
from security import is_prompt_injection, sanitize_user_instruction
from agent import analyze_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

user_instructions = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "*Я аналитик данных*\n\n"
        "*Как использовать:*\n"
        "1. Напиши `/analyze текст инструкции` (опционально)\n"
        "2. Отправь CSV или Excel файл\n\n"
        "Я покажу: статистику, графики, выбросы, корреляции и бизнес-выводы.",
        parse_mode="Markdown"
    )


async def set_instruction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    instruction = " ".join(context.args)

    if not instruction:
        await update.message.reply_text("📝 Пример: `/analyze найди аномалии в колонке price`")
        return

    if is_prompt_injection(instruction):
        await update.message.reply_text("⛔ Инструкция отклонена (обнаружена попытка injection).")
        return

    instruction = sanitize_user_instruction(instruction)
    user_instructions[user_id] = instruction
    await update.message.reply_text(f"✅ Инструкция сохранена:\n\n{instruction}")


async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    document = update.message.document
    file_name = document.file_name

    if not (file_name.endswith('.csv') or file_name.endswith('.xlsx')):
        await update.message.reply_text("❌ Отправь CSV или Excel файл.")
        return

    await update.message.reply_text("📊 Анализирую датасет ... ")

    file = await context.bot.get_file(document.file_id)

    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_name)[1]) as tmp:
        await file.download_to_drive(tmp.name)
        tmp_path = tmp.name

    try:
        instruction = user_instructions.pop(user_id, None)
        result_text, result_image = analyze_data(tmp_path, instruction)

        if result_text:
            if len(result_text) > 4000:
                for i in range(0, len(result_text), 4000):
                    await update.message.reply_text(result_text[i:i + 4000])
            else:
                await update.message.reply_text(result_text)

        if result_image:
            import base64
            from io import BytesIO

            image_bytes = base64.b64decode(result_image)
            await update.message.reply_photo(
                photo=BytesIO(image_bytes),
                caption="📈 График, сгенерированный агентом"
            )

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await update.message.reply_text(f"⚠️ Ошибка: {str(e)[:300]}")
    finally:
        os.unlink(tmp_path)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/start — приветствие\n"
        "/analyze [текст] — задать инструкцию для анализа\n"
        "/help — эта справка\n\n"
        "Просто отправь CSV/Excel файл и получи анализ от AI-агента."
    )


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("analyze", set_instruction))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))

    logger.info("Бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()