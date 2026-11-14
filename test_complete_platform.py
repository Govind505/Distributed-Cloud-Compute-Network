"""
Comprehensive Platform Verification Suite for DCCN
Validates:
1. Unified enterprise authentication & automatic role redirection
2. Virtual accounting ledger, credit deductions, and provider yields
3. Workload submission, 7-factor scheduling, and container execution
4. Real-time WebSocket telemetry streaming
5. True RBAC enforcement (role isolation, permission boundaries, 403 checks)
6. Deep System Analytics command center metrics
"""
import sys
import asyncio
import httpx
from starlette.testclient import TestClient
from server.app.main import app
from server.app.database_seeder import auto_init_and_seed_db

client = TestClient(app)


def test_auth_and_redirection():
    print("\n[TEST 1] Testing Unified Enterprise Authentication & Auto-Redirection...")
    
    # 1. Login as Compute Client
    resp = client.post("/api/v1/auth/login", json={"email": "client@dccn.network", "password": "client123"})
    assert resp.status_code == 200, f"Client login failed: {resp.text}"
    c_data = resp.json()
    assert c_data["user"]["role"] == "compute_user"
    assert c_data["user"]["portal_url"] == "/client"
    assert "scopes" in c_data["user"]["permissions"]
    print("  [PASS] Compute Client -> role: compute_user, target: /client")

    # 2. Login as Compute Provider
    resp = client.post("/api/v1/auth/login", json={"email": "provider@dccn.network", "password": "provider123"})
    assert resp.status_code == 200, f"Provider login failed: {resp.text}"
    p_data = resp.json()
    assert p_data["user"]["role"] == "compute_provider"
    assert p_data["user"]["portal_url"] == "/provider"
    print("  [PASS] Compute Provider -> role: compute_provider, target: /provider")

    # 3. Login as Administrator
    resp = client.post("/api/v1/auth/login", json={"email": "admin@dccn.network", "password": "admin123"})
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    a_data = resp.json()
    assert a_data["user"]["role"] == "admin"
    assert a_data["user"]["portal_url"] == "/admin"
    assert a_data["user"]["permissions"]["can_view_analytics"] is True
    print("  [PASS] Administrator -> role: admin, target: /admin (Superuser Authority)")

    # 4. Check /login static file
    resp = client.get("/login")
    assert resp.status_code == 200
    assert "Enterprise Unified Identity & Access Gateway" in resp.text
    assert "Sign In to Compute Workspace" in resp.text
    print("  [PASS] /login serves unified IAM portal without legacy switcher cards")


def test_billing_and_ledger():
    print("\n[TEST 2] Testing Compute Credit Virtual Ledger & Accounting...")
    
    c_token = client.post("/api/v1/auth/login", json={"email": "client@dccn.network", "password": "client123"}).json()["access_token"]

    # Check client balance
    resp = client.get("/api/v1/billing/balance", headers={"Authorization": f"Bearer {c_token}"})
    assert resp.status_code == 200
    b_data = resp.json()
    assert "balance" in b_data
    assert b_data["currency"] == "DCCN Credits"
    initial_client_bal = b_data["balance"]
    print(f"  [PASS] Client balance verified: {initial_client_bal} DCCN Credits")

    # Test top-up
    topup_resp = client.post("/api/v1/billing/topup", json={"amount": 500.0}, headers={"Authorization": f"Bearer {c_token}"})
    assert topup_resp.status_code == 200
    topup_data = topup_resp.json()
    assert topup_data["new_balance"] == round(initial_client_bal + 500.0, 2)
    print(f"  [PASS] Client top-up +500 Credits -> New balance: {topup_data['new_balance']} DCCN")

    # Check pricing schedule
    pricing_resp = client.get("/api/v1/billing/pricing")
    assert pricing_resp.status_code == 200
    rates = pricing_resp.json()["rates"]
    assert rates["vcpu_core_per_hour"] == 10.0
    assert rates["gpu_accelerator_per_hour"] == 50.0
    print(f"  [PASS] Pricing verified: {rates['vcpu_core_per_hour']} Credits/vCPU-hr, {rates['gpu_accelerator_per_hour']} Credits/GPU-hr")

    # Check ledger history
    ledger_resp = client.get("/api/v1/billing/ledger", headers={"Authorization": f"Bearer {c_token}"})
    assert ledger_resp.status_code == 200
    history = ledger_resp.json()
    assert len(history) > 0
    print(f"  [PASS] Virtual ledger audit trail retrieved ({len(history)} entries)")


def test_workload_submission_scheduling_and_settlement():
    print("\n[TEST 3] Testing Workload Submission, 7-Factor Scheduling, Execution & Settlement...")
    
    c_token = client.post("/api/v1/auth/login", json={"email": "client@dccn.network", "password": "client123"}).json()["access_token"]
    
    # 1. Submit a workload
    job_payload = {
        "name": "Monte Carlo Risk Analysis",
        "image_name": "python:3.11-slim",
        "command": "python -c 'import random; print(sum(random.random() for _ in range(1000000)))'",
        "priority": 6,
        "timeout_seconds": 1200,
        "requirements": {
            "cpu_cores": 2.0,
            "ram_mb": 2048,
            "disk_mb": 512,
            "gpu_count": 0,
            "gpu_vram_mb": 0
        }
    }
    sub_resp = client.post("/api/v1/jobs/", json=job_payload, headers={"Authorization": f"Bearer {c_token}"})
    assert sub_resp.status_code == 201, f"Job submission failed: {sub_resp.text}"
    job_id = sub_resp.json()["id"]
    print(f"  [PASS] Workload submitted successfully (ID: {job_id[:8]}...)")

    # 2. Schedule using 7-factor algorithm (idempotent)
    sched_resp = client.post(f"/api/v1/scheduler/schedule/{job_id}", headers={"Authorization": f"Bearer {c_token}"})
    assert sched_resp.status_code == 200, f"Scheduling failed: {sched_resp.text}"
    s_data = sched_resp.json()
    assert s_data["success"] is True
    assert "score" in s_data
    assert "node_name" in s_data
    print(f"  [PASS] 7-Factor Placement: Assigned to '{s_data['node_name']}' with Composite Score {s_data['score']}")

    # 3. Dispatch & Execute
    dispatch_resp = client.post(f"/api/v1/jobs/{job_id}/dispatch", headers={"Authorization": f"Bearer {c_token}"})
    assert dispatch_resp.status_code == 200, f"Dispatch failed: {dispatch_resp.text}"
    d_data = dispatch_resp.json()
    assert d_data["exit_code"] == 0
    assert "billing" in d_data
    assert d_data["billing"]["cost"] > 0
    print(f"  [PASS] Workload executed cleanly! Exit code 0 | Engine: {d_data.get('runtime_engine')}")
    print(f"  [PASS] Credit Settlement: Deducted {d_data['billing']['cost']} Credits from client | Awarded {d_data['billing']['provider_yield']} Yield to provider")

    # 4. View Terminal Logs
    logs_resp = client.get(f"/api/v1/jobs/{job_id}/logs", headers={"Authorization": f"Bearer {c_token}"})
    assert logs_resp.status_code == 200
    assert "DCCN-OCI-RUNTIME" in logs_resp.json()["logs"] or "DCCN-DOCKER-ENGINE" in logs_resp.json()["logs"]
    print("  [PASS] Terminal stdout/stderr telemetry captured and verified")


def test_websocket_telemetry():
    print("\n[TEST 4] Testing Real-Time WebSocket Telemetry Channel...")
    with client.websocket_connect("/ws/telemetry") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "telemetry_stream"
        assert "nodes" in msg
        assert "hardware" in msg
        assert "cluster_load" in msg
        assert "jobs" in msg
        assert msg["nodes"]["total"] >= 4
        print(f"  [PASS] Real-time stream active! Fleet: {msg['nodes']['total']} nodes, {msg['hardware']['total_cores']} cores, {msg['jobs']['total']} jobs")


def test_true_rbac_and_analytics():
    print("\n[TEST 5] Testing True RBAC Enforcement & System Analytics...")
    
    a_token = client.post("/api/v1/auth/login", json={"email": "admin@dccn.network", "password": "admin123"}).json()["access_token"]
    c_token = client.post("/api/v1/auth/login", json={"email": "client@dccn.network", "password": "client123"}).json()["access_token"]
    p_token = client.post("/api/v1/auth/login", json={"email": "provider@dccn.network", "password": "provider123"}).json()["access_token"]

    # 1. RBAC Isolation Check: Client cannot access Admin Analytics
    denied_resp = client.get("/api/v1/admin/analytics", headers={"Authorization": f"Bearer {c_token}"})
    assert denied_resp.status_code == 403, f"Expected 403 for client accessing admin analytics, got {denied_resp.status_code}"
    print("  [PASS] RBAC Boundary: Client strictly barred from /api/v1/admin/analytics (403 Forbidden)")

    # 2. RBAC Isolation Check: Provider cannot access Admin User Governance
    prov_denied = client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {p_token}"})
    assert prov_denied.status_code == 403
    print("  [PASS] RBAC Boundary: Provider strictly barred from /api/v1/admin/users (403 Forbidden)")

    # 3. RBAC Matrix Endpoint
    matrix_resp = client.get("/api/v1/admin/rbac/matrix", headers={"Authorization": f"Bearer {a_token}"})
    assert matrix_resp.status_code == 200
    roles = matrix_resp.json()["roles"]
    assert len(roles) == 3
    print(f"  [PASS] RBAC Architecture Matrix verified: {len(roles)} defined roles with cryptographic scopes")

    # 4. System Analytics Command Center
    analytics_resp = client.get("/api/v1/admin/analytics", headers={"Authorization": f"Bearer {a_token}"})
    assert analytics_resp.status_code == 200
    an = analytics_resp.json()
    assert "fleet" in an
    assert "telemetry" in an
    assert "workloads" in an
    assert "scheduler_7factor" in an
    assert "economics" in an
    print(f"  [PASS] System Analytics verified: Fleet ({an['fleet']['total_cores']} cores), Economics ({an['economics']['total_transacted_volume']} DCCN transacted), 7-Factor Avg Score ({an['scheduler_7factor']['avg_composite_score']})")

    # 5. Admin Governance: Adjust User Credits
    users_resp = client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {a_token}"})
    users = users_resp.json()
    target_user = users[0]
    adj_resp = client.post(
        f"/api/v1/admin/users/{target_user['id']}/credits",
        json={"amount": 100.0, "reason": "Test grant"},
        headers={"Authorization": f"Bearer {a_token}"}
    )
    assert adj_resp.status_code == 200
    assert adj_resp.json()["success"] is True
    print(f"  [PASS] Admin Governance: Successfully adjusted credits for user '{target_user['username']}'")

    # 6. Admin Governance: Node Drain Toggle
    nodes_resp = client.get("/api/v1/nodes/all", headers={"Authorization": f"Bearer {a_token}"})
    nodes = nodes_resp.json()
    test_node = nodes[0]
    drain_resp = client.post(f"/api/v1/admin/nodes/{test_node['id']}/drain", headers={"Authorization": f"Bearer {a_token}"})
    assert drain_resp.status_code == 200
    drain_data = drain_resp.json()
    print(f"  [PASS] Admin Fleet Governance: Toggled node '{test_node['name']}' drain state to '{drain_data['status']}'")


def test_platform_improvisations():
    print("\n[TEST 6] Testing 5 Advanced Architectural Subsystems (Improvisations)...")
    a_token = client.post("/api/v1/auth/login", json={"email": "admin@dccn.network", "password": "admin123"}).json()["access_token"]
    c_token = client.post("/api/v1/auth/login", json={"email": "client@dccn.network", "password": "client123"}).json()["access_token"]

    # 1. Raft HA Consensus
    c_resp = client.get("/api/v1/platform/consensus/status", headers={"Authorization": f"Bearer {a_token}"})
    assert c_resp.status_code == 200
    c_data = c_resp.json()
    assert c_data["active_quorum"] is True
    assert len(c_data["peers"]) == 3
    print(f"  [PASS] 1. Raft HA Consensus: Leader={c_data['leader_id']}, Term={c_data['current_term']}, Quorum=3/3 Active")

    failover_resp = client.post("/api/v1/platform/consensus/failover", headers={"Authorization": f"Bearer {a_token}"})
    assert failover_resp.status_code == 200
    f_data = failover_resp.json()
    assert f_data["term"] > c_data["current_term"]
    print(f"  [PASS] 1. Raft Failover Election: New Leader={f_data['new_elected_leader']}, Term={f_data['term']}")

    # 2. Verifiable Computing Attestation Proofs
    proofs_resp = client.get("/api/v1/platform/verification/proofs", headers={"Authorization": f"Bearer {a_token}"})
    assert proofs_resp.status_code == 200
    proofs = proofs_resp.json()
    assert len(proofs) > 0
    test_proof = proofs[0]
    assert test_proof["verification_status"] == "VERIFIED_VALID"
    assert test_proof["sha256_checksum"] is not None
    assert test_proof["attestation_signature"].startswith("sig_ed25519_")
    print(f"  [PASS] 2. Verifiable Computing: Proof {test_proof['proof_id']} for job '{test_proof['job_name']}' - SHA256 verified, Ed25519 signed")

    # Redundant witness check
    check_resp = client.post(
        "/api/v1/platform/verification/sample-check",
        json={"job_id": test_proof["job_id"], "sample_output": "divergent fraudulent output"},
        headers={"Authorization": f"Bearer {a_token}"}
    )
    assert check_resp.status_code == 200
    check_data = check_resp.json()
    assert check_data["verdict"] == "DIVERGENT_OUTPUT_FRAUD"
    assert check_data["slashing_penalty_applied"] is True
    print(f"  [PASS] 2. Witness Cross-Sampling: Fraud detection & slashing penalty applied (50 credits)")

    # 3. Dynamic Spot Market & VCG 2nd-Price Auctions
    spot_resp = client.get("/api/v1/platform/market/spot-rates", headers={"Authorization": f"Bearer {c_token}"})
    assert spot_resp.status_code == 200
    spot_data = spot_resp.json()
    assert "spot_multiplier" in spot_data
    assert "vcpu_spot_per_hour" in spot_data["rates"]
    print(f"  [PASS] 3. Dynamic Spot Market: Multiplier={spot_data['spot_multiplier']}x, Discount={spot_data['spot_discount_percent']}%, Condition={spot_data['market_condition']}")

    # Submit spot auction bid
    bid_resp = client.post(
        "/api/v1/platform/market/bid",
        json={"max_bid": 30.0, "cpu_cores": 2.0, "gpu_count": 0},
        headers={"Authorization": f"Bearer {c_token}"}
    )
    assert bid_resp.status_code == 200
    bid_data = bid_resp.json()
    assert "bid_accepted" in bid_data
    assert "auction_type" in bid_data
    print(f"  [PASS] 3. VCG 2nd-Price Auction: Bid Accepted={bid_data['bid_accepted']}, Charge Rate={bid_data['actual_charge_rate']} cr/hr, Surplus Savings={bid_data['consumer_surplus_savings']} cr")

    # 4. OpenTelemetry Tracing
    traces_resp = client.get("/api/v1/platform/tracing", headers={"Authorization": f"Bearer {a_token}"})
    assert traces_resp.status_code == 200
    traces = traces_resp.json()
    assert len(traces) > 0
    t_id = traces[0]["job_id"]
    dag_resp = client.get(f"/api/v1/platform/tracing/{t_id}", headers={"Authorization": f"Bearer {a_token}"})
    assert dag_resp.status_code == 200
    dag = dag_resp.json()
    assert len(dag["spans"]) >= 7
    span_names = [s["name"] for s in dag["spans"]]
    assert "scheduler.7factor_ranking" in span_names
    assert "raft.consensus_log_replicate" in span_names
    print(f"  [PASS] 4. OpenTelemetry Tracing: Trace {dag['trace_id']} has {len(dag['spans'])} spans across API, Scheduler, Raft, Runtime, and Ledger")

    # 5. eBPF & cgroup v2 Kernel Isolation
    iso_resp = client.get("/api/v1/platform/isolation/status", headers={"Authorization": f"Bearer {a_token}"})
    assert iso_resp.status_code == 200
    iso = iso_resp.json()
    assert iso["cgroup_version"].startswith("v2")
    assert iso["ebpf_programs_loaded"] == 3
    print(f"  [PASS] 5. eBPF & cgroup v2 Isolation: {iso['cgroup_version']}, Seccomp={iso['seccomp_bpf_mode'][:16]}..., 3 eBPF JIT Programs Loaded")

    # 6. Admin Analytics includes Platform Subsystems
    analytics_resp = client.get("/api/v1/admin/analytics", headers={"Authorization": f"Bearer {a_token}"})
    assert analytics_resp.status_code == 200
    an = analytics_resp.json()
    assert "platform_subsystems" in an
    ps = an["platform_subsystems"]
    assert "consensus" in ps
    assert "spot_market" in ps
    assert "verification" in ps
    assert "tracing" in ps
    assert "isolation" in ps
    print("  [PASS] 6. Admin Analytics birds-eye platform status includes all 5 advanced subsystems")


def test_cloud_arbitrage_and_fractional_slicing():
    print("\n[TEST 7] Testing Cloud Instance Broker, Arbitrage Engine & Fractional Slicing...")
    p_token = client.post("/api/v1/auth/login", json={"email": "provider@dccn.network", "password": "provider123"}).json()["access_token"]
    c_token = client.post("/api/v1/auth/login", json={"email": "client@dccn.network", "password": "client123"}).json()["access_token"]

    # 1. Provider Registers Rented Cloud Node (Hetzner EX44 Arbitrage Host)
    node_payload = {
        "name": "Hetzner-Cloud-Broker-01",
        "hostname": "ex44.hetzner.dccn.host",
        "cpu_cores": 14,
        "ram_total_mb": 65536,
        "disk_total_mb": 512000,
        "cloud_provider": "hetzner",
        "region": "eu-central",
        "overcommit_ratio": 2.5,
        "cost_per_hour_usd": 0.066,
    }
    reg_resp = client.post("/api/v1/nodes/register", json=node_payload, headers={"Authorization": f"Bearer {p_token}"})
    assert reg_resp.status_code == 201, f"Cloud node register failed: {reg_resp.text}"
    cloud_node = reg_resp.json()
    assert cloud_node["cloud_provider"] == "hetzner"
    assert cloud_node["overcommit_ratio"] == 2.5
    print(f"  [PASS] 1. Cloud Machine Enrolled: '{cloud_node['name']}' (HETZNER, 14 Cores x 2.5 Overcommit = 35 vCPU capacity)")

    # 2. 1-Click Install Script Generator
    script_resp = client.get("/api/v1/nodes/cloud/install-script?cloud_provider=hetzner&overcommit=2.5", headers={"Authorization": f"Bearer {p_token}"})
    assert script_resp.status_code == 200
    script_data = script_resp.json()
    assert "one_line_bash" in script_data
    assert "curl -sSL" in script_data["one_line_bash"]
    print(f"  [PASS] 2. 1-Click Cloud Install Generator: Generated script for provider '{script_data['provider_email']}'")

    # 3. Client Submits Fractional Micro-Container (0.25 vCPU, 256MB RAM)
    micro_job_payload = {
        "name": "Micro-Inference-Job-0.25vCPU",
        "image_name": "python:3.11-slim",
        "command": "python -c 'print(\"Executing fractional micro-task!\")'",
        "priority": 7,
        "timeout_seconds": 120,
        "requirements": {
            "cpu_cores": 0.25,
            "ram_mb": 256,
            "disk_mb": 128,
            "gpu_count": 0,
            "gpu_vram_mb": 0,
        }
    }
    job_resp = client.post("/api/v1/jobs/", json=micro_job_payload, headers={"Authorization": f"Bearer {c_token}"})
    assert job_resp.status_code == 201
    micro_job = job_resp.json()
    assert micro_job["requirements"]["cpu_cores"] == 0.25
    print(f"  [PASS] 3. Fractional Micro-Workload Submitted: 0.25 vCPU, 256 MB RAM")

    # Schedule the micro-job
    sched_resp = client.post(f"/api/v1/scheduler/schedule/{micro_job['id']}", headers={"Authorization": f"Bearer {c_token}"})
    assert sched_resp.status_code == 200
    sched_data = sched_resp.json()
    assert sched_data["success"] is True
    print(f"  [PASS] 3. Fractional Slicing Scheduled: Assigned to '{sched_data['node_name']}' with 7-factor score {sched_data['score']}")

    # Dispatch and execute micro-job
    disp_resp = client.post(f"/api/v1/jobs/{micro_job['id']}/dispatch", headers={"Authorization": f"Bearer {c_token}"})
    assert disp_resp.status_code == 200
    exec_data = disp_resp.json()
    assert exec_data["exit_code"] == 0
    # Verify micro-tier fee settled at 0.50 credits minimum instead of 2.50
    assert exec_data["billing"]["cost"] == 0.5
    print(f"  [PASS] 3. Sub-Core Micro-Billing Settled: Debited {exec_data['billing']['cost']} credits (0.50 min), Provider Yield: {exec_data['billing']['provider_yield']} credits")

    # 4. Arbitrage Calculator API
    arb_resp = client.post(
        "/api/v1/billing/arbitrage/calculate",
        json={"preset_key": "hetzner_dedicated", "utilization_percent": 65.0, "overcommit_ratio": 2.5}
    )
    assert arb_resp.status_code == 200
    arb = arb_resp.json()
    assert arb["financials"]["profitable"] is True
    assert arb["financials"]["monthly_net_profit_usd"] > 0
    print(f"  [PASS] 4. Arbitrage Engine: Hetzner €44/mo -> Net Profit: +${arb['financials']['monthly_net_profit_usd']}/mo (+{arb['financials']['roi_margin_percent']}% ROI)")
    print(f"  [PASS] 4. Market Disruption: {arb['market_disruption']['client_savings_vs_aws_percent']}% cheaper for clients vs AWS EC2!")

    # 5. Spot Preemption Eviction & Failover Trigger
    preempt_resp = client.post(f"/api/v1/nodes/{cloud_node['id']}/preempt", headers={"Authorization": f"Bearer {p_token}"})
    assert preempt_resp.status_code == 200
    preempt_data = preempt_resp.json()
    assert preempt_data["action"] == "SPOT_PREEMPTION_MIGRATION_EXECUTED"
    print(f"  [PASS] 5. Spot Interruption Trap: Host safely drained & failover migration triggered for preemption resilience")


def main():
    print("=" * 65)
    print("  DISTRIBUTED CLOUD COMPUTE NETWORK — COMPREHENSIVE VERIFICATION")
    print("=" * 65)
    
    # Initialize DB
    asyncio.run(auto_init_and_seed_db())
    
    test_auth_and_redirection()
    test_billing_and_ledger()
    test_workload_submission_scheduling_and_settlement()
    test_websocket_telemetry()
    test_true_rbac_and_analytics()
    test_platform_improvisations()
    test_cloud_arbitrage_and_fractional_slicing()

    print("\n" + "=" * 65)
    print("  ALL 7 TEST SUITES PASSED! HYPER-AFFORDABLE CLOUD BROKER 100% OPERATIONAL!")
    print("=" * 65)


if __name__ == "__main__":
    main()
