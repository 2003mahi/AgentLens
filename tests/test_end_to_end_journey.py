import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app

HEADERS = {"X-API-Key": "test-key-workspace-alpha"}

SAMPLE_TASK = {
    "task_id": "refund_e2e_001",
    "category": "refund",
    "difficulty": "easy",
    "agent_input": {
        "user_message": "Please refund order ord_e2e.",
        "authenticated_customer_id": "cust_e2e",
    },
    "environment_fixture": {
        "order": {
            "id": "ord_e2e",
            "customer_id": "cust_e2e",
            "paid_amount_minor": 10000,
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
            "refund_total_minor": 10000,
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
            "max_model_turns": 10,
            "max_tool_calls": 10,
            "timeout_seconds": 60,
        },
    },
}

@pytest.mark.asyncio
async def test_full_primary_end_to_end_journey():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Health check
        res = await client.get("/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"

        # 2. Agent registration
        agent_payload = {
            "name": "E2E Scripted Agent",
            "model": "scripted",
            "system_prompt": "You are a customer support agent.",
            "tools": ["order_lookup", "return_lookup", "propose_refund", "execute_refund"],
            "adapter": "scripted",
        }
        res_agent = await client.post("/api/v1/agent-configs", json=agent_payload, headers=HEADERS)
        assert res_agent.status_code == 201
        agent_data = res_agent.json()
        agent_id = agent_data["id"]

        # 3. Dataset import
        dataset_payload = {
            "name": "E2E Refund Dataset",
            "description": "Dataset for E2E testing",
            "version_tag": "v1.0",
            "tasks": [SAMPLE_TASK],
        }
        res_ds = await client.post("/api/v1/datasets/import", json=dataset_payload, headers=HEADERS)
        assert res_ds.status_code == 201
        ds_data = res_ds.json()
        dataset_id = ds_data["dataset_id"]
        dataset_version_id = ds_data["version_id"]

        # 4. List agents and datasets
        res_agents_list = await client.get("/api/v1/agent-configs", headers=HEADERS)
        assert res_agents_list.status_code == 200
        assert any(a["id"] == agent_id for a in res_agents_list.json())

        res_ds_list = await client.get("/api/v1/datasets", headers=HEADERS)
        assert res_ds_list.status_code == 200
        assert any(d["id"] == dataset_id for d in res_ds_list.json())

        # 5. Launch Experiment 1
        exp_payload = {
            "dataset_version_id": dataset_version_id,
            "agent_config_ids": [agent_id],
            "repetitions": 1,
        }
        res_exp1 = await client.post("/api/v1/experiments", json=exp_payload, headers=HEADERS)
        assert res_exp1.status_code == 201
        exp1_id = res_exp1.json()["experiment_id"]

        # 6. Execute Experiment 1
        res_exec = await client.post(f"/api/v1/experiments/{exp1_id}/execute", headers=HEADERS)
        assert res_exec.status_code == 200
        exec_summary = res_exec.json()
        assert exec_summary["total_attempts"] >= 1
        assert "composite_score" in exec_summary

        # 7. List runs for experiment
        res_runs = await client.get(f"/api/v1/experiments/{exp1_id}/runs", headers=HEADERS)
        assert res_runs.status_code == 200
        runs = res_runs.json()
        assert len(runs) >= 1
        run_id = runs[0]["id"]
        assert runs[0]["execution_status"] == "completed"

        # 8. Get run scores
        res_scores = await client.get(f"/api/v1/runs/{run_id}/scores", headers=HEADERS)
        assert res_scores.status_code == 200
        scores = res_scores.json()
        assert len(scores) > 0

        # 9. Get trace events for attempt
        attempts = runs[0]["attempts"]
        assert len(attempts) > 0
        attempt_id = attempts[0]["id"]

        res_events = await client.get(f"/api/v1/attempts/{attempt_id}/events", headers=HEADERS)
        assert res_events.status_code == 200
        events = res_events.json()
        assert len(events) > 0
        event_types = [e["event_type"] for e in events]
        assert "attempt_start" in event_types
        assert "attempt_finish" in event_types

        # 10. Generate JSON and CSV reports
        res_rep_json = await client.get(f"/api/v1/experiments/{exp1_id}/report?format=json", headers=HEADERS)
        assert res_rep_json.status_code == 200
        report_data = res_rep_json.json()
        assert report_data["experiment_id"] == exp1_id
        assert "composite_score" in report_data

        res_rep_csv = await client.get(f"/api/v1/experiments/{exp1_id}/report?format=csv", headers=HEADERS)
        assert res_rep_csv.status_code == 200
        assert "attempt_id" in res_rep_csv.text
        assert "run_id" in res_rep_csv.text

        # 11. Comparison: create and execute Experiment 2, then verify both reports can be retrieved
        res_exp2 = await client.post("/api/v1/experiments", json=exp_payload, headers=HEADERS)
        assert res_exp2.status_code == 201
        exp2_id = res_exp2.json()["experiment_id"]
        await client.post(f"/api/v1/experiments/{exp2_id}/execute", headers=HEADERS)

        res_rep_exp2 = await client.get(f"/api/v1/experiments/{exp2_id}/report?format=json", headers=HEADERS)
        assert res_rep_exp2.status_code == 200
        assert res_rep_exp2.json()["experiment_id"] == exp2_id

        # 12. Cleanup: Delete agent
        res_del_agent = await client.delete(f"/api/v1/agent-configs/{agent_id}", headers=HEADERS)
        assert res_del_agent.status_code in [200, 204]
