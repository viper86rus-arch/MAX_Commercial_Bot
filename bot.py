# -*- coding: utf-8 -*-
# ==============================================================================
# Модуль: bot.py
# Назначение: Диалоговый движок, FSM и интерактивный сервер бота МАКС
# Автор: V1PER (viper86rus-arch)
# Лицензия: MIT License (2026)
# ==============================================================================

import sys
import signal
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, List, Optional
from config import (
    PORT, HOST, IS_DEMO,
    MAX_BOT_TOKEN, DATABASE_PATH, logger
)
from storage import (
    init_db, get_user_state, set_user_state,
    clear_user_state, save_lead, export_leads_to_csv
)
from max_api import MaxApiClient, send_telegram_alert

# ==============================================================================
# 1. ТЕКСТЫ И ШАБЛОНЫ ДИАЛОГОВ
# ==============================================================================

WELCOME_TEXT = (
    "👋 <b>Добро пожаловать в студию автоматизации V1PER!</b>\n\n"
    "Я официальный виртуальный ассистент инженерной студии. "
    "Помогу рассчитать смету, ознакомиться с портфолио и оформить заявку на разработку.\n\n"
    "Выберите интересующий раздел:"
)

MAIN_KEYBOARD = [
    [{"text": "💼 Услуги и прайс", "action": "btn_services"},
     {"text": "🧮 Калькулятор сметы", "action": "btn_calc"}],
    [{"text": "📂 Наше портфолио", "action": "btn_portfolio"},
     {"text": "📩 Оставить заявку", "action": "btn_order"}],
    [{"text": "👤 Прямой контакт", "action": "btn_contact"}]
]

SERVICES_TEXT = (
    "💼 <b>Наши ключевые направления разработки (2026):</b>\n\n"
    "1. <b>Чат-боты для бизнеса (Telegram & МАКС)</b>\n"
    "   • Автоматизация продаж, прием платежей, закрытые клубы.\n"
    "   • Сроки: от 1 до 3 дней. Стоимость: от 5 000 ₽.\n\n"
    "2. <b>Интеграция CRM-систем (Битрикс24, amoCRM)</b>\n"
    "   • Автоматическое управление группами, лидами и сделками.\n"
    "   • Сроки: от 2 дней. Стоимость: от 7 000 ₽.\n\n"
    "3. <b>Высокоскоростной парсинг данных и маркетплейсов</b>\n"
    "   • Wildberries, Ozon, базы контрагентов, выгрузка в Excel/CSV.\n"
    "   • Сроки: от 24 часов. Стоимость: от 4 000 ₽.\n\n"
    "4. <b>Асинхронные микросервисы и серверные утилиты</b>\n"
    "   • Сетевые сканеры, мониторинг серверов, Docker-контейнеры.\n"
    "   • Сроки: от 1 дня. Стоимость: от 6 000 ₽."
)

PORTFOLIO_TEXT = (
    "📂 <b>Флагманские проекты студии V1PER:</b>\n\n"
    "• <b>Telegram Commercial Bot</b> — промышленный бот для бизнеса с генерацией счетов PDF и приемом оплат.\n"
    "• <b>CRM Group Manager</b> — микросервис создания и чистки проектных групп в Telegram (MTProto) и МАКС.\n"
    "• <b>Enterprise Web Scraper</b> — масштабируемый асинхронный сборщик данных с веб-дашбордом на FastAPI.\n"
    "• <b>Wildberries Fast Scraper</b> — моментальный парсер товарных матриц в Excel (UTF-8 BOM).\n"
    "• <b>Async TCP Scanner</b> — аудит сетевой безопасности и мониторинг портов промышленного уровня."
)

CONTACT_TEXT = (
    "👤 <b>Прямой контакт ведущего разработчика:</b>\n\n"
    "• <b>Бренд:</b> V1PER (viper86rus-arch)\n"
    "• <b>Специализация:</b> Senior Python / Automation Engineer\n"
    "• <b>Статус:</b> Официальный самозанятый РФ (работа по договору / ЭДО / чеки)\n"
    "• <b>Гарантия:</b> 30 дней бесплатной технической поддержки на весь код."
)

# ==============================================================================
# 2. ОБРАБОТЧИК СООБЩЕНИЙ И FSM (State Machine)
# ==============================================================================

class BotEngine:
    """Диалоговый движок с поддержкой многошаговых сценариев."""

    def __init__(self, api_client: MaxApiClient, db_path: Optional[str] = None):
        self.api = api_client
        self.db_path = db_path or DATABASE_PATH

    def process_incoming(self, user_id: str, text: str, user_name: str = "") -> str:
        """Обрабатывает входящее действие пользователя и возвращает ответ."""
        text = text.strip()
        step, session = get_user_state(user_id, self.db_path)

        # Команды сброса и перезапуска
        if text in ("/start", "/menu", "Главное меню", "btn_menu"):
            clear_user_state(user_id, self.db_path)
            self.api.send_message(user_id, WELCOME_TEXT, MAIN_KEYBOARD)
            return WELCOME_TEXT

        # Навигация по кнопкам меню
        if text in ("💼 Услуги и прайс", "btn_services"):
            self.api.send_message(user_id, SERVICES_TEXT, MAIN_KEYBOARD)
            return SERVICES_TEXT

        if text in ("📂 Наше портфолио", "btn_portfolio"):
            self.api.send_message(user_id, PORTFOLIO_TEXT, MAIN_KEYBOARD)
            return PORTFOLIO_TEXT

        if text in ("👤 Прямой контакт", "btn_contact"):
            self.api.send_message(user_id, CONTACT_TEXT, MAIN_KEYBOARD)
            return CONTACT_TEXT

        # Старт оформления заявки
        if text in ("📩 Оставить заявку", "btn_order", "/order"):
            set_user_state(user_id, "ask_service", {"name": user_name, "max_id": user_id}, self.db_path)
            prompt = (
                "📝 <b>Оформление заявки (Шаг 1 из 4):</b>\n\n"
                "Какая услуга вас интересует?\n"
                "1. Чат-бот (Telegram / МАКС)\n"
                "2. Парсинг данных / Excel\n"
                "3. Интеграция с CRM\n"
                "4. Другая задача"
            )
            self.api.send_message(user_id, prompt)
            return prompt

        # Шаг 1 -> Шаг 2 (Услуга -> Бюджет)
        if step == "ask_service":
            session["service"] = text
            set_user_state(user_id, "ask_budget", session, self.db_path)
            prompt = (
                "💰 <b>Шаг 2 из 4:</b>\n\n"
                "Укажите ориентировочный бюджет проекта (например: 5000, 15000 или «Договорной»):"
            )
            self.api.send_message(user_id, prompt)
            return prompt

        # Шаг 2 -> Шаг 3 (Бюджет -> Описание задачи)
        if step == "ask_budget":
            session["budget"] = text
            set_user_state(user_id, "ask_desc", session, self.db_path)
            prompt = (
                "📋 <b>Шаг 3 из 4:</b>\n\n"
                "Кратко опишите задачу (ссылка на ТЗ или ключевые пожелания):"
            )
            self.api.send_message(user_id, prompt)
            return prompt

        # Шаг 3 -> Шаг 4 (Описание -> Контактные данные)
        if step == "ask_desc":
            session["desc"] = text
            set_user_state(user_id, "ask_contact", session, self.db_path)
            prompt = (
                "📞 <b>Шаг 4 из 4:</b>\n\n"
                "Укажите ваш контакт для связи (телефон, ник в Telegram или email):"
            )
            self.api.send_message(user_id, prompt)
            return prompt

        # Шаг 4 -> Финал (Сохранение заявки и отправка в TG)
        if step == "ask_contact":
            session["phone"] = text
            if not session.get("name"):
                session["name"] = user_name or "Пользователь МАКС"

            # Сохранение в SQLite
            lead_id = save_lead(
                max_user_id=user_id,
                user_name=session["name"],
                phone=session["phone"],
                service_type=session.get("service", "Общий"),
                platforms="MAX",
                budget_range=session.get("budget", "Договорной"),
                description=session.get("desc", "—"),
                db_path=self.db_path
            )

            # Отправка мгновенного алерта в Telegram разработчику
            send_telegram_alert(lead_id, session)

            # Сброс состояния
            clear_user_state(user_id, self.db_path)

            success_text = (
                f"✅ <b>Заявка #{lead_id} успешно принята!</b>\n\n"
                f"Спасибо за обращение. Ведущий инженер свяжется с вами в течение 15 минут для уточнения деталей.\n\n"
                f"<i>Для возврата в меню отправьте /start</i>"
            )
            self.api.send_message(user_id, success_text, MAIN_KEYBOARD)
            return success_text

        # Калькулятор сметы
        if text in ("🧮 Калькулятор сметы", "btn_calc"):
            calc_text = (
                "🧮 <b>Экспресс-калькулятор стоимости:</b>\n\n"
                "• Базовый чат-бот визитка: ~4 500 ₽ (1 день)\n"
                "• Бот с корзиной, оплатой и базой данных: ~8 500 ₽ (2-3 дня)\n"
                "• Микросервис управления группами / CRM: ~6 500 ₽ (2 дня)\n"
                "• Парсер интернет-магазинов в Excel: ~5 000 ₽ (1 день)\n\n"
                "Хотите рассчитать ваш проект индивидуально? Нажмите «📩 Оставить заявку»."
            )
            self.api.send_message(user_id, calc_text, MAIN_KEYBOARD)
            return calc_text

        # Эхо / fallback
        fallback = "Извините, не распознал команду. Нажмите /start для вызова главного меню."
        self.api.send_message(user_id, fallback, MAIN_KEYBOARD)
        return fallback

# ==============================================================================
# 3. HTTP СЕРВЕР ВЕБХУКОВ ДЛЯ ПРОДАКШЕНА
# ==============================================================================

class MaxWebhookHandler(BaseHTTPRequestHandler):
    engine: Optional[BotEngine] = None

    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "service": "V1PER-MAX-Bot"}).encode("utf-8"))
        elif self.path == "/export":
            csv_path = export_leads_to_csv()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "exported_file": csv_path}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/webhook":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(body)
                # Извлечение параметров сообщения МАКС
                user_id = str(data.get("user_id") or data.get("from_id") or "guest")
                text = str(data.get("text") or data.get("action") or "")
                user_name = str(data.get("user_name") or "Пользователь")

                if self.engine:
                    self.engine.process_incoming(user_id, text, user_name)

                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(b'{"status":"ok"}')
            except Exception as exc:
                logger.error(f"Ошибка обработки вебхука: {exc}")
                self.send_response(500)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

# ==============================================================================
# 4. ИНТЕРАКТИВНЫЙ РЕЖИМ (--demo)
# ==============================================================================

def run_interactive_demo():
    """Запускает оффлайн интерактивную симуляцию работы бота в терминале."""
    print("=" * 70)
    print("🤖 СТУДИЯ V1PER: ОФФЛАЙН ДЕМО-СИМУЛЯТОР БОТА МАКС")
    print("=" * 70)
    print("Режим Zero-Pip: все сценарии работают локально без внешних токенов.\n")

    api = MaxApiClient(token="mock_token_v1per")
    engine = BotEngine(api)
    sim_user_id = "test_user_777"
    sim_user_name = "Алексей (Демо Заказчик)"

    print("Отправка /start...")
    reply = engine.process_incoming(sim_user_id, "/start", sim_user_name)
    print(f"\n[БОТ МАКС]:\n{reply}\n")

    while True:
        try:
            user_msg = input("\n[ВЫ]: ").strip()
            if not user_msg:
                continue
            if user_msg.lower() in ("exit", "quit", "выход"):
                print("Выход из демо-режима.")
                break
            reply = engine.process_incoming(sim_user_id, user_msg, sim_user_name)
            print(f"\n[БОТ МАКС]:\n{reply}")
        except (KeyboardInterrupt, EOFError):
            print("\nСессия завершена.")
            break

# ==============================================================================
# 5. ТОЧКА ВХОДА
# ==============================================================================

def signal_handler(signum, frame):
    logger.info("Получен сигнал завершения. Остановка сервера...")
    sys.exit(130)

def main():
    signal.signal(signal.SIGINT, signal_handler)
    init_db()

    if IS_DEMO:
        run_interactive_demo()
        return

    api = MaxApiClient()
    engine = BotEngine(api)
    MaxWebhookHandler.engine = engine

    server_address = (HOST, PORT)
    httpd = HTTPServer(server_address, MaxWebhookHandler)
    logger.info(f"Сервер бота МАКС запущен на http://{HOST}:{PORT}")
    logger.info("Эндпоинты: GET /health | GET /export | POST /webhook")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Сервер остановлен.")
        sys.exit(130)

if __name__ == "__main__":
    main()
