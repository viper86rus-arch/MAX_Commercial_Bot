# -*- coding: utf-8 -*-
# ==============================================================================
# Модуль: storage.py
# Назначение: Персистентное хранилище лидов, сессий и диалогов на SQLite
# Автор: V1PER (viper86rus-arch)
# Лицензия: MIT License (2026)
# ==============================================================================

import sqlite3
import csv
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from config import DATABASE_PATH, EXPORTS_DIR, logger

# ==============================================================================
# 1. ИНИЦИАЛИЗАЦИЯ СХЕМЫ БАЗЫ ДАННЫХ
# ==============================================================================

def init_db(db_path: str = DATABASE_PATH) -> None:
    """Инициализирует таблицы базы данных SQLite."""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        # Таблица входящих коммерческих лидов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS commercial_leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                max_user_id TEXT NOT NULL,
                user_name TEXT,
                phone TEXT,
                service_type TEXT,
                platforms TEXT,
                budget_range TEXT,
                description TEXT,
                status TEXT DEFAULT 'new',
                created_at TEXT NOT NULL
            )
        """)
        
        # Таблица состояний диалогового автомата (FSM)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversation_states (
                max_user_id TEXT PRIMARY KEY,
                step TEXT NOT NULL,
                session_data TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        conn.commit()
    logger.info(f"SQLite БД инициализирована: {db_path}")

# ==============================================================================
# 2. ОПЕРАЦИИ С СОСТОЯНИЯМИ ПОЛЬЗОВАТЕЛЕЙ (FSM)
# ==============================================================================

def get_user_state(max_user_id: str, db_path: str = DATABASE_PATH) -> tuple[str, Dict[str, Any]]:
    """Возвращает текущий шаг и накопленные данные пользователя."""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT step, session_data FROM conversation_states WHERE max_user_id = ?",
            (str(max_user_id),)
        )
        row = cursor.fetchone()
        if not row:
            return "idle", {}
        try:
            return row[0], json.loads(row[1])
        except Exception:
            return row[0], {}

def set_user_state(max_user_id: str, step: str, data: Dict[str, Any], db_path: str = DATABASE_PATH) -> None:
    """Обновляет состояние пользователя и данные сессии."""
    now = datetime.now(timezone.utc).isoformat()
    data_json = json.dumps(data, ensure_ascii=False)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO conversation_states (max_user_id, step, session_data, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(max_user_id) DO UPDATE SET
                step = excluded.step,
                session_data = excluded.session_data,
                updated_at = excluded.updated_at
        """, (str(max_user_id), step, data_json, now))
        conn.commit()

def clear_user_state(max_user_id: str, db_path: str = DATABASE_PATH) -> None:
    """Сбрасывает состояние пользователя в idle."""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM conversation_states WHERE max_user_id = ?", (str(max_user_id),))
        conn.commit()

# ==============================================================================
# 3. СОХРАНЕНИЕ И ЭКСПОРТ ЛИДОВ (UTF-8-SIG / Excel)
# ==============================================================================

def save_lead(
    max_user_id: str,
    user_name: str,
    phone: str,
    service_type: str,
    platforms: str,
    budget_range: str,
    description: str,
    db_path: str = DATABASE_PATH
) -> int:
    """Сохраняет новую подтвержденную заявку в базу данных."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO commercial_leads (
                max_user_id, user_name, phone, service_type,
                platforms, budget_range, description, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'new', ?)
        """, (
            str(max_user_id),
            user_name or "Аноним",
            phone or "Не указан",
            service_type or "Общий запрос",
            platforms or "MAX / Telegram",
            budget_range or "Договорной",
            description or "—",
            now
        ))
        conn.commit()
        lead_id = cursor.lastrowid
    logger.info(f"Заявка #{lead_id} успешно сохранена (Клиент: {user_name}, Сервис: {service_type})")
    return lead_id

def export_leads_to_csv(db_path: str = DATABASE_PATH) -> str:
    """
    Экспортирует все лиды в CSV с кодировкой UTF-8 BOM (utf-8-sig)
    и разделителем точка с запятой (;) по стандарту Microsoft Excel.
    """
    now_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    export_file = EXPORTS_DIR / f"leads_export_{now_str}.csv"
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, max_user_id, user_name, phone, service_type,
                   platforms, budget_range, description, status, created_at
            FROM commercial_leads ORDER BY id DESC
        """)
        rows = cursor.fetchall()

    headers = [
        "ID Заявки", "MAX ID", "Имя заказчика", "Телефон / Контакт",
        "Тип услуги", "Платформы", "Бюджет", "Описание проекта",
        "Статус", "Дата создания (UTC)"
    ]

    with open(export_file, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(headers)
        writer.writerows(rows)

    logger.info(f"Экспорт завершен: {export_file} (Всего записей: {len(rows)})")
    return str(export_file)
