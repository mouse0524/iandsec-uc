from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUBMIT_VIEW = ROOT / "web" / "src" / "views" / "ticket" / "submit" / "index.vue"
MY_VIEW = ROOT / "web" / "src" / "views" / "ticket" / "my" / "index.vue"
REVIEW_VIEW = ROOT / "web" / "src" / "views" / "ticket" / "review" / "index.vue"
TECH_VIEW = ROOT / "web" / "src" / "views" / "ticket" / "tech" / "index.vue"
DETAIL_VIEW = ROOT / "web" / "src" / "views" / "ticket" / "components" / "TicketDetailModal.vue"
SETTINGS_VIEW = ROOT / "web" / "src" / "views" / "system" / "settings" / "index.vue"
WORKBENCH_VIEW = ROOT / "web" / "src" / "views" / "workbench" / "index.vue"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_ticket_tracking_and_impact_scope_fields_are_visible_in_frontend():
    submit = read(SUBMIT_VIEW)
    my = read(MY_VIEW)
    review = read(REVIEW_VIEW)
    tech = read(TECH_VIEW)
    detail = read(DETAIL_VIEW)
    settings = read(SETTINGS_VIEW)

    assert "impact_scope: ''" in submit
    assert 'label="影响范围"' in submit
    assert 'v-model:value="form.impact_scope"' in submit
    assert 'label="跟踪"' in submit
    assert "现网问题" in submit
    assert "现网需求" in submit
    assert "产品建议" in submit

    for source in [my, review, tech]:
        assert "impactScopeOptions" in source
        assert "impact_scope" in source
        assert "title: '影响范围'" in source
        assert "title: '跟踪'" in source

    assert 'label="影响范围"' in my
    assert 'v-model:value="editForm.impact_scope"' in my
    assert 'label="跟踪"' in my

    assert "<span>影响范围</span>" in detail
    assert "{{ ticket.impact_scope || '-' }}" in detail
    assert "<span>跟踪</span>" in detail

    assert "ticket_impact_scopes" in settings
    assert 'label="影响范围"' in settings
    assert 'label="跟踪"' in settings


def test_ticket_submit_redirects_to_my_ticket_without_status_filter():
    submit = read(SUBMIT_VIEW)

    assert "router.push({ path: '/ticket/my' })" in submit
    assert "router.push({ path: '/ticket/my', query: { status: 'pending_review' } })" not in submit


def test_workbench_done_ticket_entry_keeps_my_ticket_status_visible():
    workbench = read(WORKBENCH_VIEW)
    my = read(MY_VIEW)

    assert "ticket_done: 'done'" in workbench
    assert "ticket_today_done: 'done'" in workbench
    assert "watch(" in my
    assert "route.query.status" in my
