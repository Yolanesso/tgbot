import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Dict
import pytz
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode
import database as db

# Загружаем переменные окружения из .env файла
load_dotenv()

# Установка UTF-8 для Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния пользователей для FSM
user_states: Dict[int, Dict] = {}

# ID владельца бота (загружается из .env файла)
OWNER_ID = int(os.getenv("OWNER_ID", "0"))  # Если не установлен в .env, будет 0 (отключено)


def get_main_menu():
    """Главное меню"""
    keyboard = [
        [KeyboardButton("⏰ Установить часовой пояс")],
        [KeyboardButton("🔔 Напоминания"), KeyboardButton("📝 Задачи")],
        [KeyboardButton("💝 Поддержать автора")],
        [KeyboardButton("📢 Наш канал")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_reminders_menu():
    """Меню напоминаний"""
    keyboard = [
        [InlineKeyboardButton("➕ Создать напоминание", callback_data="reminder_create")],
        [InlineKeyboardButton("📋 Управление напоминаниями", callback_data="reminder_manage")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_tasks_menu():
    """Меню задач"""
    keyboard = [
        [InlineKeyboardButton("➕ Создать задачу", callback_data="task_create")],
        [InlineKeyboardButton("📋 Управление задачами", callback_data="task_manage")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user_id = update.effective_user.id
    await db.get_or_create_user(user_id)
    
    welcome_text = (
        "👋 Привет! Я бот-помощник для управления задачами и напоминаниями.\n\n"
        "📢 Подписывайтесь на наш канал: @tgk_napominalki\n\n"
        "Выберите действие из меню:"
    )
    await update.message.reply_text(
        welcome_text,
        reply_markup=get_main_menu()
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    user_id = update.effective_user.id
    text = update.message.text
    state = user_states.get(user_id, {})

    # Установка часового пояса
    if text == "⏰ Установить часовой пояс":
        await show_timezone_selection(update, context)
        return

    # Напоминания
    if text == "🔔 Напоминания":
        await update.message.reply_text(
            "🔔 Управление напоминаниями",
            reply_markup=get_reminders_menu()
        )
        return

    # Задачи
    if text == "📝 Задачи":
        await update.message.reply_text(
            "📝 Управление задачами",
            reply_markup=get_tasks_menu()
        )
        return

    # Поддержать автора
    if text == "💝 Поддержать автора":
        await update.message.reply_text(
            "💝 Спасибо за поддержку!\n\n"
            "Если вам нравится этот бот, вы можете поддержать автора:\n\n"
            "🌐 DonationAlerts:\n"
            "https://www.donationalerts.com/r/gabrixpr\n\n"
            "💳 Банковская карта:\n"
            "2202 2084 2764 9356\n\n"
            "📢 Также подписывайтесь на наш канал:\n"
            "https://t.me/tgk_napominalki\n\n"
            "Или просто поделитесь ботом с друзьями! 🙏\n\n"
            "Ваша поддержка помогает развивать проект! ❤️"
        )
        return

    # Наш канал
    if text == "📢 Наш канал":
        await update.message.reply_text(
            "📢 <b>Наш канал</b>\n\n"
            "Подписывайтесь на наш канал, чтобы быть в курсе новостей и обновлений!\n\n"
            "🔗 <a href='https://t.me/tgk_napominalki'>@tgk_napominalki</a>",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=False
        )
        return

    # Обработка состояний
    if state.get("action") == "reminder_text":
        user_states[user_id]["reminder_text"] = text
        user_states[user_id]["action"] = "reminder_date"
        await update.message.reply_text(
            "📅 Введите дату в формате ДД.ММ.ГГГГ (например, 25.12.2024):"
        )
        return

    if state.get("action") == "reminder_date":
        try:
            date_obj = datetime.strptime(text, "%d.%m.%Y")
            user_states[user_id]["reminder_date"] = date_obj
            user_states[user_id]["action"] = "reminder_time"
            await update.message.reply_text(
                "⏰ Введите время в формате ЧЧ:ММ (например, 14:30):"
            )
            return
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ (например, 25.12.2024):"
            )
            return

    if state.get("action") == "reminder_time":
        try:
            time_obj = datetime.strptime(text, "%H:%M").time()
            reminder_date = user_states[user_id]["reminder_date"]
            reminder_datetime = datetime.combine(reminder_date.date(), time_obj)
            
            # Получаем часовой пояс пользователя
            user_tz = await db.get_user_timezone(user_id)
            tz = pytz.timezone(user_tz)
            
            # Локализуем время в часовом поясе пользователя
            local_dt = tz.localize(reminder_datetime)
            utc_dt = local_dt.astimezone(pytz.UTC)
            
            # Сохраняем напоминание
            reminder_text = user_states[user_id]["reminder_text"]
            await db.create_reminder(user_id, reminder_text, utc_dt)
            
            # Очищаем состояние
            user_states[user_id] = {}
            
            await update.message.reply_text(
                f"✅ Напоминание создано!\n\n"
                f"📝 Текст: {reminder_text}\n"
                f"📅 Дата и время: {reminder_datetime.strftime('%d.%m.%Y %H:%M')}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔔 Управление напоминаниями", callback_data="reminder_manage")],
                    [InlineKeyboardButton("➕ Создать ещё", callback_data="reminder_create")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="back_main")]
                ])
            )
            return
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат времени. Используйте ЧЧ:ММ (например, 14:30):"
            )
            return

    if state.get("action") == "task_text":
        await db.create_task(user_id, text)
        user_states[user_id] = {}
        await update.message.reply_text(
            f"✅ Задача создана: {text}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 Управление задачами", callback_data="task_manage")],
                [InlineKeyboardButton("➕ Создать ещё", callback_data="task_create")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="back_main")]
            ])
        )
        return

    if state.get("action") == "task_edit":
        task_id = state.get("task_id")
        await db.update_task(user_id, task_id, text)
        user_states[user_id] = {}
        await update.message.reply_text(
            f"✅ Задача обновлена: {text}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 Вернуться к задачам", callback_data="task_manage")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="back_main")]
            ])
        )
        return

    if state.get("action") == "reminder_edit_time":
        try:
            date_obj = datetime.strptime(text, "%d.%m.%Y")
            user_states[user_id]["reminder_edit_date"] = date_obj
            user_states[user_id]["action"] = "reminder_edit_time_only"
            await update.message.reply_text(
                "⏰ Введите время в формате ЧЧ:ММ (например, 14:30):"
            )
            return
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ (например, 25.12.2024):"
            )
            return

    if state.get("action") == "reminder_edit_time_only":
        try:
            time_obj = datetime.strptime(text, "%H:%M").time()
            reminder_date = user_states[user_id]["reminder_edit_date"]
            reminder_datetime = datetime.combine(reminder_date.date(), time_obj)
            
            user_tz = await db.get_user_timezone(user_id)
            tz = pytz.timezone(user_tz)
            local_dt = tz.localize(reminder_datetime)
            utc_dt = local_dt.astimezone(pytz.UTC)
            
            reminder_id = user_states[user_id]["reminder_id"]
            await db.update_reminder_time(reminder_id, user_id, utc_dt)
            
            user_states[user_id] = {}
            await update.message.reply_text(
                f"✅ Время напоминания обновлено: {reminder_datetime.strftime('%d.%m.%Y %H:%M')}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔔 Вернуться к напоминаниям", callback_data="reminder_manage")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="back_main")]
                ])
            )
            return
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат времени. Используйте ЧЧ:ММ (например, 14:30):"
            )
            return


async def show_reminders_menu(query, user_id: int):
    """Показать улучшенное меню управления напоминаниями"""
    reminders = await db.get_user_reminders(user_id)
    
    if not reminders:
        await query.edit_message_text(
            "🔔 У вас пока нет напоминаний.\n\n"
            "Создайте первое напоминание, нажав кнопку ниже!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Создать напоминание", callback_data="reminder_create")],
                [InlineKeyboardButton("◀️ Назад", callback_data="back_main")]
            ])
        )
        return
    
    user_tz = await db.get_user_timezone(user_id)
    tz = pytz.timezone(user_tz)
    now = datetime.now(pytz.UTC).astimezone(tz)
    
    # Разделяем напоминания на прошедшие и будущие
    future_reminders = []
    past_reminders = []
    
    for reminder in reminders:
        utc_dt = datetime.fromisoformat(reminder["reminder_time"])
        local_dt = utc_dt.astimezone(tz)
        
        reminder_data = {
            **reminder,
            "local_time": local_dt
        }
        
        if local_dt > now:
            future_reminders.append(reminder_data)
        else:
            past_reminders.append(reminder_data)
    
    # Сортируем: будущие по возрастанию времени, прошедшие по убыванию
    future_reminders.sort(key=lambda x: x["local_time"])
    past_reminders.sort(key=lambda x: x["local_time"], reverse=True)
    
    # Формируем текст
    text = "🔔 <b>Ваши напоминания</b>\n\n"
    
    if future_reminders:
        text += "⏰ <b>Предстоящие:</b>\n"
        for i, reminder in enumerate(future_reminders, 1):
            time_str = reminder["local_time"].strftime('%d.%m.%Y %H:%M')
            text += f"{i}. <b>{time_str}</b>\n"
            text += f"   {reminder['text']}\n\n"
    
    if past_reminders:
        text += f"⏳ <b>Прошедшие ({len(past_reminders)}):</b>\n"
        for reminder in past_reminders[:5]:  # Показываем только последние 5
            time_str = reminder["local_time"].strftime('%d.%m.%Y %H:%M')
            text += f"⏳ <s>{time_str}</s> - {reminder['text']}\n"
        if len(past_reminders) > 5:
            text += f"   ... и ещё {len(past_reminders) - 5}\n"
        text += "\n"
    
    # Статистика
    total = len(reminders)
    future = len(future_reminders)
    text += f"📊 <i>Всего: {total} | Предстоящих: {future}</i>"
    
    # Формируем клавиатуру
    keyboard = []
    
    # Кнопки для будущих напоминаний (компактно)
    for reminder in future_reminders:
        time_str = reminder["local_time"].strftime('%d.%m %H:%M')
        reminder_short = reminder['text'][:20] + "..." if len(reminder['text']) > 20 else reminder['text']
        keyboard.append([
            InlineKeyboardButton(f"✏️ {time_str}", callback_data=f"reminder_edit_{reminder['id']}"),
            InlineKeyboardButton("🗑", callback_data=f"reminder_delete_{reminder['id']}")
        ])
    
    # Кнопки для прошедших напоминаний (только удаление)
    if past_reminders:
        for reminder in past_reminders[:3]:  # Показываем кнопки только для последних 3
            reminder_short = reminder['text'][:20] + "..." if len(reminder['text']) > 20 else reminder['text']
            keyboard.append([
                InlineKeyboardButton(f"🗑 {reminder_short}", callback_data=f"reminder_delete_{reminder['id']}")
            ])
    
    # Дополнительные кнопки
    if past_reminders:
        keyboard.append([
            InlineKeyboardButton("🗑 Удалить все прошедшие", callback_data="reminder_delete_past")
        ])
    
    keyboard.append([
        InlineKeyboardButton("➕ Создать напоминание", callback_data="reminder_create"),
        InlineKeyboardButton("🔄 Обновить", callback_data="reminder_manage")
    ])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_main")])
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )


async def show_tasks_menu(query, user_id: int):
    """Показать улучшенное меню управления задачами"""
    tasks = await db.get_user_tasks(user_id)
    
    if not tasks:
        await query.edit_message_text(
            "📋 У вас пока нет задач.\n\n"
            "Создайте первую задачу, нажав кнопку ниже!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Создать задачу", callback_data="task_create")],
                [InlineKeyboardButton("◀️ Назад", callback_data="back_main")]
            ])
        )
        return
    
    # Разделяем задачи на выполненные и невыполненные
    # В SQLite completed хранится как INTEGER (0 или 1)
    # Но может возвращаться как строка или bool, поэтому нормализуем
    def is_completed(task):
        completed = task.get("completed", 0)
        if isinstance(completed, bool):
            return completed
        elif isinstance(completed, str):
            return completed == "1" or completed.lower() == "true"
        else:
            return int(completed) == 1 if completed else False
    
    active_tasks = [t for t in tasks if not is_completed(t)]
    completed_tasks = [t for t in tasks if is_completed(t)]
    
    # Формируем текст
    text = "📋 <b>Ваши задачи</b>\n\n"
    
    if active_tasks:
        text += "🔄 <b>Активные задачи:</b>\n"
        for i, task in enumerate(active_tasks, 1):
            text += f"{i}. {task['text']}\n"
        text += "\n"
    
    if completed_tasks:
        text += f"✅ <b>Выполнено ({len(completed_tasks)}):</b>\n"
        for i, task in enumerate(completed_tasks, 1):
            text += f"✅ <s>{task['text']}</s>\n"
        text += "\n"
    
    # Отладочная информация (можно убрать после проверки)
    # text += f"\n<i>Отладка: активных={len(active_tasks)}, выполненных={len(completed_tasks)}</i>"
    
    # Статистика
    total = len(tasks)
    completed = len(completed_tasks)
    progress = int((completed / total * 100)) if total > 0 else 0
    text += f"📊 <i>Прогресс: {completed}/{total} ({progress}%)</i>"
    
    # Формируем клавиатуру
    keyboard = []
    
    # Кнопки для активных задач (компактно)
    for task in active_tasks:
        task_short = task['text'][:25] + "..." if len(task['text']) > 25 else task['text']
        keyboard.append([
            InlineKeyboardButton(f"✅ {task_short}", callback_data=f"task_toggle_{task['id']}"),
            InlineKeyboardButton("✏️", callback_data=f"task_edit_{task['id']}"),
            InlineKeyboardButton("🗑", callback_data=f"task_delete_{task['id']}")
        ])
    
    # Кнопки для выполненных задач (только удаление)
    if completed_tasks:
        for task in completed_tasks:
            task_short = task['text'][:25] + "..." if len(task['text']) > 25 else task['text']
            keyboard.append([
                InlineKeyboardButton(f"↩️ {task_short}", callback_data=f"task_toggle_{task['id']}"),
                InlineKeyboardButton("🗑", callback_data=f"task_delete_{task['id']}")
            ])
    
    # Дополнительные кнопки
    if completed_tasks:
        keyboard.append([
            InlineKeyboardButton("🗑 Удалить все выполненные", callback_data="task_delete_completed")
        ])
    
    keyboard.append([
        InlineKeyboardButton("➕ Создать задачу", callback_data="task_create"),
        InlineKeyboardButton("🔄 Обновить", callback_data="task_manage")
    ])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_main")])
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )


async def show_timezone_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать выбор часового пояса"""
    # Часовые пояса России
    timezones = [
        ("Калининград (UTC+2)", "Europe/Kaliningrad"),
        ("Москва (UTC+3)", "Europe/Moscow"),
        ("Самара (UTC+4)", "Europe/Samara"),
        ("Екатеринбург (UTC+5)", "Asia/Yekaterinburg"),
        ("Омск (UTC+6)", "Asia/Omsk"),
        ("Красноярск (UTC+7)", "Asia/Krasnoyarsk"),
        ("Иркутск (UTC+8)", "Asia/Irkutsk"),
        ("Чита (UTC+9)", "Asia/Chita"),
        ("Якутск (UTC+9)", "Asia/Yakutsk"),
        ("Владивосток (UTC+10)", "Asia/Vladivostok"),
        ("Магадан (UTC+11)", "Asia/Magadan"),
        ("Камчатка (UTC+12)", "Asia/Kamchatka"),
    ]
    
    keyboard = []
    for tz_name, tz_code in timezones:
        keyboard.append([InlineKeyboardButton(tz_name, callback_data=f"tz_{tz_code}")])
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_main")])
    
    await update.message.reply_text(
        "⏰ Выберите ваш часовой пояс:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    # Назад в главное меню
    if data == "back_main":
        await query.edit_message_text(
            "Главное меню",
            reply_markup=None
        )
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="Выберите действие:",
            reply_markup=get_main_menu()
        )
        return

    # Установка часового пояса
    if data.startswith("tz_"):
        timezone = data[3:]
        await db.set_user_timezone(user_id, timezone)
        await query.edit_message_text(
            f"✅ Часовой пояс установлен: {timezone}"
        )
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="Выберите действие:",
            reply_markup=get_main_menu()
        )
        return

    # Напоминания
    if data == "reminder_create":
        user_states[user_id] = {"action": "reminder_text"}
        await query.edit_message_text(
            "📝 Введите текст напоминания:"
        )
        return

    if data == "reminder_manage":
        await show_reminders_menu(query, user_id)
        return

    if data.startswith("reminder_edit_"):
        reminder_id = int(data.split("_")[2])
        user_states[user_id] = {
            "action": "reminder_edit_time",
            "reminder_id": reminder_id
        }
        await query.edit_message_text(
            "📅 Введите новую дату в формате ДД.ММ.ГГГГ (например, 25.12.2024):"
        )
        return

    if data.startswith("reminder_delete_"):
        reminder_id_str = data.split("_")[2]
        
        # Проверяем, не является ли это запросом на удаление всех прошедших
        if reminder_id_str == "past":
            reminders = await db.get_user_reminders(user_id)
            user_tz = await db.get_user_timezone(user_id)
            tz = pytz.timezone(user_tz)
            now = datetime.now(pytz.UTC).astimezone(tz)
            
            deleted_count = 0
            for reminder in reminders:
                utc_dt = datetime.fromisoformat(reminder["reminder_time"])
                local_dt = utc_dt.astimezone(tz)
                if local_dt <= now:
                    await db.delete_reminder(reminder["id"], user_id)
                    deleted_count += 1
            
            if deleted_count > 0:
                await query.answer(f"🗑 Удалено напоминаний: {deleted_count}")
            else:
                await query.answer("ℹ️ Нет прошедших напоминаний для удаления")
            await show_reminders_menu(query, user_id)
            return
        
        reminder_id = int(reminder_id_str)
        await db.delete_reminder(reminder_id, user_id)
        await query.answer("🗑 Напоминание удалено!")
        await show_reminders_menu(query, user_id)
        return

    # Задачи
    if data == "task_create":
        user_states[user_id] = {"action": "task_text"}
        await query.edit_message_text(
            "📝 Введите текст задачи:"
        )
        return

    if data == "task_manage":
        await show_tasks_menu(query, user_id)
        return

    if data.startswith("task_edit_"):
        task_id = int(data.split("_")[2])
        user_states[user_id] = {
            "action": "task_edit",
            "task_id": task_id
        }
        await query.edit_message_text(
            "📝 Введите новый текст задачи:"
        )
        return

    # ВАЖНО: проверка task_delete_completed должна быть ПЕРЕД task_delete_
    # иначе "task_delete_completed" попадет в startswith("task_delete_")
    if data == "task_delete_completed":
        try:
            await query.answer("⏳ Удаляю выполненные задачи...", show_alert=False)
            
            tasks = await db.get_user_tasks(user_id)
            deleted_count = 0
            completed_task_ids = []
            
            # Собираем ID выполненных задач
            # Проверяем разные варианты: 1, "1", True
            for task in tasks:
                completed = task.get("completed", 0)
                # Преобразуем в int для надежности
                if isinstance(completed, bool):
                    completed = 1 if completed else 0
                elif isinstance(completed, str):
                    completed = int(completed) if completed.isdigit() else 0
                else:
                    completed = int(completed) if completed else 0
                
                if completed == 1:
                    completed_task_ids.append(task["id"])
            
            logger.info(f"Найдено выполненных задач для удаления: {len(completed_task_ids)}")
            
            # Удаляем выполненные задачи
            for task_id in completed_task_ids:
                try:
                    await db.delete_task(user_id, task_id)
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"Ошибка при удалении задачи {task_id}: {e}")
            
            if deleted_count > 0:
                await query.answer(f"✅ Удалено задач: {deleted_count}", show_alert=False)
            else:
                await query.answer("ℹ️ Нет выполненных задач для удаления", show_alert=False)
            
            # Обновляем меню
            await show_tasks_menu(query, user_id)
        except Exception as e:
            logger.error(f"Ошибка при удалении выполненных задач: {e}", exc_info=True)
            await query.answer(f"❌ Ошибка: {str(e)[:50]}", show_alert=True)
        return

    if data.startswith("task_delete_"):
        task_id = int(data.split("_")[2])
        await db.delete_task(user_id, task_id)
        await query.answer("🗑 Задача удалена!")
        await show_tasks_menu(query, user_id)
        return

    if data.startswith("task_toggle_"):
        task_id = int(data.split("_")[2])
        await db.toggle_task_completion(user_id, task_id)
        await query.answer("✅ Статус изменён!")
        await show_tasks_menu(query, user_id)
        return


async def check_reminders(application: Application):
    """Проверка и отправка напоминаний"""
    due_reminders = await db.get_due_reminders()
    
    for reminder in due_reminders:
        user_id = reminder["user_id"]
        reminder_text = reminder["text"]
        
        # Получаем часовой пояс пользователя для отображения
        user_tz = await db.get_user_timezone(user_id)
        tz = pytz.timezone(user_tz)
        utc_dt = datetime.fromisoformat(reminder["reminder_time"])
        local_dt = utc_dt.astimezone(tz)
        
        message = (
            f"🔔 Напоминание!\n\n"
            f"📝 {reminder_text}\n"
            f"🕐 {local_dt.strftime('%d.%m.%Y %H:%M')}"
        )
        
        try:
            await application.bot.send_message(
                chat_id=user_id,
                text=message
            )
            # Удаляем отправленное напоминание
            await db.delete_sent_reminder(reminder["id"])
        except Exception as e:
            logger.error(f"Ошибка при отправке напоминания: {e}")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /stats для просмотра аналитики (только для владельца)"""
    user_id = update.effective_user.id
    
    # Проверка прав доступа
    if OWNER_ID == 0:
        await update.message.reply_text(
            "⚠️ Аналитика не настроена. Установите переменную окружения OWNER_ID."
        )
        return
    
    if user_id != OWNER_ID:
        await update.message.reply_text(
            "❌ У вас нет доступа к этой команде."
        )
        return
    
    try:
        # Получаем статистику
        total_users = await db.get_total_users()
        active_today = await db.get_active_users_today()
        active_week = await db.get_active_users_week()
        active_month = await db.get_active_users_month()
        
        tasks_stats = await db.get_tasks_stats()
        reminders_stats = await db.get_reminders_stats()
        new_users_stats = await db.get_new_users_stats()
        
        top_users = await db.get_top_active_users(limit=5)
        daily_stats = await db.get_daily_stats(days=7)
        
        # Формируем сообщение со статистикой
        text = "📊 <b>Аналитика бота</b>\n\n"
        
        # Статистика пользователей
        text += "👥 <b>Пользователи:</b>\n"
        text += f"   Всего: {total_users}\n"
        text += f"   Активных сегодня: {active_today}\n"
        text += f"   Активных за неделю: {active_week}\n"
        text += f"   Активных за месяц: {active_month}\n"
        text += f"   Новых сегодня: {new_users_stats['today']}\n"
        text += f"   Новых за неделю: {new_users_stats['week']}\n"
        text += f"   Новых за месяц: {new_users_stats['month']}\n\n"
        
        # Статистика задач
        text += "📝 <b>Задачи:</b>\n"
        text += f"   Всего: {tasks_stats['total']}\n"
        text += f"   Выполнено: {tasks_stats['completed']}\n"
        text += f"   Активных: {tasks_stats['active']}\n"
        if tasks_stats['total'] > 0:
            completion_rate = round((tasks_stats['completed'] / tasks_stats['total']) * 100, 1)
            text += f"   Процент выполнения: {completion_rate}%\n"
        text += "\n"
        
        # Статистика напоминаний
        text += "🔔 <b>Напоминания:</b>\n"
        text += f"   Всего: {reminders_stats['total']}\n"
        text += f"   Будущих: {reminders_stats['future']}\n"
        text += f"   Прошедших: {reminders_stats['past']}\n\n"
        
        # Топ активных пользователей
        if top_users:
            text += "🏆 <b>Топ-5 активных пользователей:</b>\n"
            for i, user in enumerate(top_users, 1):
                user_id_stat = user['user_id']
                tasks_count = user['tasks_count'] or 0
                reminders_count = user['reminders_count'] or 0
                total_activity = user['total_activity'] or 0
                text += f"   {i}. ID: {user_id_stat} | Задач: {tasks_count} | Напоминаний: {reminders_count} | Всего: {total_activity}\n"
            text += "\n"
        
        # Статистика за последние 7 дней
        text += "📈 <b>Активность за последние 7 дней:</b>\n"
        for day_stat in daily_stats:
            date_str = datetime.strptime(day_stat['date'], '%Y-%m-%d').strftime('%d.%m')
            text += f"   {date_str}: +{day_stat['new_users']} пользователей, +{day_stat['new_tasks']} задач, +{day_stat['new_reminders']} напоминаний\n"
        
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"Ошибка при получении статистики: {e}", exc_info=True)
        await update.message.reply_text(
            f"❌ Ошибка при получении статистики: {str(e)}"
        )




def main():
    """Главная функция"""
    # Получаем токен из .env файла
    TOKEN = os.getenv("BOT_TOKEN")
    
    if not TOKEN:
        print("⚠️ ОШИБКА: Токен бота не найден!")
        print("Создайте файл .env в корне проекта и добавьте:")
        print("BOT_TOKEN=ваш_токен_здесь")
        print("OWNER_ID=ваш_telegram_id")
        print("\nПример файла .env.example уже есть в проекте.")
        print("Получите токен у @BotFather в Telegram")
        return
    
    # Инициализация базы данных
    asyncio.run(db.init_db())
    
    # Создание приложения
    application = Application.builder().token(TOKEN).build()
    
    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Запуск проверки напоминаний в фоне
    async def reminder_checker_task():
        """Фоновая задача для проверки напоминаний"""
        await asyncio.sleep(10)  # Начальная задержка
        while True:
            try:
                await check_reminders(application)
            except Exception as e:
                logger.error(f"Ошибка в задаче проверки напоминаний: {e}")
            await asyncio.sleep(60)  # Проверяем каждую минуту
    
    # Запускаем фоновую задачу через post_init
    async def post_init(app: Application) -> None:
        """Инициализация после запуска бота"""
        asyncio.create_task(reminder_checker_task())
    
    application.post_init = post_init
    
    # Запуск бота
    print("🤖 Бот запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

