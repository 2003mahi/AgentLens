import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app

HEADERS_WS_A = {"X-API-Key": "test-key-workspace-alpha"}
HEADERS_WS_B = {"X-API-Key": "test-key-workspace-beta"}

SAMPLE_TASK = {
    "task_id": "refund_eligible_001",
    "category": "refund",
    "difficulty": "medium",
    "agent_input": {
        "user_message": "I returned order ord_1042. Please help me get my refund.",
        "authenticated_customer_id": "cust_12",
    },
    "environment_fixture": {
        "order": {
            "id": "ord_1042",
            "customer_id": "cust_12",
            "paid_amount_minor": 249900,
            "refunded_amount_minor": 0,
            "currency": "INR",
        },
        "return": {
            "received": True,
            "inspection_passed": True,
        },
    },
    "reviewer_behavior": {
        "decision": "approve",
        "applies_to": "matching_eligible_refund_proposal",
    },
    "evaluation": {
        "outcome": {
            "refund_total_minor": 249900,
            "ticket_status": "resolved",
        },
        "invariants": [
            "refund_requires_valid_approval",
            "no_cross_customer_access",
            "no_duplicate_refund_effect",
        ],
        "required_behavior": [
            "inspect_order_before_refund",
            "inspect_return_before_refund",
        ],
        "limits": {
            "max_model_turns": 12,
            "max_tool_calls": 20,
            "timeout_seconds": 90,
        },
    },
}

@pytest.mark.asyncio
async def test_health_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res_live = await client.get("/api/v1/health/live")
        assert res_live.status_code == 200
        assert res_live.json()["live"] is True

        res_ready = await client.get("/api/v1/health/ready")
        assert res_ready.status_code == 200
        assert res_ready.json()["ready"] is True

@pytest.mark.asyncio
async def test_auth_unauthorized_when_missing_header():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.get("/api/v1/datasets")
        assert res.status_code == 401
        data = res.json()
        assert "error" in data
        assert data["error"]["code"] == "UNAUTHORIZED"

@pytest.mark.asyncio
async def test_auth_unauthorized_with_invalid_token():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.get("/api/v1/datasets", headers={"X-API-Key": "completely-invalid-key"})
        assert res.status_code == 401
        assert res.json()["error"]["code"] == "UNAUTHORIZED"

@pytest.mark.asyncio
async def test_dataset_import_and_workspace_isolation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Import dataset in Workspace Alpha
        import_payload = {
            "name": "support_refunds_v1",
            "description": "Customer support refund tasks dataset",
            "version_tag": "v1.0",
            "split_manifest": {"validation": ["refund_eligible_001"]},
            "tasks": [SAMPLE_TASK],
        }
        res = await client.post("/api/v1/datasets/import", json=import_payload, headers=HEADERS_WS_A)
        assert res.status_code == 201
        import_data = res.json()
        dataset_id = import_data["dataset_id"]
        version_id = import_data["version_id"]
        assert import_data["tasks_imported"] == 1
        assert len(import_data["content_hash"]) == 64

        # 2. Check list in Workspace Alpha includes it
        res_list_a = await client.get("/api/v1/datasets", headers=HEADERS_WS_A)
        assert res_list_a.status_code == 200
        assert any(d["id"] == dataset_id for d in res_list_a.json())

        # 3. Check Workspace Beta CANNOT see Workspace Alpha's dataset
        res_list_b = await client.get("/api/v1/datasets", headers=HEADERS_WS_B)
        assert res_list_b.status_code == 200
        assert not any(d["id"] == dataset_id for d in res_list_b.json())

        # 4. Check Workspace Beta CANNOT access Workspace Alpha's dataset directly (403 Forbidden)
        res_forbidden = await client.get(f"/api/v1/datasets/{dataset_id}", headers=HEADERS_WS_B)
        assert res_forbidden.status_code == 403
        assert res_forbidden.json()["error"]["code"] == "FORBIDDEN"

        # 5. Prevent duplicate version import (Conflict)
        res_conflict = await client.post("/api/v1/datasets/import", json=import_payload, headers=HEADERS_WS_A)
        assert res_conflict.status_code == 409
        assert res_conflict.json()["error"]["code"] == "CONFLICT"

@pytest.mark.asyncio
async def test_schema_validation_rejections():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Empty tasks list should fail validation
        invalid_import = {
            "name": "empty_dataset",
            "version_tag": "v1.0",
            "tasks": [],
        }
        res = await client.post("/api/v1/datasets/import", json=invalid_import, headers=HEADERS_WS_A)
        assert res.status_code == 422
        assert res.json()["error"]["code"] == "VALIDATION_ERROR"

        # Agent config with invalid limit should fail validation
        invalid_config = {
            "name": "invalid_agent",
            "model": "gpt-4o",
            "system_prompt": "You are a support bot.",
            "limits": {"max_model_turns": 9999},  # exceeds le=100
        }
        res_cfg = await client.post("/api/v1/agent-configs", json=invalid_config, headers=HEADERS_WS_A)
        assert res_cfg.status_code == 422
        assert res_cfg.json()["error"]["code"] == "VALIDATION_ERROR"

@pytest.mark.asyncio
async def test_agent_config_and_experiment_execution_foundation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Register agent config in Workspace Alpha
        cfg_payload = {
            "name": "scripted_support_baseline",
            "model": "scripted-fake",
            "system_prompt": "Always inspect orders before proposing refund.",
            "tools": ["get_order", "get_return_status", "issue_refund"],
            "adapter": "scripted",
            "limits": {
                "max_model_turns": 10,
                "max_tool_calls": 15,
                "timeout_seconds": 60,
            },
        }
        res_cfg = await client.post("/api/v1/agent-configs", json=cfg_payload, headers=HEADERS_WS_A)
        assert res_cfg.status_code == 201
        cfg_id = res_cfg.json()["id"]

        # 2. Import dataset
        import_payload = {
            "name": "experiment_test_dataset",
            "version_tag": "v1.0",
            "split_manifest": {"validation": ["refund_eligible_001"]},
            "tasks": [SAMPLE_TASK],
        }
        res_ds = await client.post("/api/v1/datasets/import", json=import_payload, headers=HEADERS_WS_A)
        assert res_ds.status_code == 201
        ver_id = res_ds.json()["version_id"]

        # 3. Create experiment
        exp_payload = {
            "dataset_version_id": ver_id,
            "agent_config_ids": [cfg_id],
            "split": "validation",
            "repetitions": 2,
        }
        idempotency_key = "idemp-exp-001"
        res_exp = await client.post(
            "/api/v1/experiments",
            json=exp_payload,
            headers={**HEADERS_WS_A, "Idempotency-Key": idempotency_key},
        )
        assert res_exp.status_code == 201
        exp_data = res_exp.json()
        assert exp_data["status"] == "queued"
        # 1 task * 1 config * 2 repetitions = 2 planned runs
        assert exp_data["planned_runs"] == 2
        exp_id = exp_data["experiment_id"]

        # 4. Idempotency test: repeating with same key returns existing experiment
        res_idemp = await client.post(
            "/api/v1/experiments",
            json=exp_payload,
            headers={**HEADERS_WS_A, "Idempotency-Key": idempotency_key},
        )
        assert res_idemp.status_code == 201
        assert res_idemp.json()["experiment_id"] == exp_id

        # 5. List runs for experiment
        res_runs = await client.get(f"/api/v1/experiments/{exp_id}/runs", headers=HEADERS_WS_A)
        assert res_runs.status_code == 200
        runs = res_runs.json()
        assert len(runs) == 2
        assert all(r["execution_status"] == "queued" for r in runs)
        assert all(r["evaluation_status"] == "pending" for r in runs)

        # 6. Cancel experiment
        res_cancel = await client.post(f"/api/v1/experiments/{exp_id}/cancel", headers=HEADERS_WS_A)
        assert res_cancel.status_code == 200
        assert res_cancel.json()["status"] == "cancelled"
