# -*- coding: utf-8 -*-
# ==============================================================================
# Модуль: config.py
# Назначение: Централизованная конфигурация коммерческого бота мессенджера МАКС
# Автор: V1PER (viper86rus-arch)
# Лицензия: MIT License (2026)
# ==============================================================================

import os
import sys
import logging
from pathlib import Path

# ==============================================================================
# 1. СИСТЕМНЫЕ ПУТИ И ОКРУЖЕНИЕ
# ==============================================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Загрузка .env без сторонних зависимостей (Zero-Pip)
ENV_FILE = BASE_DIR / ".env"
if ENV_FILE.exists():
    try:
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip().strip("'\"")
                    if k and k not in os.environ:
                        os.environ[k] = v
    except Exception as exc:
        sys.stderr.write(f"[CONFIG WARNING] Не удалось распарсить .env: {exc}\n")

# ==============================================================================
# 2. ПАРАМЕТРЫ MAX И TELEGRAM УВЕДОМЛЕНИЙ
# ==============================================================================

# Официальный продакшен API MAX (platform-api2.max.ru)
MAX_API_BASE_URL = os.getenv("MAX_API_BASE_URL", "https://platform-api2.max.ru").rstrip("/")
MAX_BOT_TOKEN = os.getenv("MAX_BOT_TOKEN", "").strip()

# Шлюз уведомлений в Telegram инженера (мгновенные лиды)
TG_NOTIFY_BOT_TOKEN = os.getenv("TG_NOTIFY_BOT_TOKEN", "").strip()
TG_NOTIFY_CHAT_ID = os.getenv("TG_NOTIFY_CHAT_ID", "9172025400").strip()

# Параметры локального сервера / вебхуков
PORT = int(os.getenv("PORT", "8080"))
HOST = os.getenv("HOST", "0.0.0.0")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip()

# Режим работы (production, mock, demo)
IS_DEMO = "--demo" in sys.argv or os.getenv("DEMO_MODE", "0") == "1"

# Администратор бота в МАКС (закрытая админ-панель и личные уведомления)
ADMIN_MAX_ID = os.getenv("ADMIN_MAX_ID", "31469506").strip()

# Каталоги хранения файлов и экспортов
DATABASE_PATH = str(DATA_DIR / "max_bot.db")
EXPORTS_DIR = BASE_DIR / "exports"
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
PROPOSALS_DIR = BASE_DIR / "proposals"
PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)

# Реквизиты самозанятого для генерации PDF-смет и договоров-оферт
SELLER_NAME = os.getenv("SELLER_NAME", "V1PER (Самозанятый исполнитель)")
SELLER_INN = os.getenv("SELLER_INN", "860200000000")
BANK_NAME = os.getenv("BANK_NAME", "АО Т-Банк")
BANK_BIK = os.getenv("BANK_BIK", "044525974")
BANK_CORR = os.getenv("BANK_CORR", "30101810145250000974")
BANK_ACCOUNT = os.getenv("BANK_ACCOUNT", "40817810000000000000")
PAYMENT_SBP = os.getenv("PAYMENT_SBP", "+79000000000")

# ==============================================================================
# 3. ЛОГИРОВАНИЕ
# ==============================================================================

LOG_FORMAT = "%(asctime)s [%(levelname)s] [%(name)s]: %(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("MAX_Commercial_Bot")
