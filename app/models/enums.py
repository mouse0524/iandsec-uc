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
    TECH_REJECTED = "tech_rejected"
    DONE = "done"


class TicketActionType(StrEnum):
    SUBMIT = "submit"
    RESUBMIT = "resubmit"
    CS_APPROVE = "cs_approve"
    CS_REJECT = "cs_reject"
    TECH_START = "tech_start"
    TECH_REJECT = "tech_reject"
    FINISH = "finish"


class PartnerRegisterStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class RegisterType(StrEnum):
    CHANNEL = "channel"
    USER = "user"


class SkillKnowDocumentStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class SkillKnowPromptCategory(StrEnum):
    SYSTEM = "system"
    CHAT = "chat"
    SKILL = "skill"
    CLASSIFICATION = "classification"
    SEARCH = "search"


class SkillKnowMessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class SkillKnowLearningStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    INDEXED = "indexed"
