import html
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from packaging.version import Version

from app.controllers import mail as mail_module
from app.controllers.mail import MailController
from app.controllers.ticket import TicketController
from app.core.crud import CRUDBase
from app.services import database_backup_service as backup_module


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_mail_headers_strip_crlf_before_smtp_send(monkeypatch):
    sent_messages = []

    async def fake_setting():
        return {
            "smtp_host": "smtp.example.com",
            "smtp_port": 25,
            "smtp_sender": "sender@example.com",
            "smtp_sender_name": "System\r\nCc: injected@example.com",
            "smtp_use_ssl": False,
            "smtp_use_tls": False,
        }

    class FakeSMTP:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def login(self, *args, **kwargs):
            return None

        def sendmail(self, sender, recipients, message):
            sent_messages.append(message)

    monkeypatch.setattr(MailController, "_get_setting", staticmethod(fake_setting))
    monkeypatch.setattr(MailController, "_is_valid_email", staticmethod(lambda email: True))
    monkeypatch.setattr(mail_module.smtplib, "SMTP", FakeSMTP)

    controller = MailController()
    subject = "Ticket updated\r\nBcc: victim@example.com"

    await controller._send_email(
        to_email="user@example.com",
        subject=subject,
        content="ok",
    )

    assert sent_messages
    message = sent_messages[0]
    assert "\nBcc:" not in message
    assert "\nCc:" not in message


def test_email_code_uses_secrets_choice(monkeypatch):
    calls = []

    def fake_choice(values):
        calls.append(values)
        return "7"

    monkeypatch.setattr(mail_module, "secrets", SimpleNamespace(choice=fake_choice), raising=False)

    assert MailController._gen_code(4) == "7777"
    assert calls == ["0123456789"] * 4


def test_email_validation_does_not_probe_deliverability(monkeypatch):
    kwargs_seen = {}

    def fake_validate_email(*args, **kwargs):
        kwargs_seen.update(kwargs)
        return object()

    monkeypatch.setattr(mail_module, "validate_email", fake_validate_email)

    assert MailController._is_valid_email("user@example.com")
    assert kwargs_seen["check_deliverability"] is False


def test_ticket_rich_html_sanitizer_removes_events_css_and_encoded_javascript():
    raw_html = (
        '<p>ok</p><img src="https://example.com/a.png" '
        'onerror="alert(1)" style="background:url(javascript:alert(2))">'
        '<a href="&#x6a;avascript:alert(3)">bad</a><style>body{color:red}</style>'
    )

    cleaned = TicketController._sanitize_rich_html(raw_html)
    decoded = html.unescape(cleaned).lower()

    assert "<p>ok</p>" in cleaned
    assert "onerror" not in decoded
    assert "style=" not in decoded
    assert "javascript:" not in decoded
    assert "<style" not in decoded


def test_csp_does_not_allow_unsafe_eval():
    content = Path("deploy/security-headers.conf").read_text(encoding="utf-8")

    assert "'unsafe-eval'" not in content


def test_nginx_denies_hidden_files():
    content = Path("deploy/web.conf").read_text(encoding="utf-8")

    assert re.search(r"location\s+~\s+/\\\.", content)
    assert "deny all;" in content


@pytest.mark.anyio
async def test_webdav_upload_reuses_single_http_client(monkeypatch):
    clients = []

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.requests = []
            clients.append(self)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def request(self, method, url, **kwargs):
            self.requests.append(method)
            return SimpleNamespace(status_code=201)

        async def put(self, url, **kwargs):
            self.requests.append("PUT")
            return SimpleNamespace(status_code=201)

    monkeypatch.setattr(backup_module.httpx, "AsyncClient", FakeClient)

    service = backup_module.DatabaseBackupService()
    result = await service.upload_to_webdav(
        {
            "db_backup_webdav_base_url": "https://nas.example.com/dav",
            "db_backup_webdav_username": "u",
            "db_backup_webdav_password": "p",
            "db_backup_directory": "/backups",
        },
        "backup.sql.gz",
        b"payload",
    )

    assert result["status_code"] == 201
    assert len(clients) == 1
    assert clients[0].requests == ["MKCOL", "PUT"]


@pytest.mark.anyio
async def test_crudbase_filters_raw_dict_to_model_fields():
    class FakeModel:
        _meta = SimpleNamespace(fields={"id", "name", "roles"}, m2m_fields={"roles"})
        created = None
        existing = None

        def __init__(self, **kwargs):
            self.data = kwargs
            FakeModel.created = self

        @classmethod
        async def get(cls, id):
            return cls.existing

        def update_from_dict(self, data):
            self.updated = data
            return self

        async def save(self):
            return None

    FakeModel.existing = FakeModel(name="old")
    crud = CRUDBase(FakeModel)

    await crud.create({"id": 9, "name": "new", "roles": [1], "unknown": "drop"})
    updated = await crud.update(1, {"id": 10, "name": "updated", "roles": [2], "unknown": "drop"})

    assert FakeModel.created.data == {"name": "new"}
    assert updated.updated == {"name": "updated"}


def test_sanitizer_dependency_and_pymupdf_pin_are_current():
    requirements = Path("requirements.txt").read_text(encoding="utf-8")
    pymupdf_match = re.search(r"^PyMuPDF==(.+)$", requirements, re.MULTILINE)

    assert re.search(r"^nh3==0\.3\.5$", requirements, re.MULTILINE)
    assert pymupdf_match is not None
    assert Version(pymupdf_match.group(1)) >= Version("1.28.0")
