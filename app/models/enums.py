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
    FIELD_VERIFY = "field_verify"
    FIELD_REJECT = "field_reject"
    TECH_REJECT = "tech_reject"
    FINISH = "finish"
    CLOSE = "close"


class PartnerRegisterStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class RegisterType(StrEnum):
    CHANNEL = "channel"
    USER = "user"


class PartnerLevel(StrEnum):
    REGIONAL = "区域代理"
    DIAMOND = "钻石"
    PLATINUM = "铂金"
    GOLD = "金牌"
    UNSIGNED = "未签约"

