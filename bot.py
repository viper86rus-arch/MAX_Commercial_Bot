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
    "👋 <b>Добро пожаловать в V1PER IT Solutions!</b>\n\n"
    "Студия промышленной разработки и автоматизации бизнес-процессов.\n\n"
    "Реализуем проекты по вашему готовому ТЗ либо <b>поможем грамотно составить и декомпозировать техзадание с нуля</b> под ваши бизнес-задачи.\n\n"
    "• Рассчитаем прозрачную смету и сроки\n"
    "• Покажем реальные кейсы и чистую архитектуру\n"
    "• Примем задачу в работу 24/7\n\n"
    "Выберите интересующий раздел:"
)

MAIN_KEYBOARD = [
    [{"text": "💼 Услуги и прайс", "action": "btn_services"},
     {"text": "🧮 Калькулятор", "action": "btn_calc"}],
    [{"text": "📂 Наше портфолио", "action": "btn_portfolio"},
     {"text": "📩 Оставить заявку", "action": "btn_order"}],
    [{"text": "👤 Прямой контакт", "action": "btn_contact"}]
]

SERVICES_TEXT = (
    "💼 <b>Направления разработки и прайс V1PER IT Solutions (2026):</b>\n\n"
    "1. 📝 <b>Инженерное проектирование и составление ТЗ</b>\n"
    "   • Декомпозиция бизнес-задач, схема базы данных, эндпоинты API, User Flow.\n"
    "   • Сроки: от 24 часов. Стоимость: <b>2 500 – 5 000 ₽</b>.\n"
    "   <i>* Бесплатно при заказе разработки проекта под ключ!</i>\n\n"
    "2. 🤖 <b>Чат-боты для бизнеса (Telegram & МАКС)</b>\n"
    "   • Визитки, продажи, закрытые VIP-клубы, оплата (ЮKassa/СБП/Stars).\n"
    "   • Сроки: от 1 до 3 дней. Стоимость: <b>3 500 – 12 000 ₽</b>.\n\n"
    "3. 🛍️ <b>Telegram Mini Apps (TMA) & WebApps</b>\n"
    "   • Полнофункциональные интернет-магазины и веб-сервисы внутри мессенджера.\n"
    "   • Сроки: от 3 до 5 дней. Стоимость: <b>15 000 – 25 000 ₽</b>.\n\n"
    "4. 📊 <b>Высокоскоростной парсинг данных и маркетплейсов</b>\n"
    "   • Wildberries, Ozon, Авито, классифайды, выгрузка в Excel (UTF-8 BOM).\n"
    "   • Сроки: от 24 часов. Стоимость: <b>4 500 – 10 000 ₽</b>.\n\n"
    "5. 🏢 <b>Интеграция CRM-систем (Битрикс24 / amoCRM)</b>\n"
    "   • Автоматическое управление группами, сделками и синхронизация баз.\n"
    "   • Сроки: от 2 дней. Стоимость: <b>6 500 – 14 000 ₽</b>.\n\n"
    "6. 📑 <b>Автоматизация Excel и обработка прайс-листов</b>\n"
    "   • Сведение сотен прайсов поставщиков в единый чистый каталог, формулы.\n"
    "   • Сроки: от 24 часов. Стоимость: <b>3 500 – 6 000 ₽</b>.\n\n"
    "🛡️ <i>Гарантия: 30 дней бесплатной техподдержки на весь код.</i>"
)

PORTFOLIO_TEXT = (
    "📂 <b>Флагманские проекты V1PER IT Solutions (GitHub):</b>\n\n"
    "1. 🎯 <b><a href=\"https://github.com/viper86rus-arch/Wildberries_Fast_Scraper\">Wildberries Fast Scraper</a></b>\n"
    "   • Высокоскоростной парсер каталога WB без браузера. Расчёт цен с СПП (WB Кошелёк), остатки по РФ, экспорт в Excel (UTF-8 BOM).\n\n"
    "2. ⚡ <b><a href=\"https://github.com/viper86rus-arch/Async_TCP_Scanner\">Async TCP Scanner</a></b>\n"
    "   • Асинхронный сканер портов и аудит сетевой безопасности на Python asyncio. Захват баннеров служб (SSH/HTTP), контроль семафором.\n\n"
    "3. 🌐 <b><a href=\"https://github.com/viper86rus-arch/Enterprise_Web_Scraper\">Enterprise Web Scraper</a></b>\n"
    "   • Сбор динамических данных на Playwright в Stealth-режиме. Веб-панель управления на FastAPI и стриминг логов через WebSockets.\n\n"
    "4. 🤖 <b><a href=\"https://github.com/viper86rus-arch/Telegram_Commercial_Bot\">Telegram Commercial Bot</a></b>\n"
    "   • Платформа продаж для бизнеса: расчет сметы, векторный генератор A4 PDF со штампом ЭЦП (63-ФЗ), прием оплат и микро-CRM.\n\n"
    "5. 🛍️ <b><a href=\"https://github.com/viper86rus-arch/Telegram_Commerce_MiniApp\">Telegram Commerce MiniApp</a></b>\n"
    "   • Полнофункциональный интернет-магазин внутри мессенджера (TMA): витрина товаров, интерактивная корзина, оформление заказов и чеки.\n\n"
    "6. 🏢 <b><a href=\"https://github.com/viper86rus-arch/CRM_Group_Manager\">CRM Group Manager</a></b>\n"
    "   • Микросервис оркестрации проектных групп в Telegram (MTProto) и МАКС по вебхукам корпоративных CRM (Битрикс24 / amoCRM).\n\n"
    "🔗 <i>Исходный код всех решений открыт на GitHub:</i> <a href=\"https://github.com/viper86rus-arch\">github.com/viper86rus-arch</a>"
)

CONTACT_TEXT = (
    "👤 <b>Прямой контакт ведущего инженера:</b>\n\n"
    "• <b>Бренд:</b> V1PER IT Solutions (viper86rus-arch)\n"
    "• <b>Специализация:</b> Senior Python / Automation Engineer\n"
    "• <b>Формат:</b> Разработка по готовому ТЗ или проектирование требований с нуля\n"
    "• <b>Статус:</b> Официальный самозанятый РФ (работа по договору / ЭДО / чеки)\n"
    "• <b>Гарантия:</b> 30 дней бесплатной технической поддержки на весь код."
)

# ==============================================================================
# КОНФИГУРАЦИЯ ИНТЕРАКТИВНОГО КАЛЬКУЛЯТОРА СМЕТЫ
# ==============================================================================

CALCULATOR_CONFIG = {
    "types": {
        "bot": {"title": "🤖 Чат-бот (Telegram / МАКС)", "price": 3500, "days": 1},
        "parser": {"title": "📊 Парсер данных / WB / Ozon", "price": 4500, "days": 1},
        "crm": {"title": "🏢 CRM-интеграция / Микросервис", "price": 6500, "days": 2},
        "miniapp": {"title": "🛍️ Telegram Mini App (TMA)", "price": 15000, "days": 3},
        "tz": {"title": "📝 Инженерное ТЗ с нуля", "price": 2500, "days": 1}
    },
    "db": {
        "yes": {"title": "🗄 Да, с базой данных (PostgreSQL / SQLite)", "price": 3000, "days": 1},
        "no": {"title": "❌ Без базы данных (только логика/API)", "price": 0, "days": 0},
        "basic": {"title": "📄 Базовое ТЗ (БД, API, User Flow)", "price": 0, "days": 0},
        "corp": {"title": "📑 Корпоративное ТЗ (C4, Swagger, ГОСТ)", "price": 2500, "days": 1}
    },
    "extra": {
        "pay": {"title": "💳 Онлайн-оплата (ЮKassa / СБП / Stars)", "price": 4500, "days": 1},
        "admin": {"title": "📊 Панель управления и рассылки", "price": 4000, "days": 1},
        "all": {"title": "🚀 Всё вместе: Оплата + Админка", "price": 7500, "days": 2},
        "none": {"title": "⏩ Без доп. модулей", "price": 0, "days": 0}
    }
}

# ==============================================================================
# 2. ОБРАБОТЧИК СООБЩЕНИЙ И FSM (State Machine)
# ==============================================================================

class BotEngine:
    """Диалоговый движок с поддержкой многошаговых сценариев."""

    def __init__(self, api_client: MaxApiClient, db_path: Optional[str] = None):
        self.api = api_client
        self.db_path = db_path or DATABASE_PATH

    def _handle_calculator(self, user_id: str, text: str, user_name: str = "") -> str:
        """Интерактивный пошаговый квиз-калькулятор стоимости и сроков проекта."""
        # Шаг 1: Выбор направления
        if text in ("🧮 Калькулятор", "🧮 Калькулятор сметы", "btn_calc", "/calc", "calc_step1"):
            prompt = (
                "🧮 <b>ИНТЕРАКТИВНЫЙ КАЛЬКУЛЯТОР СМЕТЫ (Шаг 1 из 3):</b>\n\n"
                "Выберите основное направление вашего проекта:"
            )
            keyboard = [
                [{"text": "🤖 Чат-бот (от 3 500 ₽)", "action": "calc_s2:bot"}],
                [{"text": "📊 Парсер данных (от 4 500 ₽)", "action": "calc_s2:parser"}],
                [{"text": "🏢 CRM-интеграция (от 6 500 ₽)", "action": "calc_s2:crm"}],
                [{"text": "🛍️ Mini App TMA (от 15 000 ₽)", "action": "calc_s2:miniapp"}],
                [{"text": "📝 Разработка ТЗ (от 2 500 ₽)", "action": "calc_s2:tz"}],
                [{"text": "◀️ В главное меню", "action": "btn_menu"}]
            ]
            self.api.send_message(user_id, prompt, keyboard)
            return prompt

        # Шаг 2: База данных или опции ТЗ
        if text.startswith("calc_s2:"):
            parts = text.split(":")
            q_type = parts[1]
            t_info = CALCULATOR_CONFIG["types"].get(q_type, CALCULATOR_CONFIG["types"]["bot"])

            if q_type == "tz":
                prompt = (
                    "🧮 <b>ИНТЕРАКТИВНЫЙ КАЛЬКУЛЯТОР СМЕТЫ (Шаг 2 из 2):</b>\n\n"
                    f"Направление: <b>{t_info['title']}</b>\n\n"
                    "Выберите требуемый уровень детализации техзадания:"
                )
                keyboard = [
                    [{"text": "📄 Базовое ТЗ (БД, API, User Flow) — 2 500 ₽", "action": "calc_res:tz:basic:none"}],
                    [{"text": "📑 Enterprise ТЗ (C4, Swagger, ГОСТ) — 5 000 ₽", "action": "calc_res:tz:corp:none"}],
                    [{"text": "◀️ Назад", "action": "calc_step1"}, {"text": "◀️ В меню", "action": "btn_menu"}]
                ]
            else:
                prompt = (
                    "🧮 <b>ИНТЕРАКТИВНЫЙ КАЛЬКУЛЯТОР СМЕТЫ (Шаг 2 из 3):</b>\n\n"
                    f"Выбрано: <b>{t_info['title']}</b>\n\n"
                    "Требуется ли подключение базы данных (PostgreSQL / SQLite) для хранения пользователей, заказов или истории?"
                )
                keyboard = [
                    [{"text": "🗄 Да, нужна база (+3 000 ₽)", "action": f"calc_s3:{q_type}:yes"}],
                    [{"text": "❌ Нет, без базы данных (0 ₽)", "action": f"calc_s3:{q_type}:no"}],
                    [{"text": "◀️ Назад", "action": "calc_step1"}, {"text": "◀️ В меню", "action": "btn_menu"}]
                ]
            self.api.send_message(user_id, prompt, keyboard)
            return prompt

        # Шаг 3: Дополнительные бизнес-модули
        if text.startswith("calc_s3:"):
            parts = text.split(":")
            q_type = parts[1]
            q_db = parts[2]
            t_info = CALCULATOR_CONFIG["types"].get(q_type, CALCULATOR_CONFIG["types"]["bot"])
            db_info = CALCULATOR_CONFIG["db"].get(q_db, CALCULATOR_CONFIG["db"]["no"])

            prompt = (
                "🧮 <b>ИНТЕРАКТИВНЫЙ КАЛЬКУЛЯТОР СМЕТЫ (Шаг 3 из 3):</b>\n\n"
                f"Выбрано: <b>{t_info['title']}</b>\n"
                f"База данных: <b>{db_info['title']}</b>\n\n"
                "Нужны ли дополнительные бизнес-модули?"
            )
            keyboard = [
                [{"text": "💳 Онлайн-оплата (+4 500 ₽)", "action": f"calc_res:{q_type}:{q_db}:pay"}],
                [{"text": "📊 Админка и рассылки (+4 000 ₽)", "action": f"calc_res:{q_type}:{q_db}:admin"}],
                [{"text": "🚀 Всё вместе: Оплата + Админка (+7 500 ₽)", "action": f"calc_res:{q_type}:{q_db}:all"}],
                [{"text": "⏩ Без доп. модулей (0 ₽)", "action": f"calc_res:{q_type}:{q_db}:none"}],
                [{"text": "◀️ Назад", "action": f"calc_s2:{q_type}"}, {"text": "◀️ В меню", "action": "btn_menu"}]
            ]
            self.api.send_message(user_id, prompt, keyboard)
            return prompt

        # Итоговый расчет сметы
        if text.startswith("calc_res:"):
            parts = text.split(":")
            q_type, q_db, q_extra = parts[1], parts[2], parts[3]
            t_info = CALCULATOR_CONFIG["types"].get(q_type, CALCULATOR_CONFIG["types"]["bot"])
            db_info = CALCULATOR_CONFIG["db"].get(q_db, CALCULATOR_CONFIG["db"]["no"])
            ext_info = CALCULATOR_CONFIG["extra"].get(q_extra, CALCULATOR_CONFIG["extra"]["none"])

            total_price = t_info["price"] + db_info["price"] + ext_info["price"]
            total_days = max(1, t_info["days"] + db_info["days"] + ext_info["days"])

            prompt = (
                "🧾 <b>ИТОГОВЫЙ РАСЧЁТ СМЕТЫ ПРОЕКТА:</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"📌 <b>Направление:</b> {t_info['title']}\n"
                f"🗄 <b>База данных:</b> {db_info['title']}\n"
                f"⚙️ <b>Дополнения:</b> {ext_info['title']}\n\n"
                f"💰 <b>Расчётная стоимость:</b> <b>{total_price:,} ₽</b>\n"
                f"⏱ <b>Срок разработки:</b> <b>{total_days} дн.</b>\n"
                f"🛡 <b>Гарантия:</b> 30 дней бесплатной техподдержки\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "<i>Нажмите «Оформить заказ», чтобы зафиксировать смету и сразу передать задачу в работу:</i>"
            )
            keyboard = [
                [{"text": f"✅ Заказать смету ({total_price:,} ₽)", "action": f"calc_ord:{q_type}:{q_db}:{q_extra}:{total_price}:{total_days}"}],
                [{"text": "🔄 Пересчитать заново", "action": "calc_step1"}],
                [{"text": "◀️ В главное меню", "action": "btn_menu"}]
            ]
            self.api.send_message(user_id, prompt, keyboard)
            return prompt

        # Оформление заказа по смете -> переход к вводу контакта
        if text.startswith("calc_ord:"):
            parts = text.split(":")
            q_type, q_db, q_extra = parts[1], parts[2], parts[3]
            total_price = int(parts[4])
            total_days = int(parts[5])

            t_info = CALCULATOR_CONFIG["types"].get(q_type, CALCULATOR_CONFIG["types"]["bot"])
            db_info = CALCULATOR_CONFIG["db"].get(q_db, CALCULATOR_CONFIG["db"]["no"])
            ext_info = CALCULATOR_CONFIG["extra"].get(q_extra, CALCULATOR_CONFIG["extra"]["none"])

            calc_session = {
                "name": user_name or "Пользователь МАКС",
                "max_id": user_id,
                "service": t_info["title"],
                "budget": f"{total_price:,} ₽ ({total_days} дн.)",
                "desc": (
                    f"Заказ по смете калькулятора:\n"
                    f"• Проект: {t_info['title']}\n"
                    f"• БД: {db_info['title']}\n"
                    f"• Дополнения: {ext_info['title']}\n"
                    f"• Срок: {total_days} дн."
                )
            }
            set_user_state(user_id, "ask_contact", calc_session, self.db_path)

            prompt = (
                f"📋 <b>Оформление заказа по смете ({total_price:,} ₽):</b>\n\n"
                f"• <b>Проект:</b> {t_info['title']}\n"
                f"• <b>Конфигурация:</b> {db_info['title']}, {ext_info['title']}\n"
                f"• <b>Срок:</b> ~{total_days} дн.\n\n"
                "📞 <b>Укажите ваш контакт для связи</b> (номер телефона, ник в Telegram / МАКС или email), "
                "и ведущий инженер свяжется с вами в течение 15 минут для подтверждения сметы:"
            )
            keyboard = [
                [{"text": "◀️ Отмена / В главное меню", "action": "btn_menu"}]
            ]
            self.api.send_message(user_id, prompt, keyboard)
            return prompt

        return self._handle_calculator(user_id, "calc_step1", user_name)

    def process_incoming(self, user_id: str, text: str, user_name: str = "") -> str:
        """Обрабатывает входящее действие пользователя и возвращает ответ."""
        text = text.strip()
        step, session = get_user_state(user_id, self.db_path)

        # Команды сброса и перезапуска
        if text in ("/start", "/menu", "Главное меню", "btn_menu"):
            clear_user_state(user_id, self.db_path)
            self.api.send_message(user_id, WELCOME_TEXT, MAIN_KEYBOARD)
            return WELCOME_TEXT

        # Интерактивный калькулятор сметы (пошаговый квиз-конфигуратор)
        if text in ("🧮 Калькулятор", "🧮 Калькулятор сметы", "btn_calc", "/calc") or text.startswith(("calc_", "calc_s2:", "calc_s3:", "calc_res:", "calc_ord:")):
            return self._handle_calculator(user_id, text, user_name)

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
                "Какая задача стоит перед вами?\n"
                "1. Составить техническое задание (ТЗ)\n"
                "2. Чат-бот (Telegram / МАКС)\n"
                "3. Telegram Mini App (TMA)\n"
                "4. Парсинг данных / Маркетплейсы\n"
                "5. Интеграция с CRM\n"
                "6. Автоматизация Excel / Скрипты\n"
                "7. Другая задача\n\n"
                "<i>Напишите номер варианта или опишите своими словами:</i>"
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

import time

def run_polling(engine: BotEngine, api: MaxApiClient):
    """Слушает события МАКС через официальный Long Polling (GET /updates)."""
    logger.info("Запуск боевого слушателя МАКС Long Polling...")
    me = api.get_me()
    if isinstance(me, dict) and "user_id" in me:
        logger.info(f"✅ Успешная авторизация бота: @{me.get('username')} ({me.get('first_name')}, ID: {me.get('user_id')})")
    
    marker = None
    while True:
        try:
            updates, marker = api.get_updates(marker=marker, timeout=20)
            for upd in updates:
                upd_type = upd.get("update_type")
                if upd_type == "message_created":
                    msg = upd.get("message", {})
                    sender = msg.get("sender", {})
                    user_id = str(sender.get("user_id", ""))
                    user_name = sender.get("name") or sender.get("first_name", "Пользователь")
                    body = msg.get("body", {})
                    text = body.get("text", "")
                    if user_id and text:
                        logger.info(f"[ВХОДЯЩЕЕ СООБЩЕНИЕ] от {user_name} ({user_id}): {text}")
                        engine.process_incoming(user_id, text, user_name)
                elif upd_type == "message_callback":
                    cb = upd.get("callback", {})
                    user = cb.get("user", {})
                    user_id = str(user.get("user_id", ""))
                    user_name = user.get("name") or user.get("first_name", "Пользователь")
                    payload = cb.get("payload", "")
                    cb_id = cb.get("callback_id")
                    if cb_id:
                        api.answer_callback(cb_id)
                    if user_id and payload:
                        logger.info(f"[НАЖАТИЕ КНОПКИ] от {user_name} ({user_id}): {payload}")
                        engine.process_incoming(user_id, payload, user_name)
                elif upd_type == "bot_started":
                    user = upd.get("user", {})
                    user_id = str(user.get("user_id", ""))
                    user_name = user.get("name") or user.get("first_name", "Пользователь")
                    logger.info(f"[СТАРТ БОТА] пользователь {user_name} ({user_id})")
                    engine.process_incoming(user_id, "/start", user_name)
        except KeyboardInterrupt:
            logger.info("Остановка Long Polling...")
            break
        except Exception as e:
            logger.error(f"Ошибка в цикле Long Polling: {e}")
            time.sleep(2)

def signal_handler(signum, frame):
    logger.info("Получен сигнал завершения. Остановка бота...")
    sys.exit(130)

def main():
    signal.signal(signal.SIGINT, signal_handler)
    init_db()

    if IS_DEMO:
        run_interactive_demo()
        return

    api = MaxApiClient()
    engine = BotEngine(api)

    if "--webhook" in sys.argv:
        MaxWebhookHandler.engine = engine
        server_address = (HOST, PORT)
        httpd = HTTPServer(server_address, MaxWebhookHandler)
        logger.info(f"Сервер вебхуков МАКС запущен на http://{HOST}:{PORT}")
        logger.info("Эндпоинты: GET /health | GET /export | POST /webhook")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            logger.info("Сервер остановлен.")
            sys.exit(130)
    else:
        run_polling(engine, api)

if __name__ == "__main__":
    main()
