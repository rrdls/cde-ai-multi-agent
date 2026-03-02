"""Integration test for the full CDE container lifecycle.

Tests the ISO 19650 governance workflow:
Create Project -> Add Member -> Create Container (WIP)
-> Upload Revision -> Request Transition (WIP->Shared)
-> Approve Transition -> Verify State -> Full Lifecycle
"""

import pytest
import httpx
import os

BASE_URL = os.getenv("CDE_BASE_URL", "http://localhost:8000")


@pytest.fixture
def client():
    """Synchronous HTTP client for integration tests."""
    with httpx.Client(base_url=BASE_URL, timeout=10) as c:
        yield c


@pytest.fixture
def project(client):
    """Create a test project."""
    r = client.post("/projects", json={
        "name": "Test Project",
        "description": "Integration test project",
    })
    assert r.status_code == 201
    return r.json()


@pytest.fixture
def member(client, project):
    """Add a task_team member to the test project."""
    r = client.post(f"/projects/{project['id']}/members", json={
        "name": "Test Engineer",
        "role": "task_team",
    })
    assert r.status_code == 201
    return r.json()


@pytest.fixture
def container(client, project):
    """Create an IFC container in WIP state."""
    r = client.post(f"/projects/{project['id']}/containers", json={
        "name": "test-model.ifc",
        "container_type": "ifc_model",
        "created_by": "Test Engineer",
    })
    assert r.status_code == 201
    return r.json()


class TestFullContainerLifecycle:
    """Test the complete WIP -> Shared -> Published -> Archived lifecycle."""

    def test_create_upload_transition_approve(self, client, project, member, container):
        container_id = container["id"]

        assert container["current_state"] == "wip"

        r = client.post(
            f"/containers/{container_id}/revisions",
            files={"file": ("model.ifc", b"IFC content here", "application/octet-stream")},
            data={"uploaded_by": "Test Engineer", "description": "Initial version"},
        )
        assert r.status_code == 201
        assert r.json()["revision_number"] == 1

        r = client.post(f"/containers/{container_id}/transitions", json={
            "to_state": "shared",
            "suitability_code": "S1",
            "requested_by": "Test Engineer",
            "justification": "Ready for coordination",
        })
        assert r.status_code == 201
        assert r.json()["status"] == "pending"
        transition_id = r.json()["id"]

        r = client.post(f"/transitions/{transition_id}/approve", json={
            "approved_by": "Project Coordinator",
        })
        assert r.status_code == 200
        assert r.json()["status"] == "approved"

        r = client.get(f"/containers/{container_id}")
        assert r.json()["current_state"] == "shared"
        assert r.json()["suitability_code"] == "S1"

        r = client.post(f"/containers/{container_id}/transitions", json={
            "to_state": "published",
            "requested_by": "Project Coordinator",
            "justification": "Approved for use",
        })
        assert r.status_code == 201
        t2_id = r.json()["id"]

        r = client.post(f"/transitions/{t2_id}/approve", json={
            "approved_by": "Client Representative",
        })
        assert r.status_code == 200

        r = client.get(f"/containers/{container_id}")
        assert r.json()["current_state"] == "published"

        r = client.post(f"/containers/{container_id}/transitions", json={
            "to_state": "archived",
            "requested_by": "Project Coordinator",
            "justification": "Superseded by v2",
        })
        assert r.status_code == 201
        t3_id = r.json()["id"]
        client.post(f"/transitions/{t3_id}/approve", json={
            "approved_by": "Project Coordinator",
        })

        r = client.get(f"/containers/{container_id}")
        assert r.json()["current_state"] == "archived"


class TestGovernanceRules:
    """Test that ISO 19650 governance rules are enforced."""

    def test_suitability_required_for_shared(self, client, container):
        r = client.post(f"/containers/{container['id']}/transitions", json={
            "to_state": "shared",
            "requested_by": "Test Engineer",
        })
        assert r.status_code == 422
        assert "suitability code" in r.json()["detail"].lower()

    def test_invalid_transition_wip_to_published(self, client, container):
        r = client.post(f"/containers/{container['id']}/transitions", json={
            "to_state": "published",
            "requested_by": "Test Engineer",
        })
        assert r.status_code == 422
        assert "Invalid transition" in r.json()["detail"]

    def test_upload_blocked_in_non_wip(self, client, container):
        cid = container["id"]

        r = client.post(f"/containers/{cid}/transitions", json={
            "to_state": "shared",
            "suitability_code": "S1",
            "requested_by": "Test Engineer",
            "justification": "Ready",
        })
        tid = r.json()["id"]
        client.post(f"/transitions/{tid}/approve", json={"approved_by": "Coordinator"})

        r = client.post(
            f"/containers/{cid}/revisions",
            files={"file": ("v2.ifc", b"new content", "application/octet-stream")},
            data={"uploaded_by": "Test Engineer", "description": "Should fail"},
        )
        assert r.status_code == 422
        assert "WIP" in r.json()["detail"]

    def test_reject_transition(self, client, container):
        cid = container["id"]
        r = client.post(f"/containers/{cid}/transitions", json={
            "to_state": "shared",
            "suitability_code": "S2",
            "requested_by": "Test Engineer",
            "justification": "Please review",
        })
        tid = r.json()["id"]

        r = client.post(f"/transitions/{tid}/reject", json={
            "rejected_by": "Reviewer",
            "reason": "Model incomplete",
        })
        assert r.status_code == 200
        assert r.json()["status"] == "rejected"

        r = client.get(f"/containers/{cid}")
        assert r.json()["current_state"] == "wip"


class TestAuditTrail:
    """Test that all actions are properly audited."""

    def test_audit_trail_completeness(self, client, project, container):
        r = client.get(f"/projects/{project['id']}/audit")
        assert r.status_code == 200
        entries = r.json()
        actions = [e["action"] for e in entries]
        assert "project_created" in actions
        assert "container_created" in actions
