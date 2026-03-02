"""HTTP client for the CDE API.

Wraps all CDE endpoints used by the agent pipeline.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

CDE_BASE_URL = os.getenv("CDE_API_URL", "http://localhost:8000")


class CDEClient:
    """Synchronous HTTP client for the CDE PoC API."""

    def __init__(self, base_url: str = CDE_BASE_URL):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self.base_url, timeout=30.0, follow_redirects=True
        )

    # -- Projects --

    def create_project(self, name: str, description: str = "") -> dict:
        """POST /projects"""
        resp = self._client.post(
            "/projects",
            json={"name": name, "description": description},
        )
        resp.raise_for_status()
        return resp.json()

    def list_projects(self) -> list[dict]:
        """GET /projects"""
        resp = self._client.get("/projects")
        resp.raise_for_status()
        return resp.json()

    def add_member(
        self, project_id: str, name: str, role: str, organization: str = ""
    ) -> dict:
        """POST /projects/{id}/members"""
        resp = self._client.post(
            f"/projects/{project_id}/members",
            json={"name": name, "role": role, "organization": organization},
        )
        resp.raise_for_status()
        return resp.json()

    def list_members(self, project_id: str) -> list[dict]:
        """GET /projects/{project_id}/members"""
        resp = self._client.get(f"/projects/{project_id}/members")
        resp.raise_for_status()
        return resp.json()

    # -- Containers --

    def create_container(
        self,
        project_id: str,
        name: str,
        container_type: str,
        description: str = "",
        created_by: str = "Agent",
    ) -> dict:
        """POST /projects/{project_id}/containers"""
        resp = self._client.post(
            f"/projects/{project_id}/containers",
            json={
                "name": name,
                "container_type": container_type,
                "created_by": created_by,
            },
        )
        resp.raise_for_status()
        return resp.json()

    def list_containers(self, project_id: str) -> list[dict]:
        """GET /projects/{project_id}/containers"""
        resp = self._client.get(f"/projects/{project_id}/containers")
        resp.raise_for_status()
        return resp.json()

    def get_container(self, container_id: str) -> dict:
        """GET /containers/{id}"""
        resp = self._client.get(f"/containers/{container_id}")
        resp.raise_for_status()
        return resp.json()

    def upload_revision(
        self,
        container_id: str,
        file_path: Path,
        uploader_name: str = "Agent",
    ) -> dict:
        """POST /containers/{id}/revisions"""
        with open(file_path, "rb") as f:
            resp = self._client.post(
                f"/containers/{container_id}/revisions",
                files={"file": (file_path.name, f)},
                data={"uploaded_by": uploader_name},
            )
        resp.raise_for_status()
        return resp.json()

    def download_revision(
        self,
        container_id: str,
        revision_number: int = 1,
    ) -> Path:
        """GET /containers/{id}/revisions/{rev}/download

        Downloads the file to a temp directory and returns the local path.
        """
        resp = self._client.get(
            f"/containers/{container_id}/revisions/{revision_number}/download"
        )
        resp.raise_for_status()

        # Extract filename from Content-Disposition header or use a default
        content_disp = resp.headers.get("content-disposition", "")
        if "filename=" in content_disp:
            filename = content_disp.split("filename=")[-1].strip('"').strip("'")
        else:
            filename = f"revision_{revision_number}"

        # Save to a temp directory that persists
        download_dir = Path(tempfile.gettempdir()) / "cde_downloads"
        download_dir.mkdir(parents=True, exist_ok=True)
        file_path = download_dir / f"{container_id}_rev{revision_number}_{filename}"
        file_path.write_bytes(resp.content)
        return file_path

    def create_container_with_content(
        self,
        project_id: str,
        name: str,
        container_type: str,
        content: dict[str, Any],
        description: str = "",
        uploader_name: str = "Agent",
    ) -> dict:
        """Create a container and upload JSON content as its first revision.

        Used by agents to store reports, quantity reports, and estimates.
        """
        container = self.create_container(
            project_id, name, container_type, description
        )
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as tmp:
            json.dump(content, tmp, ensure_ascii=False, indent=2)
            tmp_path = Path(tmp.name)

        try:
            self.upload_revision(container["id"], tmp_path, uploader_name)
        finally:
            tmp_path.unlink(missing_ok=True)

        return container

    # -- Transitions --

    def request_transition(
        self,
        container_id: str,
        to_state: str,
        requester_name: str,
        justification: str = "",
        suitability_code: str | None = None,
    ) -> dict:
        """POST /containers/{id}/transitions"""
        payload: dict[str, Any] = {
            "to_state": to_state,
            "requested_by": requester_name,
            "justification": justification,
        }
        if suitability_code:
            payload["suitability_code"] = suitability_code
        resp = self._client.post(
            f"/containers/{container_id}/transitions", json=payload
        )
        resp.raise_for_status()
        return resp.json()

    def approve_transition(
        self, transition_id: str, approver_name: str
    ) -> dict:
        """POST /transitions/{id}/approve"""
        resp = self._client.post(
            f"/transitions/{transition_id}/approve",
            json={"approved_by": approver_name},
        )
        resp.raise_for_status()
        return resp.json()

    # -- Audit --

    def list_audit(self, project_id: str) -> list[dict]:
        """GET /projects/{project_id}/audit"""
        resp = self._client.get(f"/projects/{project_id}/audit")
        resp.raise_for_status()
        return resp.json()

    def close(self) -> None:
        self._client.close()
