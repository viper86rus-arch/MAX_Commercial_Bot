# -*- coding: utf-8 -*-
# ==============================================================================
# Модуль: max_api.py
# Назначение: Клиент официального Bot API мессенджера МАКС и Telegram-шлюз
# Автор: V1PER (viper86rus-arch)
# Лицензия: MIT License (2026)
# ==============================================================================

import ssl
import json
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from config import (
    MAX_API_BASE_URL, MAX_BOT_TOKEN,
    TG_NOTIFY_BOT_TOKEN, TG_NOTIFY_CHAT_ID,
    IS_DEMO, BASE_DIR, logger
)

# ==============================================================================
# 1. КЛИЕНТ ОФИЦИАЛЬНОГО API МАКС (platform-api2.max.ru)
# ==============================================================================

class MaxApiClient:
    """Официальный клиент REST API МАКС (платформа platform-api2.max.ru)."""

    def __init__(self, token: Optional[str] = None, base_url: Optional[str] = None):
        self.token = (token or MAX_BOT_TOKEN).strip()
        self.base_url = (base_url or MAX_API_BASE_URL).rstrip("/")
        
        # Настройка доверенного корневого сертификата Минцифры
        ca_path = BASE_DIR / "russian_trusted_root_ca.pem"
        if ca_path.exists():
            self.ssl_ctx = ssl.create_default_context(cafile=str(ca_path))
        else:
            self.ssl_ctx = ssl.create_default_context()
            self.ssl_ctx.check_hostname = False
            self.ssl_ctx.verify_mode = ssl.CERT_NONE

    def _headers(self) -> Dict[str, str]:
        # Официальный формат авторизации МАКС: сырой токен без префикса Bearer
        return {
            "Authorization": self.token,
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "V1PER-MAX-Commercial-Bot/1.0"
        }

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        timeout: int = 15
    ) -> Dict[str, Any]:
        """Выполняет сетевой HTTP-запрос к API МАКС."""
        if IS_DEMO or not self.token or self.token.startswith(("mock_", "test_")):
            logger.info(f"[MOCK MAX] {method} {endpoint} -> payload: {payload}")
            return {"status": "ok", "mock": True, "result": {"message_id": "mock_msg_1001"}}

        query_str = f"?{urllib.parse.urlencode(params)}" if params else ""
        url = f"{self.base_url}/{endpoint.lstrip('/')}{query_str}"
        data_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload else None
        req = urllib.request.Request(url, data=data_bytes, headers=self._headers(), method=method)

        try:
            with urllib.request.urlopen(req, context=self.ssl_ctx, timeout=timeout) as response:
                body = response.read().decode("utf-8")
                return json.loads(body) if body else {"status": "ok"}
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            logger.error(f"Ошибка API МАКС HTTP {exc.code} на {url}: {err_body}")
            return {"status": "error", "code": exc.code, "message": err_body}
        except Exception as exc:
            logger.error(f"Сетевой сбой при обращении к API МАКС: {exc}")
            return {"status": "error", "message": str(exc)}

    def get_me(self) -> Dict[str, Any]:
        """Проверяет токен и возвращает актуальный профиль бота."""
        return self._request("GET", "/me")

    def get_updates(self, marker: Optional[int] = None, timeout: int = 25) -> Tuple[List[Dict[str, Any]], Optional[int]]:
        """
        Long Polling метод получения событий мессенджера МАКС (GET /updates).
        Возвращает кортеж (список_событий, следующий_маркер).
        """
        params: Dict[str, Any] = {"timeout": timeout}
        if marker is not None:
            params["marker"] = marker

        res = self._request("GET", "/updates", params=params, timeout=timeout + 5)
        if isinstance(res, dict) and "updates" in res:
            return res.get("updates", []), res.get("marker")
        return [], marker

    def send_message(
        self,
        recipient_id: Any,
        text: str = "",
        keyboard: Optional[List[List[Dict[str, str]]]] = None,
        is_chat: bool = False
    ) -> Dict[str, Any]:
        """
        Отправляет текстовое сообщение пользователю или в чат
        в полном соответствии со спецификацией МАКС Bot API.
        """
        params: Dict[str, Any] = {}
        s_id = str(recipient_id)
        if is_chat or s_id.startswith(("-", "chat")):
            params["chat_id"] = s_id
        else:
            params["user_id"] = s_id

        body: Dict[str, Any] = {
            "text": text,
            "format": "html"
        }

        # Формирование inline_keyboard по официальной схеме МАКС
        if keyboard:
            formatted_rows: List[List[Dict[str, str]]] = []
            for row in keyboard:
                formatted_row: List[Dict[str, str]] = []
                for btn in row:
                    btn_text = btn.get("text", "Кнопка")
                    action = btn.get("action") or btn.get("payload") or btn_text
                    formatted_row.append({
                        "type": "callback",
                        "text": btn_text,
                        "payload": action
                    })
                formatted_rows.append(formatted_row)

            body["attachments"] = [
                {
                    "type": "inline_keyboard",
                    "payload": {
                        "buttons": formatted_rows
                    }
                }
            ]

        return self._request("POST", "/messages", params=params, payload=body)

    def answer_callback(self, callback_id: str, text: Optional[str] = None) -> Dict[str, Any]:
        """Подтверждает получение callback-события нажатия кнопки (POST /answers)."""
        params = {"callback_id": callback_id}
        payload = {"notification": text} if text else {}
        return self._request("POST", "/answers", params=params, payload=payload)

# ==============================================================================
# 2. ШЛЮЗ МГНОВЕННЫХ УВЕДОМЛЕНИЙ В TELEGRAM
# ==============================================================================

def send_telegram_alert(lead_id: int, lead_data: Dict[str, Any]) -> bool:
    """
    Отправляет мгновенное уведомление в Telegram разработчика (@viper_order_bot),
    когда клиент заполняет заявку в МАКС.
    """
    if not TG_NOTIFY_BOT_TOKEN or not TG_NOTIFY_CHAT_ID:
        logger.warning("Telegram Bot Token или Chat ID не заданы. Пропуск отправки в TG.")
        return False

    name = lead_data.get("name", "Аноним")
    phone = lead_data.get("phone", "Не указан")
    service = lead_data.get("service", "Не выбран")
    budget = lead_data.get("budget", "Договорной")
    desc = lead_data.get("desc", "—")
    max_id = lead_data.get("max_id", "—")

    text = (
        f"⚡ <b>НОВАЯ ЗАЯВКА ИЗ МАКС #{lead_id}</b>\n\n"
        f"👤 <b>Заказчик:</b> {name}\n"
        f"📞 <b>Контакт:</b> {phone}\n"
        f"🆔 <b>MAX ID:</b> <code>{max_id}</code>\n"
        f"💼 <b>Услуга:</b> {service}\n"
        f"💰 <b>Бюджет:</b> {budget}\n"
        f"📝 <b>Техзадание:</b> {desc}\n\n"
        f"<i>Студия автоматизации V1PER (viper86rus-arch)</i>"
    )

    url = f"https://api.telegram.org/bot{TG_NOTIFY_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_NOTIFY_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.status == 200
    except Exception as exc:
        logger.error(f"Не удалось отправить уведомление в Telegram: {exc}")
        return False
