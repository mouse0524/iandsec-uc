import re

from tortoise.expressions import Q

LEGAL_COMPANY_NAME_RE = re.compile(
    r"^.+?(?:有限责任公司|有限公司|股份有限公司|股份公司|合伙企业|（有限合伙）|（特殊普通合伙）|分公司)$",
    re.IGNORECASE,
)
LEGAL_COMPANY_NAME_MESSAGE = "公司名称必须填写完整，并以有限公司、有限责任公司、股份有限公司、股份公司、合伙企业、（有限合伙）、（特殊普通合伙）或分公司结尾"


COMPANY_SUFFIXES = (
    "集团股份有限公司",
    "集团有限责任公司",
    "股份有限公司",
    "有限责任公司",
    "集团有限公司",
    "股份公司",
    "集团公司",
    "有限公司",
    "公司",
)
REGION_PREFIXES = (
    "黑龙江",
    "内蒙古",
    "北京",
    "天津",
    "上海",
    "重庆",
    "河北",
    "山西",
    "辽宁",
    "吉林",
    "江苏",
    "浙江",
    "安徽",
    "福建",
    "江西",
    "山东",
    "河南",
    "湖北",
    "湖南",
    "广东",
    "海南",
    "四川",
    "贵州",
    "云南",
    "陕西",
    "甘肃",
    "青海",
    "台湾",
    "广西",
    "西藏",
    "宁夏",
    "新疆",
    "香港",
    "澳门",
)


def validate_legal_company_name(value: str) -> str:
    name = str(value or "").strip()
    if not name:
        raise ValueError("请输入公司名称")
    if not LEGAL_COMPANY_NAME_RE.fullmatch(name):
        raise ValueError(LEGAL_COMPANY_NAME_MESSAGE)
    return name


def _strip_suffix(text: str, suffixes: tuple[str, ...]) -> str:
    for suffix in suffixes:
        if text.endswith(suffix) and len(text) > len(suffix):
            return text[: -len(suffix)]
    return text


def company_name_search_terms(company_name: str | None) -> list[str]:
    original = re.sub(r"[\s（）()·,，.。-]+", "", str(company_name or ""))
    if not original:
        return []

    terms = [original]
    base = _strip_suffix(original, COMPANY_SUFFIXES)
    terms.append(base)
    for prefix in REGION_PREFIXES:
        if base.startswith(prefix) and len(base) > len(prefix):
            base = base[len(prefix):]
            terms.append(base)
            break
    terms.append(_strip_suffix(base, ("技术",)))

    return list(dict.fromkeys(term for term in terms if term))


def company_name_search_q(company_name: str | None) -> Q:
    q = Q()
    for term in company_name_search_terms(company_name):
        item = Q(company_name__contains=term)
        q = item if not q.children and not q.filters else q | item
    return q
