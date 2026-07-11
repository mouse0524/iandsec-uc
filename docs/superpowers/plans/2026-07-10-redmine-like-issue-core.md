# Redmine-like Issue Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first Redmine-like Issue core: configurable tracker/status/priority/workflow models, journal history, and a tested unified issue update service.

**Architecture:** Keep the existing `Ticket` table as the Issue storage surface for now, and add Redmine-like configuration/history tables around it. Existing role-specific ticket APIs remain untouched in this phase; new code is additive and testable through service-level tests.

**Tech Stack:** FastAPI, Tortoise ORM, Aerich-style manual migrations, pytest, PowerShell on Windows.

---

## File Structure

- Modify: `app/models/enums.py`
  - Add small string enums for custom field formats, workflow field rules, relation types, version status, version sharing, and time entry activity status.
- Modify: `app/models/admin.py`
  - Add Redmine-like models: `ProjectMember`, `IssueTracker`, `IssueStatus`, `IssuePriority`, `IssueCategory`, `IssueVersion`, `IssueCustomField`, `IssueCustomFieldBinding`, `IssueCustomValue`, `IssueWorkflowTransition`, `IssueWorkflowPermission`, `IssueWatcher`, `IssueRelation`, `IssueTimeEntry`, `IssueJournal`, `IssueJournalDetail`, `IssueQuery`.
  - Add nullable Issue fields to `Ticket` for tracker/status/priority/category/version/parent/root/assigned fields.
- Create: `migrations/models/30_20260710210000_add_issue_core.py`
  - Add the new tables and nullable `ticket` columns.
- Create: `app/controllers/issue.py`
  - Implement transition lookup and unified issue update with journal detail recording.
- Create: `tests/test_issue_core.py`
  - Service-level tests using simple async fakes first, then model import/compile checks.
- Modify: `.gitignore`
  - Allow `tests/test_issue_core.py` to be tracked.

## Task 1: Redmine-like Enums And Models

**Files:**
- Modify: `app/models/enums.py`
- Modify: `app/models/admin.py`
- Test: `tests/test_issue_core.py`

- [ ] **Step 1: Write the failing model import test**

```python
def test_issue_core_models_are_importable():
    from app.models.admin import (
        IssueCustomField,
        IssueJournal,
        IssueJournalDetail,
        IssuePriority,
        IssueStatus,
        IssueTracker,
        IssueWorkflowPermission,
        IssueWorkflowTransition,
        Ticket,
    )

    assert IssueTracker.Meta.table == "issue_tracker"
    assert IssueStatus.Meta.table == "issue_status"
    assert IssuePriority.Meta.table == "issue_priority"
    assert IssueWorkflowTransition.Meta.table == "issue_workflow_transition"
    assert IssueWorkflowPermission.Meta.table == "issue_workflow_permission"
    assert IssueJournal.Meta.table == "issue_journal"
    assert IssueJournalDetail.Meta.table == "issue_journal_detail"
    assert Ticket._meta.fields_map["issue_tracker_id"].null is True
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `python -m pytest -q tests/test_issue_core.py::test_issue_core_models_are_importable --basetemp .pytest-tmp`

Expected: FAIL because `tests/test_issue_core.py` or the new models do not exist.

- [ ] **Step 3: Add minimal enums and models**

Implement only the fields listed in the design doc that are needed for storage and service logic. Keep names prefixed with `Issue` to avoid colliding with existing `Project`/`Ticket` names.

- [ ] **Step 4: Re-run the model import test**

Run: `python -m pytest -q tests/test_issue_core.py::test_issue_core_models_are_importable --basetemp .pytest-tmp`

Expected: PASS.

## Task 2: Manual Migration

**Files:**
- Create: `migrations/models/30_20260710210000_add_issue_core.py`

- [ ] **Step 1: Write migration compile check expectation**

Run: `python -m py_compile migrations\models\30_20260710210000_add_issue_core.py`

Expected before file exists: FAIL with file-not-found.

- [ ] **Step 2: Add the migration**

Create a migration that:

- Adds nullable Redmine-like columns to `ticket`.
- Creates all new Issue core tables with `CREATE TABLE IF NOT EXISTS`.
- Adds indexes for common filters: tracker/status/priority/project/assigned/author/category/version.
- Drops new tables and columns on downgrade.

- [ ] **Step 3: Re-run migration compile check**

Run: `python -m py_compile migrations\models\30_20260710210000_add_issue_core.py`

Expected: PASS.

## Task 3: Workflow Transition Lookup

**Files:**
- Create: `app/controllers/issue.py`
- Test: `tests/test_issue_core.py`

- [ ] **Step 1: Write the failing transition test**

```python
import pytest

from app.controllers.issue import IssueWorkflowService


@pytest.mark.anyio
async def test_transition_options_follow_role_tracker_and_current_status():
    transitions = [
        {"role_id": 1, "tracker_id": 10, "old_status_id": 20, "new_status_id": 30},
        {"role_id": 2, "tracker_id": 10, "old_status_id": 20, "new_status_id": 40},
        {"role_id": 1, "tracker_id": 11, "old_status_id": 20, "new_status_id": 50},
    ]

    service = IssueWorkflowService(transition_reader=lambda **kwargs: transitions)

    result = await service.allowed_status_ids(role_ids=[1], tracker_id=10, status_id=20)

    assert result == [30]
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `python -m pytest -q tests/test_issue_core.py::test_transition_options_follow_role_tracker_and_current_status --basetemp .pytest-tmp`

Expected: FAIL because `IssueWorkflowService` does not exist.

- [ ] **Step 3: Implement minimal transition lookup**

Implement `IssueWorkflowService.allowed_status_ids(role_ids, tracker_id, status_id)` so it filters transitions by role, tracker, and old status, preserving order and de-duplicating status IDs.

- [ ] **Step 4: Re-run the test**

Run: `python -m pytest -q tests/test_issue_core.py::test_transition_options_follow_role_tracker_and_current_status --basetemp .pytest-tmp`

Expected: PASS.

## Task 4: Unified Issue Update And Journal Details

**Files:**
- Modify: `app/controllers/issue.py`
- Test: `tests/test_issue_core.py`

- [ ] **Step 1: Write the failing journal test**

```python
import pytest

from app.controllers.issue import IssueUpdateService


class FakeIssue:
    id = 7
    issue_status_id = 20
    assigned_to_id = None
    priority_id = 1

    async def save(self):
        self.saved = True


@pytest.mark.anyio
async def test_update_issue_records_changed_fields_as_journal_details():
    issue = FakeIssue()
    journals = []
    details = []

    service = IssueUpdateService(
        issue_getter=lambda issue_id: issue,
        journal_writer=lambda **kwargs: journals.append(kwargs) or {"id": 99},
        detail_writer=lambda **kwargs: details.append(kwargs),
        workflow_service=None,
    )

    updated = await service.update_issue(
        issue_id=7,
        user_id=3,
        role_ids=[1],
        changes={"issue_status_id": 30, "assigned_to_id": 4},
        notes="推进处理",
    )

    assert updated.issue_status_id == 30
    assert updated.assigned_to_id == 4
    assert journals[0]["notes"] == "推进处理"
    assert details == [
        {"journal_id": 99, "property": "attr", "prop_key": "issue_status_id", "old_value": "20", "value": "30"},
        {"journal_id": 99, "property": "attr", "prop_key": "assigned_to_id", "old_value": "", "value": "4"},
    ]
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `python -m pytest -q tests/test_issue_core.py::test_update_issue_records_changed_fields_as_journal_details --basetemp .pytest-tmp`

Expected: FAIL because `IssueUpdateService` does not exist or cannot record details.

- [ ] **Step 3: Implement minimal update service**

Implement `IssueUpdateService.update_issue(...)` to:

- Load the issue.
- Validate requested status transition when `workflow_service` is provided.
- Apply changed standard fields.
- Save the issue.
- Create one journal row.
- Create one journal detail row per changed field.
- Skip unchanged fields.

- [ ] **Step 4: Re-run the journal test**

Run: `python -m pytest -q tests/test_issue_core.py::test_update_issue_records_changed_fields_as_journal_details --basetemp .pytest-tmp`

Expected: PASS.

## Task 5: Phase 1 Verification

**Files:**
- All Phase 1 files.

- [ ] **Step 1: Run focused tests**

Run: `python -m pytest -q tests/test_issue_core.py --basetemp .pytest-tmp`

Expected: all tests in `test_issue_core.py` pass.

- [ ] **Step 2: Run compile check**

Run: `python -m compileall app`

Expected: compile succeeds.

- [ ] **Step 3: Run diff whitespace check**

Run: `git diff --check`

Expected: no whitespace errors; CRLF warnings are acceptable on this Windows checkout.

- [ ] **Step 4: Update status**

Report that Phase 1 Redmine-like Issue core is implemented, while frontend Redmine-like screens and migration of old `RdTask` flow remain for later phases.
