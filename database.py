import aiosqlite
import pytz
from datetime import datetime, timedelta
from typing import Optional, List, Dict

DB_NAME = "bot_database.db"


async def init_db():
    """Инициализация базы данных"""
    async with aiosqlite.connect(DB_NAME) as db:
        # Таблица пользователей с настройками
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                timezone TEXT DEFAULT 'UTC',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица напоминаний
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                reminder_time TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)
        
        # Таблица задач
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                completed INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)
        
        await db.commit()


async def get_or_create_user(user_id: int) -> Dict:
    """Получить или создать пользователя"""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM users WHERE user_id = ?",
            (user_id,)
        )
        user = await cursor.fetchone()
        
        if not user:
            await db.execute(
                "INSERT INTO users (user_id, timezone) VALUES (?, ?)",
                (user_id, 'UTC')
            )
            await db.commit()
            return {"user_id": user_id, "timezone": "UTC"}
        
        return dict(user)


async def set_user_timezone(user_id: int, timezone: str):
    """Установить часовой пояс пользователя"""
    await get_or_create_user(user_id)  # Убедимся, что пользователь существует
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE users SET timezone = ? WHERE user_id = ?",
            (timezone, user_id)
        )
        await db.commit()


async def get_user_timezone(user_id: int) -> str:
    """Получить часовой пояс пользователя"""
    user = await get_or_create_user(user_id)
    return user.get("timezone", "UTC")


async def create_reminder(user_id: int, text: str, reminder_time: datetime):
    """Создать напоминание"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO reminders (user_id, text, reminder_time) VALUES (?, ?, ?)",
            (user_id, text, reminder_time.isoformat())
        )
        await db.commit()


async def get_user_reminders(user_id: int) -> List[Dict]:
    """Получить все напоминания пользователя"""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM reminders WHERE user_id = ? ORDER BY reminder_time ASC",
            (user_id,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def delete_reminder(reminder_id: int, user_id: int):
    """Удалить напоминание"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "DELETE FROM reminders WHERE id = ? AND user_id = ?",
            (reminder_id, user_id)
        )
        await db.commit()


async def update_reminder_time(reminder_id: int, user_id: int, new_time: datetime):
    """Обновить время напоминания"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE reminders SET reminder_time = ? WHERE id = ? AND user_id = ?",
            (new_time.isoformat(), reminder_id, user_id)
        )
        await db.commit()


async def get_due_reminders() -> List[Dict]:
    """Получить напоминания, которые должны быть отправлены сейчас"""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        now = datetime.utcnow().isoformat()
        cursor = await db.execute(
            "SELECT * FROM reminders WHERE reminder_time <= ?",
            (now,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def delete_sent_reminder(reminder_id: int):
    """Удалить отправленное напоминание"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "DELETE FROM reminders WHERE id = ?",
            (reminder_id,)
        )
        await db.commit()


async def create_task(user_id: int, text: str):
    """Создать задачу"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO tasks (user_id, text) VALUES (?, ?)",
            (user_id, text)
        )
        await db.commit()


async def get_user_tasks(user_id: int) -> List[Dict]:
    """Получить все задачи пользователя"""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM tasks WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def update_task(user_id: int, task_id: int, new_text: str):
    """Обновить текст задачи"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE tasks SET text = ? WHERE id = ? AND user_id = ?",
            (new_text, task_id, user_id)
        )
        await db.commit()


async def delete_task(user_id: int, task_id: int):
    """Удалить задачу"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "DELETE FROM tasks WHERE id = ? AND user_id = ?",
            (task_id, user_id)
        )
        await db.commit()


async def toggle_task_completion(user_id: int, task_id: int):
    """Переключить статус выполнения задачи"""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT completed FROM tasks WHERE id = ? AND user_id = ?",
            (task_id, user_id)
        )
        row = await cursor.fetchone()
        if row:
            new_status = 1 - row[0]
            await db.execute(
                "UPDATE tasks SET completed = ? WHERE id = ? AND user_id = ?",
                (new_status, task_id, user_id)
            )
            await db.commit()


# ==================== Функции аналитики ====================

async def get_total_users() -> int:
    """Получить общее количество пользователей"""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        row = await cursor.fetchone()
        return row[0] if row else 0


async def get_active_users_today() -> int:
    """Получить количество активных пользователей за сегодня"""
    async with aiosqlite.connect(DB_NAME) as db:
        today = datetime.utcnow().strftime('%Y-%m-%d')
        cursor = await db.execute(
            """
            SELECT COUNT(DISTINCT user_id) FROM (
                SELECT user_id FROM tasks WHERE DATE(created_at) = ?
                UNION
                SELECT user_id FROM reminders WHERE DATE(created_at) = ?
            )
            """,
            (today, today)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def get_active_users_week() -> int:
    """Получить количество активных пользователей за последние 7 дней"""
    async with aiosqlite.connect(DB_NAME) as db:
        week_ago = (datetime.utcnow() - timedelta(days=7)).strftime('%Y-%m-%d')
        cursor = await db.execute(
            """
            SELECT COUNT(DISTINCT user_id) FROM (
                SELECT user_id FROM tasks WHERE DATE(created_at) >= ?
                UNION
                SELECT user_id FROM reminders WHERE DATE(created_at) >= ?
            )
            """,
            (week_ago, week_ago)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def get_active_users_month() -> int:
    """Получить количество активных пользователей за последние 30 дней"""
    async with aiosqlite.connect(DB_NAME) as db:
        month_ago = (datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%d')
        cursor = await db.execute(
            """
            SELECT COUNT(DISTINCT user_id) FROM (
                SELECT user_id FROM tasks WHERE DATE(created_at) >= ?
                UNION
                SELECT user_id FROM reminders WHERE DATE(created_at) >= ?
            )
            """,
            (month_ago, month_ago)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def get_tasks_stats() -> Dict:
    """Получить статистику по задачам"""
    async with aiosqlite.connect(DB_NAME) as db:
        # Всего задач
        cursor = await db.execute("SELECT COUNT(*) FROM tasks")
        total_tasks = (await cursor.fetchone())[0]
        
        # Выполненных задач
        cursor = await db.execute("SELECT COUNT(*) FROM tasks WHERE completed = 1")
        completed_tasks = (await cursor.fetchone())[0]
        
        # Активных задач
        active_tasks = total_tasks - completed_tasks
        
        return {
            "total": total_tasks or 0,
            "completed": completed_tasks or 0,
            "active": active_tasks or 0
        }


async def get_reminders_stats() -> Dict:
    """Получить статистику по напоминаниям"""
    async with aiosqlite.connect(DB_NAME) as db:
        now = datetime.utcnow().isoformat()
        
        # Всего напоминаний
        cursor = await db.execute("SELECT COUNT(*) FROM reminders")
        total_reminders = (await cursor.fetchone())[0]
        
        # Будущих напоминаний
        cursor = await db.execute(
            "SELECT COUNT(*) FROM reminders WHERE reminder_time > ?",
            (now,)
        )
        future_reminders = (await cursor.fetchone())[0]
        
        # Прошедших напоминаний
        past_reminders = (total_reminders or 0) - (future_reminders or 0)
        
        return {
            "total": total_reminders or 0,
            "future": future_reminders or 0,
            "past": past_reminders or 0
        }


async def get_new_users_stats() -> Dict:
    """Получить статистику по новым пользователям"""
    async with aiosqlite.connect(DB_NAME) as db:
        today = datetime.utcnow().strftime('%Y-%m-%d')
        week_ago = (datetime.utcnow() - timedelta(days=7)).strftime('%Y-%m-%d')
        month_ago = (datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        # За сегодня
        cursor = await db.execute(
            "SELECT COUNT(*) FROM users WHERE DATE(created_at) = ?",
            (today,)
        )
        today_new = (await cursor.fetchone())[0]
        
        # За неделю
        cursor = await db.execute(
            "SELECT COUNT(*) FROM users WHERE DATE(created_at) >= ?",
            (week_ago,)
        )
        week_new = (await cursor.fetchone())[0]
        
        # За месяц
        cursor = await db.execute(
            "SELECT COUNT(*) FROM users WHERE DATE(created_at) >= ?",
            (month_ago,)
        )
        month_new = (await cursor.fetchone())[0]
        
        return {
            "today": today_new or 0,
            "week": week_new or 0,
            "month": month_new or 0
        }


async def get_top_active_users(limit: int = 10) -> List[Dict]:
    """Получить топ активных пользователей по количеству задач и напоминаний"""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT 
                u.user_id,
                COUNT(DISTINCT t.id) as tasks_count,
                COUNT(DISTINCT r.id) as reminders_count,
                (COUNT(DISTINCT t.id) + COUNT(DISTINCT r.id)) as total_activity
            FROM users u
            LEFT JOIN tasks t ON u.user_id = t.user_id
            LEFT JOIN reminders r ON u.user_id = r.user_id
            GROUP BY u.user_id
            ORDER BY total_activity DESC
            LIMIT ?
            """,
            (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_daily_stats(days: int = 7) -> List[Dict]:
    """Получить ежедневную статистику за последние N дней"""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        stats = []
        
        for i in range(days):
            date = (datetime.utcnow() - timedelta(days=i)).strftime('%Y-%m-%d')
            
            # Новые пользователи
            cursor = await db.execute(
                "SELECT COUNT(*) FROM users WHERE DATE(created_at) = ?",
                (date,)
            )
            new_users = (await cursor.fetchone())[0] or 0
            
            # Новые задачи
            cursor = await db.execute(
                "SELECT COUNT(*) FROM tasks WHERE DATE(created_at) = ?",
                (date,)
            )
            new_tasks = (await cursor.fetchone())[0] or 0
            
            # Новые напоминания
            cursor = await db.execute(
                "SELECT COUNT(*) FROM reminders WHERE DATE(created_at) = ?",
                (date,)
            )
            new_reminders = (await cursor.fetchone())[0] or 0
            
            stats.append({
                "date": date,
                "new_users": new_users,
                "new_tasks": new_tasks,
                "new_reminders": new_reminders
            })
        
        return list(reversed(stats))  # Возвращаем в хронологическом порядке
