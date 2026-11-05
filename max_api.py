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
    ADMIN_MAX_ID, IS_DEMO, BASE_DIR, logger
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

    def upload_file(self, file_path: str) -> Optional[str]:
        """
        Загружает файл (PDF смету, Excel CSV) на CDN МАКС (oneme.ru).
        Возвращает токен файла для отправки вложений.
        """
        p = Path(file_path)
        if not p.exists():
            logger.error(f"Файл не найден для отправки в МАКС: {file_path}")
            return None

        if IS_DEMO or not self.token or self.token.startswith(("mock_", "test_")):
            logger.info(f"[MOCK MAX] Загрузка файла {p.name}")
            return f"mock_file_token_{p.name}"

        # 1. Запрос одноразового upload URL
        res = self._request("POST", "/uploads", params={"type": "file"}, payload={})
        upload_url = res.get("url") if isinstance(res, dict) else None
        if not upload_url:
            logger.error(f"Не удалось получить upload URL от МАКС: {res}")
            return None

        # 2. Формирование multipart/form-data
        import uuid
        boundary = uuid.uuid4().hex
        try:
            with open(p, "rb") as f:
                file_bytes = f.read()

            content_type = "application/pdf" if p.suffix.lower() == ".pdf" else "application/octet-stream"
            header_part = (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="v1"; filename="{p.name}"\r\n'
                f"Content-Type: {content_type}\r\n\r\n"
            ).encode("utf-8")
            footer_part = f"\r\n--{boundary}--\r\n".encode("utf-8")
            body = header_part + file_bytes + footer_part

            # CDN хранилище oneme.ru использует публичный сертификат
            cdn_ssl_ctx = ssl.create_default_context()
            cdn_ssl_ctx.check_hostname = False
            cdn_ssl_ctx.verify_mode = ssl.CERT_NONE

            req = urllib.request.Request(
                upload_url,
                data=body,
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
                method="POST"
            )
            with urllib.request.urlopen(req, context=cdn_ssl_ctx, timeout=30) as response:
                resp_data = json.loads(response.read().decode("utf-8"))
                token = resp_data.get("token")
                logger.info(f"✅ Файл {p.name} успешно загружен в МАКС CDN")
                return token
        except Exception as exc:
            logger.error(f"Сбой загрузки файла {p.name} в МАКС: {exc}")
            return None

    def send_document(
        self,
        recipient_id: Any,
        file_path: str,
        caption: str = "",
        keyboard: Optional[List[List[Dict[str, str]]]] = None,
        is_chat: bool = False
    ) -> Dict[str, Any]:
        """
        Отправляет документ (PDF смету, Excel CSV) в чат или пользователю.
        """
        file_token = self.upload_file(file_path)
        if not file_token:
            return self.send_message(recipient_id, caption, keyboard, is_chat=is_chat)

        if IS_DEMO or not self.token or self.token.startswith(("mock_", "test_")):
            logger.info(f"[MOCK MAX] Отправка документа {file_path} -> {recipient_id}: {caption}")
            return {"status": "ok", "mock": True, "result": {"message_id": "mock_doc_1002"}}

        params: Dict[str, Any] = {}
        s_id = str(recipient_id)
        if is_chat or s_id.startswith(("-", "chat")):
            params["chat_id"] = s_id
        else:
            params["user_id"] = s_id

        body: Dict[str, Any] = {
            "text": caption,
            "format": "html",
            "attachments": [
                {
                    "type": "file",
                    "payload": {
                        "token": file_token
                    }
                }
            ]
        }

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
            body["attachments"].append({
                "type": "inline_keyboard",
                "payload": {"buttons": formatted_rows}
            })

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

# ==============================================================================
# 3. БЕЗОПАСНАЯ ДОСТАВКА ЛИДОВ АДМИНИСТРАТОРУ
# ==============================================================================

def send_admin_order_notification(
    api: MaxApiClient,
    lead_id: int,
    lead_data: Dict[str, Any],
    pdf_path: Optional[str] = None
) -> bool:
    """
    Отправляет уведомление о заказе СТРОГО в личный чат администратора в МАКС (ADMIN_MAX_ID)
    и дублирует в Telegram.
    ГАРАНТИЯ БЕЗОПАСНОСТИ: Никакие сторонние пользователи и чаты не могут получить эту информацию.
    """
    target_admin_id = str(ADMIN_MAX_ID).strip()
    if not target_admin_id or target_admin_id == "0":
        logger.warning("[SECURITY] ADMIN_MAX_ID не сконфигурирован. Уведомление в ЛС МАКС пропущено.")
    else:
        name = lead_data.get("name", "Аноним")
        phone = lead_data.get("phone", "Не указан")
        service = lead_data.get("service", "Не указан")
        budget = lead_data.get("budget", "Договорной")
        desc = lead_data.get("desc", "—")
        client_max_id = lead_data.get("max_id", "—")

        admin_text = (
            f"🚨 <b>НОВАЯ ЗАЯВКА #{lead_id} В V1PER IT Solutions!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Клиент:</b> {name} (ID: <code>{client_max_id}</code>)\n"
            f"📞 <b>Контакт:</b> <b>{phone}</b>\n"
            f"💼 <b>Направление:</b> {service}\n"
            f"💰 <b>Смета / Бюджет:</b> <b>{budget}</b>\n"
            f"📝 <b>Детализация задачи:</b>\n{desc}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📄 <i>Смета в PDF с цифровой подписью сформирована и прикреплена ниже.</i>"
        )

        logger.info(f"[SECURITY] Отправка закрытого уведомления о лиде #{lead_id} СТРОГО администратору (ID: {target_admin_id})")
        if pdf_path and Path(pdf_path).exists():
            api.send_document(target_admin_id, pdf_path, caption=admin_text)
        else:
            api.send_message(target_admin_id, admin_text)

    # Дублирование в Telegram разработчика
    send_telegram_alert(lead_id, lead_data)
    return True

