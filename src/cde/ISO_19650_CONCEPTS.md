# ISO 19650 Concepts Used in the CDE PoC

This document maps every ISO 19650 concept implemented in the CDE PoC to its normative source.

---

## Core Concepts

### 1. Information Container (ISO 19650-1:2018, Clause 3.3.8)

> **Definition:** Named persistent set of information retrievable from within a file, system, or application storage hierarchy.

**Implementation:** The `InformationContainer` model. Each IFC model, PDF document, spreadsheet, or report is an individual information container with its own identity, metadata, and governance lifecycle.

**Normative Source:** ISO 19650-1:2018, Clause 3.3.8

---

### 2. Information States (ISO 19650-1:2018, Clause 12.1)

> **Definition:** The four states that govern the lifecycle of information containers within a CDE.

| State | ISO Definition | PoC Behavior |
|-------|---------------|--------------|
| **Work in Progress (WIP)** | Information being developed by the task team | Default state on creation. Only state that accepts new file revisions. |
| **Shared** | Information released for coordination | Requires a Suitability Code. Upload of new revisions is blocked. |
| **Published** | Information approved for its intended purpose | Transition requires approval chain. |
| **Archived** | Superseded information retained for audit | Terminal state. No further transitions allowed. |

**Normative Source:** ISO 19650-1:2018, Clause 12.1 and Figure 6

---

### 3. Suitability Code / Status (ISO 19650-1:2018, Table 1)

> **Definition:** Metadata indicating the purpose for which shared information may be used.

| Code | Meaning |
|------|---------|
| S0 | Work in Progress (initial) |
| S1 | Suitable for Coordination |
| S2 | Suitable for Information |
| S3 | Suitable for Review and Comment |
| S4 | Suitable for Stage Approval |

**Implementation:** The `suitability_code` field on `InformationContainer` and `StateTransition`. A suitability code is **mandatory** when requesting a WIP-to-Shared transition. This ensures every shared container explicitly declares its intended purpose.

**Normative Source:** ISO 19650-1:2018, Table 1

---

### 4. State Transitions and Human Approval (ISO 19650-2:2018, Clause 5.6)

> **Principle:** State transitions constitute governance decisions that require human accountability.

**Implementation:** The two-step `StateTransition` model:
1. **Request:** An actor proposes a transition with justification.
2. **Approve/Reject:** A different (or same, for internal reviews) actor approves or rejects.

The CDE **never** autonomously changes a container's state. This preserves the ISO 19650 requirement that governance decisions carry human accountability and traceability.

**Normative Source:** ISO 19650-2:2018, Clause 5.6 (Information model delivery planning)

---

### 5. Revision Management (ISO 19650-1:2018, Clause 12.2)

> **Principle:** Information containers evolve through revisions within the WIP state.

**Implementation:** The `ContainerRevision` model stores each version of a file with:
- Sequential revision numbers
- SHA-256 integrity hash
- Original filename and file size
- Upload timestamp and actor

New revisions can **only** be uploaded when the container is in WIP state. Once shared, the content is frozen for coordination purposes.

**Normative Source:** ISO 19650-1:2018, Clause 12.2

---

### 6. Audit Trail (ISO 19650-1:2018, Clause 11)

> **Principle:** All significant events must be recorded for traceability and accountability.

**Implementation:** The `AuditLog` model records every action:
- Container creation, revision uploads
- Transition requests, approvals, and rejections
- Member additions and removals
- Project creation

Entries are **immutable** (append-only, never modified or deleted).

**Normative Source:** ISO 19650-1:2018, Clause 11 (Security-minded approach); ISO 19650-2:2018, Clause 5.1.4

---

### 7. Organizational Roles (ISO 19650-2:2018, Clause 5)

> **Definition:** Parties involved in the information management process.

| Role | ISO 19650 Definition | PoC Behavior |
|------|---------------------|--------------|
| **Appointing Party** | Organization commissioning work (client) | Final authority for Shared-to-Published transitions |
| **Lead Appointed Party** | Main contractor or coordinator | Manages overall delivery, coordinates across task teams |
| **Task Team** | Discipline-specific team producing deliverables | Creates containers, uploads revisions, requests internal transitions |

**Implementation:** The `ProjectMember` model with a `role` enum. In this PoC, role-based authorization is simplified (not enforced at the API level), but the data model supports it for future enhancement.

**Normative Source:** ISO 19650-2:2018, Clause 5.1 through 5.3

---

## Summary of Normative Parts Referenced

| ISO Standard | Part | Clauses Used |
|--------------|------|--------------|
| **ISO 19650-1:2018** | Concepts and Principles | 3.3.8, 11, 12.1, 12.2, Table 1 |
| **ISO 19650-2:2018** | Delivery Phase | 5.1, 5.3, 5.6 |
