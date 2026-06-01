from pathlib import Path


SUBMIT_VIEW = Path(__file__).resolve().parents[1] / "web" / "src" / "views" / "ticket" / "submit" / "index.vue"


def test_company_name_note_is_below_input():
    source = SUBMIT_VIEW.read_text(encoding="utf-8")

    assert '<div class="field-stack">' in source
    assert '<NInput v-model:value="form.company_name" placeholder="请输入客户公司名称" />' in source
    assert '<div class="field-note">备注：请填写客户公司名称，不是自己公司。</div>' in source
    assert ".field-stack {\n  width: 100%;" in source
    assert "flex-direction: column;" in source
