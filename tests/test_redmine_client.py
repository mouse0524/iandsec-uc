from __future__ import annotations

import time
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from redminelib.exceptions import AuthError

from app.services.redmine_client import RedmineClient, RedmineConfig


class FakeIssueResource:
    def __init__(self):
        self.calls = []

    def filter(self, **params):
        self.calls.append(("filter", params))
        return [{"id": 1, "subject": "Demo"}]

    def get(self, issue_id, **params):
        self.calls.append(("get", issue_id, params))
        return {"id": issue_id, "include": params.get("include")}

    def create(self, **payload):
        self.calls.append(("create", payload))
        return {"id": 123, **payload}

    def update(self, issue_id, **payload):
        self.calls.append(("update", issue_id, payload))
        return True


class FakeListResource:
    def __init__(self, items):
        self.items = items
        self.calls = []

    def all(self):
        self.calls.append(("all",))
        return self.items

    def filter(self, **params):
        self.calls.append(("filter", params))
        return self.items


class FakeRedmine:
    def __init__(self, base_url, key, requests):
        self.base_url = base_url
        self.key = key
        self.requests = requests
        self.issue = FakeIssueResource()
        self.project = FakeListResource([SimpleNamespace(id=1, identifier="demo", name="Demo")])
        self.tracker = FakeListResource([SimpleNamespace(id=8, name="现网问题")])
        self.enumeration = FakeListResource([SimpleNamespace(id=2, name="一般")])
        self.user = FakeListResource([SimpleNamespace(id=7, login="tech", firstname="Tech", lastname="User")])
        self.custom_field = FakeListResource([SimpleNamespace(id=11, name="项目阶段")])
        self.upload_calls = []
        self.download_calls = []

    def upload(self, payload, **kwargs):
        self.upload_calls.append((payload.read(), getattr(payload, "name", ""), kwargs))
        return SimpleNamespace(token="token-1")

    def download(self, url, **kwargs):
        self.download_calls.append((url, kwargs))
        return SimpleNamespace(content=b"image-bytes")


def fake_factory_holder():
    instances = []

    def factory(*args, **kwargs):
        instance = FakeRedmine(*args, **kwargs)
        instances.append(instance)
        return instance

    return instances, factory


@pytest.mark.anyio
async def test_create_issue_uses_python_redmine_with_api_key():
    instances, factory = fake_factory_holder()
    client = RedmineClient(RedmineConfig("https://redmine.example.com/", "secret-key"), redmine_factory=factory)

    result = await client.create_issue({"project_id": 1, "subject": "Demo", "tracker_id": None})

    assert result == {"id": 123, "project_id": 1, "subject": "Demo"}
    assert instances[0].base_url == "https://redmine.example.com"
    assert instances[0].key == "secret-key"
    assert instances[0].requests == {"timeout": 30.0}
    assert instances[0].issue.calls == [("create", {"project_id": 1, "subject": "Demo"})]


@pytest.mark.anyio
async def test_add_issue_note_updates_issue_notes():
    instances, factory = fake_factory_holder()
    client = RedmineClient({"redmine_base_url": "https://redmine.example.com", "redmine_api_key": "secret-key"}, redmine_factory=factory)

    result = await client.add_issue_note(123, "done")

    assert result is True
    assert instances[0].issue.calls == [("update", 123, {"notes": "done"})]


@pytest.mark.anyio
async def test_upload_returns_upload_token():
    instances, factory = fake_factory_holder()
    client = RedmineClient(RedmineConfig("https://redmine.example.com", "secret-key"), redmine_factory=factory)

    token = await client.upload("a b.txt", b"hello", content_type="text/plain")

    assert token == "token-1"
    assert instances[0].upload_calls == [(b"hello", "a b.txt", {"filename": "a b.txt"})]


@pytest.mark.anyio
async def test_download_attachment_uses_content_url():
    instances, factory = fake_factory_holder()
    client = RedmineClient(RedmineConfig("https://redmine.example.com", "secret-key"), redmine_factory=factory)

    content = await client.download_attachment(SimpleNamespace(content_url="https://redmine.example.com/attachments/1/image.png"))

    assert content == b"image-bytes"
    assert instances[0].download_calls == [("https://redmine.example.com/attachments/1/image.png", {})]


@pytest.mark.anyio
async def test_metadata_resources_are_listed():
    instances, factory = fake_factory_holder()
    client = RedmineClient(RedmineConfig("https://redmine.example.com", "secret-key"), redmine_factory=factory)

    projects = await client.list_projects()
    trackers = await client.list_trackers()
    priorities = await client.list_issue_priorities()
    users = await client.list_users()
    custom_fields = await client.list_custom_fields()

    assert projects[0].identifier == "demo"
    assert trackers[0].id == 8
    assert priorities[0].name == "一般"
    assert users[0].login == "tech"
    assert custom_fields[0].name == "项目阶段"
    assert instances[0].project.calls == [("all",)]
    assert instances[1].tracker.calls == [("all",)]
    assert instances[2].enumeration.calls == [("filter", {"resource": "issue_priorities"})]
    assert instances[3].user.calls == [("all",)]
    assert instances[4].custom_field.calls == [("all",)]


@pytest.mark.anyio
async def test_redmine_auth_error_reports_api_key_error():
    class FailingIssueResource:
        def filter(self, **params):
            raise AuthError

    class FailingRedmine(FakeRedmine):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.issue = FailingIssueResource()

    client = RedmineClient(RedmineConfig("https://redmine.example.com", "bad-key"), redmine_factory=FailingRedmine)

    with pytest.raises(HTTPException) as exc_info:
        await client.list_issues(status_id="*")

    assert exc_info.value.status_code == 502
    assert "API Key" in str(exc_info.value.detail)


@pytest.mark.anyio
async def test_python_redmine_calls_are_wrapped_in_thread():
    def factory(*args, **kwargs):
        class SlowIssueResource:
            def filter(self, **params):
                time.sleep(0.05)
                return []

        return SimpleNamespace(issue=SlowIssueResource())

    client = RedmineClient(RedmineConfig("https://redmine.example.com", "secret-key"), redmine_factory=factory)

    started = time.perf_counter()
    result = await client.list_issues(status_id="*")

    assert result == []
    assert time.perf_counter() - started >= 0.05
