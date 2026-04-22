from enum import Enum


class AgentStatus(str, Enum):
    OFFLINE = "offline"
    AVAILABLE = "available"
    RINGING = "ringing"
    IN_CALL = "in_call"
    PAUSED = "paused"
    WRAP_UP = "wrap_up"

    @classmethod
    def values(cls) -> list[str]:
        return [item.value for item in cls]


class CallStatus(str, Enum):
    QUEUED = "queued"
    DIALING = "dialing"
    RINGING_CUSTOMER = "ringing_customer"
    ANSWERED = "answered"

    HUMAN = "human"
    MACHINE = "machine"

    BUSY = "busy"
    NO_ANSWER = "no_answer"
    FAILED = "failed"
    CANCELED = "canceled"

    AWAITING_OPERATOR = "awaiting_operator"
    OFFERED = "offered"
    ACCEPTED = "accepted"
    REJECTED = "rejected"

    IN_CALL = "in_call"
    COMPLETED = "completed"

    CALLBACK = "callback"

    @classmethod
    def values(cls) -> list[str]:
        return [item.value for item in cls]


class CallbackStatus(str, Enum):
    PENDING = "pending"
    RESERVED = "reserved"
    DIALING = "dialing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"

    @classmethod
    def values(cls) -> list[str]:
        return [item.value for item in cls]


class LeadQualification(str, Enum):
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    NOT_INTERESTED = "not_interested"
    CALLBACK_REQUESTED = "callback_requested"
    INVALID = "invalid"
    CONVERTED = "converted"

    @classmethod
    def values(cls) -> list[str]:
        return [item.value for item in cls]


class CallOutcome(str, Enum):
    NO_CONTACT = "no_contact"
    SALE = "sale"
    CALLBACK = "callback"
    NOT_INTERESTED = "not_interested"
    WRONG_NUMBER = "wrong_number"
    VOICEMAIL = "voicemail"
    DROPPED = "dropped"

    @classmethod
    def values(cls) -> list[str]:
        return [item.value for item in cls]