"""
Comprehensive unit tests for /api/tasks CRUD endpoints.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
"""

import json
from tests.test_base import BaseMindFlowTestCase


class TestTasksEndpoints(BaseMindFlowTestCase):

    def test_get_tasks_empty(self):
        """GET /api/tasks returns empty list when no tasks exist."""
        resp = self.client.get("/api/tasks", headers=self.get_auth_headers())
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 0)

    def test_add_task_success(self):
        """POST /api/tasks successfully creates a task and returns it."""
        payload = {"text": "Write unit tests"}
        resp = self.client.post("/api/tasks", headers=self.get_auth_headers(), data=json.dumps(payload))
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data.get("status"), "success")
        task = data.get("task", {})
        self.assertEqual(task.get("text"), "Write unit tests")
        self.assertEqual(task.get("completed"), 0)

    def test_add_task_validation(self):
        """POST /api/tasks requires non-empty text."""
        resp = self.client.post("/api/tasks", headers=self.get_auth_headers(), data=json.dumps({"text": "   "}))
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn("error", data)

    def test_update_task_toggle_complete(self):
        """PUT /api/tasks updates completion status."""
        # Create task first
        add_resp = self.client.post("/api/tasks", headers=self.get_auth_headers(), data=json.dumps({"text": "Ship code"}))
        task_id = add_resp.get_json()["task"]["id"]

        # Update task to completed
        update_resp = self.client.put("/api/tasks", headers=self.get_auth_headers(), data=json.dumps({"id": task_id, "completed": 1}))
        self.assertEqual(update_resp.status_code, 200)
        self.assertEqual(update_resp.get_json().get("status"), "success")

        # Verify through GET
        get_resp = self.client.get("/api/tasks", headers=self.get_auth_headers())
        tasks = get_resp.get_json()
        updated_task = next((t for t in tasks if t["id"] == task_id), None)
        self.assertIsNotNone(updated_task)
        self.assertEqual(updated_task["completed"], 1)

    def test_delete_task_success(self):
        """DELETE /api/tasks removes the task."""
        add_resp = self.client.post("/api/tasks", headers=self.get_auth_headers(), data=json.dumps({"text": "Temporary Task"}))
        task_id = add_resp.get_json()["task"]["id"]

        del_resp = self.client.delete(f"/api/tasks?id={task_id}", headers=self.get_auth_headers())
        self.assertEqual(del_resp.status_code, 200)
        data = del_resp.get_json()
        self.assertEqual(data.get("status"), "success")

        # Verify task is gone
        get_resp = self.client.get("/api/tasks", headers=self.get_auth_headers())
        self.assertEqual(len(get_resp.get_json()), 0)

    def test_tasks_auth_required(self):
        """Endpoints enforce @require_api_token."""
        resp = self.client.get("/api/tasks")
        self.assertEqual(resp.status_code, 401)

        resp_post = self.client.post("/api/tasks", data=json.dumps({"text": "No Auth"}))
        self.assertEqual(resp_post.status_code, 401)
