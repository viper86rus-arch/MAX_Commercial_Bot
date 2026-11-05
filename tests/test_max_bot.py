# -*- coding: utf-8 -*-
# ==============================================================================
# Тестовый модуль: test_max_bot.py
# Назначение: Модульное тестирование диалогового движка, SQLite и экспорта МАКС
# Автор: V1PER (viper86rus-arch)
# Лицензия: MIT License (2026)
# ==============================================================================

import unittest
import os
import tempfile
import sqlite3
from pathlib import Path

# Добавляем родительский каталог в sys.path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from storage import (
    init_db, get_user_state, set_user_state,
    clear_user_state, save_lead, export_leads_to_csv
)
from max_api import MaxApiClient
from bot import BotEngine

class TestMaxCommercialBot(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_max_bot.db")
        init_db(self.db_path)
        self.api = MaxApiClient(token="mock_token_123")
        self.engine = BotEngine(self.api, self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_database_schema_initialization(self):
        """Проверяет корректность создания таблиц SQLite."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in cursor.fetchall()]
            self.assertIn("commercial_leads", tables)
            self.assertIn("conversation_states", tables)

    def test_fsm_state_transitions(self):
        """Проверяет переходы состояний конечного автомата (FSM)."""
        user_id = "user_42"
        step, data = get_user_state(user_id, self.db_path)
        self.assertEqual(step, "idle")

        set_user_state(user_id, "ask_budget", {"service": "Telegram Bot"}, self.db_path)
        step, data = get_user_state(user_id, self.db_path)
        self.assertEqual(step, "ask_budget")
        self.assertEqual(data.get("service"), "Telegram Bot")

        clear_user_state(user_id, self.db_path)
        step, data = get_user_state(user_id, self.db_path)
        self.assertEqual(step, "idle")

    def test_lead_saving_and_excel_csv_export(self):
        """Проверяет запись лида и экспорт в CSV с UTF-8-SIG."""
        lead_id = save_lead(
            max_user_id="user_999",
            user_name="Иван Петров",
            phone="+79991112233",
            service_type="Парсинг Wildberries",
            platforms="MAX",
            budget_range="15000",
            description="Сбор цен конкурентов",
            db_path=self.db_path
        )
        self.assertGreater(lead_id, 0)

        export_path = export_leads_to_csv(self.db_path)
        self.assertTrue(os.path.exists(export_path))

        # Проверка UTF-8 BOM (\xef\xbb\xbf) для идеального отображения в Excel
        with open(export_path, "rb") as f:
            raw_header = f.read(3)
            self.assertEqual(raw_header, b"\xef\xbb\xbf")

    def test_bot_dialogue_flow(self):
        """Проверяет полный 4-шаговый цикл сбора лида через диалоговый движок."""
        uid = "client_300"
        name = "Константин"

        # 1. Приветствие
        reply_start = self.engine.process_incoming(uid, "/start", name)
        self.assertIn("Добро пожаловать", reply_start)

        # 2. Клик на услуги
        reply_services = self.engine.process_incoming(uid, "btn_services", name)
        self.assertIn("Чат-боты для бизнеса", reply_services)

        # 3. Старт заказа
        reply_order = self.engine.process_incoming(uid, "btn_order", name)
        self.assertIn("Шаг 1 из 4", reply_order)

        # 4. Ввод типа услуги
        reply_s1 = self.engine.process_incoming(uid, "Чат-бот для Telegram и МАКС", name)
        self.assertIn("Шаг 2 из 4", reply_s1)

        # 5. Ввод бюджета
        reply_s2 = self.engine.process_incoming(uid, "10000 ₽", name)
        self.assertIn("Шаг 3 из 4", reply_s2)

        # 6. Ввод описания
        reply_s3 = self.engine.process_incoming(uid, "Автоматизация заявок на доставку", name)
        self.assertIn("Шаг 4 из 4", reply_s3)

        # 7. Ввод контакта -> подтверждение
        reply_final = self.engine.process_incoming(uid, "@konstantin_delivery", name)
        self.assertIn("успешно принята", reply_final)

if __name__ == "__main__":
    unittest.main()
