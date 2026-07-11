import pytest
from pydantic import ValidationError

from app.api.v1.tickets import tickets as tickets_api
from app.schemas.partner import PartnerRegisterIn
from app.schemas.tickets import TicketCreate, TicketUpdateIn


def ticket_payload(**overrides):
    data = {
        "company_name": "安徽繁霆信息科技有限公司",
        "contact_name": "张三",
        "email": "zhangsan@example.com",
        "phone": "13800000000",
        "project_phase": "实施",
        "issue_type": "现网问题",
        "impact_scope": "单用户",
        "category": "软件",
        "title": "标题",
        "description": "描述",
    }
    data.update(overrides)
    return data


def register_payload(**overrides):
    data = {
        "register_type": "channel",
        "company_name": "安徽繁霆信息科技有限公司",
        "contact_name": "张三",
        "email": "zhangsan@example.com",
        "phone": "13800000000",
        "password": "123456",
        "email_code": "123456",
        "invite_code": "invite",
    }
    data.update(overrides)
    return data


@pytest.mark.parametrize("model,payload", [(TicketCreate, ticket_payload), (PartnerRegisterIn, register_payload)])
def test_company_name_requires_legal_suffix(model, payload):
    with pytest.raises(ValidationError):
        model(**payload(company_name="测试公司"))


def test_ticket_update_validates_company_name():
    with pytest.raises(ValidationError):
        TicketUpdateIn(**ticket_payload(ticket_id=1, company_name="测试公司"))


@pytest.mark.parametrize(
    "company_name",
    [
        "安徽繁霆信息科技有限公司",
        "广东太力科技股份有限公司",
        "北京样例分公司",
        "上海样例合伙企业",
        "深圳样例（有限合伙）",
    ],
)
def test_company_name_accepts_supported_suffixes(company_name):
    assert TicketCreate(**ticket_payload(company_name=company_name)).company_name == company_name
    assert PartnerRegisterIn(**register_payload(company_name=company_name)).company_name == company_name


def test_ticket_required_error_rejects_empty_rich_text_description():
    payload = TicketCreate(**ticket_payload(description="<p><br></p>"))

    assert tickets_api._ticket_required_error(payload) == "问题描述不能为空"


def test_ticket_required_error_uses_issue_field_label():
    payload = TicketCreate(**ticket_payload(category=""))

    assert tickets_api._ticket_required_error(payload) == "问题分类不能为空"
