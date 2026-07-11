from enum import Enum, StrEnum


class EnumBase(Enum):
    @classmethod
    def get_member_values(cls):
        return [item.value for item in cls._member_map_.values()]

    @classmethod
    def get_member_names(cls):
        return [name for name in cls._member_names_]


class MethodType(StrEnum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


class TicketStatus(StrEnum):
    PENDING_REVIEW = "pending_review"
    CS_REJECTED = "cs_rejected"
    TECH_PROCESSING = "tech_processing"
    TEST_FILTERING = "test_filtering"
    PRODUCT_EVALUATION = "product_evaluation"
    RD_PROCESSING = "rd_processing"
    TEST_VERIFICATION = "test_verification"
    FIELD_VERIFICATION = "field_verification"
    PENDING_CLOSE = "pending_close"
    TECH_REJECTED = "tech_rejected"
    DONE = "done"


class TicketActionType(StrEnum):
    SUBMIT = "submit"
    RESUBMIT = "resubmit"
    CS_APPROVE = "cs_approve"
    CS_REJECT = "cs_reject"
    TECH_START = "tech_start"
    TECH_ASSIGN = "tech_assign"
    TECH_NOTE = "tech_note"
    TEST_FILTER = "test_filter"
    PRODUCT_EVALUATE = "product_evaluate"
    RD_PROCESS = "rd_process"
    TEST_VERIFY = "test_verify"
    FIELD_VERIFY = "field_verify"
    FIELD_REJECT = "field_reject"
    TECH_REJECT = "tech_reject"
    FINISH = "finish"
    CLOSE = "close"


class IssueCustomFieldFormat(StrEnum):
    STRING = "string"
    TEXT = "text"
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    DATE = "date"
    LIST = "list"
    USER = "user"
    VERSION = "version"


class IssueWorkflowFieldRule(StrEnum):
    READONLY = "readonly"
    REQUIRED = "required"


class IssueRelationType(StrEnum):
    RELATES = "relates"
    DUPLICATES = "duplicates"
    DUPLICATED = "duplicated"
    BLOCKS = "blocks"
    BLOCKED = "blocked"
    PRECEDES = "precedes"
    FOLLOWS = "follows"
    COPIED_TO = "copied_to"
    COPIED_FROM = "copied_from"


class IssueVersionStatus(StrEnum):
    OPEN = "open"
    LOCKED = "locked"
    CLOSED = "closed"


class IssueVersionSharing(StrEnum):
    NONE = "none"
    DESCENDANTS = "descendants"
    HIERARCHY = "hierarchy"
    TREE = "tree"
    SYSTEM = "system"


class PartnerRegisterStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


LEGACY_PENDING_PARTNER_REGISTER_STATUS = "待审核"
PENDING_PARTNER_REGISTER_STATUSES = [
    PartnerRegisterStatus.PENDING,
]


class RegisterType(StrEnum):
    CHANNEL = "channel"
    USER = "user"


class PartnerLevel(StrEnum):
    REGIONAL = "区域代理"
    DIAMOND = "钻石"
    PLATINUM = "铂金"
    GOLD = "金牌"
    UNSIGNED = "未签约"


ROLE_ADMIN = "管理员"
ROLE_CUSTOMER_SERVICE = "客服"
ROLE_TECH = "技术"
ROLE_PRODUCT = "产品"
ROLE_TEST = "测试"
ROLE_RD = "研发"
ROLE_USER = "用户"
ROLE_CHANNEL = "渠道商"
ROLE_AGENT = "代理商"

