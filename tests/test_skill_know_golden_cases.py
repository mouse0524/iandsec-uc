from app.services.skill_know.golden_case_service import DEFAULT_GOLDEN_CASES


def test_default_golden_cases_are_readable_chinese():
    questions = [item["question"] for item in DEFAULT_GOLDEN_CASES]

    assert "落地解密在哪里配置" in questions
    assert "U 盘客户端导出 key 在哪里" in questions
    assert all("锟" not in item["question"] for item in DEFAULT_GOLDEN_CASES)
    assert all("�" not in item["question"] for item in DEFAULT_GOLDEN_CASES)
    assert all("锟" not in str(item.get("expected_heading_contains", "")) for item in DEFAULT_GOLDEN_CASES)
