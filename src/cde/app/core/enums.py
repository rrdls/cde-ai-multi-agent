"""Enumerations for the CDE domain model, based on ISO 19650 concepts."""

from enum import Enum


class ContainerState(str, Enum):
    """ISO 19650 information container governance states.

    Defined in ISO 19650-1:2018, Clause 12.1.
    """

    WIP = "wip"
    SHARED = "shared"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ContainerType(str, Enum):
    """Types of information containers managed by the CDE."""

    IFC_MODEL = "ifc_model"
    DOCUMENT = "document"
    SPREADSHEET = "spreadsheet"
    REPORT = "report"
    COST_ESTIMATE = "cost_estimate"


class SuitabilityCode(str, Enum):
    """ISO 19650 suitability codes (status codes).

    Defined in ISO 19650-1:2018, Table 1.

    S0: Work in Progress
    S1: Suitable for Coordination
    S2: Suitable for Information
    S3: Suitable for Review and Comment
    S4: Suitable for Stage Approval
    """

    S0 = "S0"
    S1 = "S1"
    S2 = "S2"
    S3 = "S3"
    S4 = "S4"


class MemberRole(str, Enum):
    """Simplified ISO 19650 organizational roles.

    Based on ISO 19650-2:2018, Clause 5.
    """

    APPOINTING_PARTY = "appointing_party"
    LEAD_APPOINTED = "lead_appointed"
    TASK_TEAM = "task_team"


class TransitionStatus(str, Enum):
    """Status of a state transition request."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class AuditAction(str, Enum):
    """Auditable actions in the CDE."""

    CONTAINER_CREATED = "container_created"
    REVISION_UPLOADED = "revision_uploaded"
    TRANSITION_REQUESTED = "transition_requested"
    TRANSITION_APPROVED = "transition_approved"
    TRANSITION_REJECTED = "transition_rejected"
    MEMBER_ADDED = "member_added"
    MEMBER_REMOVED = "member_removed"
    PROJECT_CREATED = "project_created"
