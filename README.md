# 🤖 V1PER IT Solutions | Enterprise Commercial Messenger MAX Bot & Sales Platform

[![Tests](https://img.shields.io/badge/Tests-9%2F9%20Passed%20(100%25)-brightgreen.svg)](tests/)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Studio](https://img.shields.io/badge/Studio-V1PER_IT_Solutions-emerald.svg)]()
[![Architecture: Clean Zero--Pip](https://img.shields.io/badge/Architecture-Clean%20Zero--Pip-blueviolet.svg)]()
[![Platform: MAX 2026](https://img.shields.io/badge/Platform-MAX%20API%20v2-purple.svg)](https://dev.max.ru)
[![Digital Stamp](https://img.shields.io/badge/Electronic_Signature-63--FZ%20Compliant-red.svg)](https://github.com/viper86rus-arch/MAX_Commercial_Bot)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Автономный промышленный коммерческий чат-бот студии V1PER IT Solutions для официальной российской платформы Мессенджер МАКС (`platform-api2.max.ru`).**  
> Полный цикл автоматизации первичных продаж: 3-шаговый интерактивный калькулятор сметы, автоматическая генерация официальных коммерческих предложений в A4 PDF с векторным штампом усиленной квалифицированной электронной подписи (63-ФЗ РФ), изолированная панель администратора (`/admin`) со сквозной воронкой и выгрузкой в Excel CSV, и защищённые push-уведомления инженеру.

---

## 📋 Архитектурный поток (FSM & PDF Generation)

```mermaid
flowchart TD
    USR["📱 Клиент в Мессенджере МАКС"] -->|1. /start| BOT["🤖 MAX Commercial Bot (V1PER IT Solutions)"]
    BOT -->|2. Интерактивное меню| MENU{"Выбор раздела"}
    
    MENU -->|💼 Услуги и цены| S1["Прайс-лист и условия (боты, парсеры, CRM, ТЗ)"]
    MENU -->|📂 Портфолио| S2["Флагманские решения V1PER IT Solutions"]
    MENU -->|🧮 Калькулятор сметы| S3["3-шаговый интерактивный степпер расчёта"]
    MENU -->|📩 Оформить заказ| FSM["📝 Опросник квалификации лида"]
    
    S3 -->|Выбор стека и модулей| CALC_RES["🧾 Итоговый расчёт бюджета и сроков"]
    CALC_RES -->|✅ Заказать смету| FSM
    
    FSM --> DB[("💾 SQLite Хранилище (leads.db)")]:::db
    FSM --> PDF["📄 Pure-Python Генератор сметы в PDF (63-ФЗ)"]
    
    PDF --> CDN["☁️ MAX CDN Upload Gateway (fu.oneme.ru)"]
    CDN -->|Доставка КП клиенту| USR
    CDN -->|Закрытый алерт лида| ADM["🔒 Администратор студии (ADMIN_MAX_ID)"]
    
    ADM -->|Команда /admin| ADM_PANEL["📊 Аналитическая панель воронки"]
    ADM_PANEL -->|1 клик| CSV["📥 Выгрузка базы в Excel (UTF-8 BOM CSV)"]

    classDef db fill:#0d1117,stroke:#58a6ff,stroke-width:2px,color:#fff;
```

---

## 🌟 Ключевые возможности и инженерные решения

1. **Clean Zero-Pip Architecture (Чистый Python Standard Library)**:
   * Ядро бота, сетевой клиент и генератор документов построены исключительно на стандартной библиотеке Python (`urllib.request`, `sqlite3`, `json`, `dataclasses`).
   * Внешние pip-пакеты не требуются — запуск "из коробки" на любой системе без риска конфликтов зависимостей.

2. **Официальный стек Мессенджера МАКС 2026 года**:
   * Интеграция с официальным шлюзом `https://platform-api2.max.ru` с поддержкой сертификатов Минцифры РФ (`russian_trusted_root_ca.pem`).
   * Поддержка Long Polling и Webhook-режимов с надёжной обработкой `callback`-событий и санитизацией payload.

3. **🧮 3-шаговый интерактивный калькулятор сметы (`_handle_calculator`)**:
   * Пошаговый конфигуратор: выбор типа системы (Telegram/MAX бот, парсер маркетплейсов, ТЗ, автоматизация), выбор БД и доп. модулей (эквайринг, админ-панель).
   * Автоматический расчёт бюджета и сроков с мгновенным переносом параметров в форму заказа.

4. **📄 Pure-Python генератор коммерческих предложений с ЭЦП (63-ФЗ)**:
   * Векторный рендеринг PDF 1.4 A4 с системным TrueType-шрифтом Roboto.
   * Синий штамп простой электронной подписи (ПЭП, 63-ФЗ) с уникальным криптографическим хэшем SHA-256 документа.
   * Прямая загрузка на CDN МАКС (`fu.oneme.ru`) и нативная отправка PDF-файла клиенту прямо в чат.

5. **🔒 Закрытая панель администратора (`/admin`)**:
   * Строгая авторизация по `ADMIN_MAX_ID`: обычным пользователям панель недоступна.
   * Метрики в реальном времени: количество лидов, новые заявки, подтверждённые заказы и прогнозируемая выручка (₽).
   * Мгновенный экспорт актуального реестра заказов в `.csv` с кодировкой `UTF-8 с BOM` (`utf-8-sig`) и русскими разделителями `;` для безупречного открытия в Microsoft Excel.

6. **🚨 Защищённые алерты лидов**:
   * При оформлении заказа ведущий инженер мгновенно получает уведомление в МАКС и Telegram с контактами клиента, сметой и прикреплённым PDF-документом.

---

## 🏗 Архитектура проекта

```text
MAX_Commercial_Bot/
├── bot.py                  # Главный диспетчер Long Polling/Webhook, FSM и меню
├── max_api.py              # Клиент MAX Bot API 2026 (сообщения, колбэки, загрузка файлов)
├── pdf_generator.py        # Векторный генератор PDF-смет с цифровой подписью (63-ФЗ)
├── database.py             # SQLite3 CRM, воронка и экспорт в Excel CSV (UTF-8 BOM)
├── config.py               # Конфигурация из .env (токены, ADMIN_MAX_ID, пути)
├── tests/
│   └── test_max_bot.py     # Модульные тесты (FSM, калькулятор, PDF, экспорт)
├── exports/                # Сгенерированные выгрузки реестра заказов
├── proposals/              # Сгенерированные клиентские сметы в PDF
├── .env.example            # Шаблон переменных окружения
├── .gitignore              # Исключение секретов, баз данных и файлов
└── README.md               # Документация проекта
```

---

## 🛠️ Быстрый старт

### 1. Настройка конфигурации
```bash
cp .env.example .env
# Заполните MAX_BOT_TOKEN и ADMIN_MAX_ID
```

### 2. Запуск в интерактивном демо-режиме (без токена)
```bash
python bot.py --demo
```

### 3. Запуск промышленного сервиса
```bash
python bot.py
```

### 4. Экспорт заявок в CSV для бухгалтерии
```bash
curl http://localhost:8080/export
```
Либо нажмите кнопку **«📥 Выгрузить Excel (CSV)»** прямо в закрытом чате администратора (`/admin`).

---

## 🧪 Модульное тестирование

Проект покрыт автономным тестовым комплексом (9/9 тестов):
```bash
python3 -m unittest discover -s tests -v
```

---

## 🖥️ Поддерживаемые операционные системы

* Linux (Ubuntu, Debian, RHEL)
* macOS
* Windows Server

---

## 📄 Лицензия и авторство

* **Автор разработки:** V1PER ([`viper86rus-arch`](https://github.com/viper86rus-arch))
* **Лицензия:** [MIT License](LICENSE) (2026) — открытый исходный код без ограничений на коммерческое и образовательное применение.
