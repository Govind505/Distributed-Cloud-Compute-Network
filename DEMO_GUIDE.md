# 🎓 DCCN Mid-Evaluation Presentation & Demo Guide
**Date: October 7, 2026**
**Team:** Govind Choudhary (500123445), Neetesh Bisht (500124582), Yash Khanna (500119667)
**Project:** Distributed Cloud Compute Network for Dynamic Resource Allocation

---

## ⚡ 1-Minute Quick Start (Before Your Presentation)

### Step 1: Start Infrastructure & Server
Open a terminal in the project directory:
```bash
# Option A: Double-click run_demo.bat
# Option B: Run manually:
cd server
python init_db.py
uvicorn app.main:app --reload --port 8000
```
Open **`http://localhost:8000/dashboard`** in your browser.

### Step 2: Seed the Cluster with Telemetry & Benchmark Jobs
In a second terminal window:
```bash
cd agent
python seed_demo.py
```
> 🎉 **Instantly**, your dashboard will show **4 heterogeneous compute nodes** (2 CPU, 2 with NVIDIA RTX 3080 & Tesla T4 GPUs), live telemetry meters, and sample submitted jobs!

---

## 🎙️ 5-Minute Live Evaluation Script

### 1. The Problem Statement (1 Minute)
* *"Distributed workstations and edge compute nodes sit idle for 70%+ of the time, while engineers and researchers needing GPUs for ML training or CPU power for simulations lack dedicated cloud credits."*
* *"Our project pools volunteered heterogeneous hardware into an elastic compute network without needing expensive commercial cloud subscriptions."*

### 2. Show the Dashboard & Nodes (1 Minute)
* Open the **Compute Nodes** tab.
* Point out:
  * **Heterogeneity:** Show that node `Compute-Node-01` has 8 CPU cores / 16GB RAM, while `GPU-Cluster-01` has an NVIDIA RTX 3080 with 10GB VRAM.
  * **Live Telemetry:** Show the last seen heartbeat updates (5s intervals).
  * **Role-Based Access:** Mention the role system (`Admin`, `Compute Provider`, `Compute Client`).

### 3. Demonstrate Job Submission (1 Minute)
* Click **"Submit New Job"**.
* Fill in:
  * Workload Name: `PyTorch ResNet Classifier`
  * Docker Image: `pytorch/pytorch:latest`
  * GPU Request: `1 GPU` with `4096 MB VRAM`
* Click **Submit Job** → Show it immediately enters the **`QUEUED`** state.

### 4. The Intellectual Core — 7-Factor Weighted Scheduler (1.5 Minutes)
* Click **"Schedule"** next to the job or click the **"Scheduler Engine & Scoring"** tab.
* Explain the formula directly from your synopsis:
  $$\text{Score}(i,j) = 0.22C + 0.18M + 0.25G + 0.12L + 0.08N + 0.10R + 0.05P$$
* Show the live breakdown:
  * **Filter stage:** Excluded CPU-only nodes because the job requested a GPU.
  * **Ranker stage:** Scored the remaining GPU servers based on available VRAM match, inverse load, and reliability.
  * **Winner:** Node allocated atomically and logged into the **Audit Trail**.

### 5. Audit Trail & Wrap-up (30 Seconds)
* Open the **Audit Trail** tab.
* Show that every scheduling decision, node registration, and allocation is recorded with immutable timestamps and outcome statuses.

---

## 💡 Quick Answers to Likely Evaluator Questions

| Evaluator Question | Your Confident Answer |
|--------------------|----------------------|
| *"Where are the actual Docker containers executing?"* | *"For the mid-evaluation, the node agent collects and streams real system telemetry via psutil and simulates container execution states. Docker socket daemon integration with non-root security boundaries is our planned end-sem milestone."* |
| *"How do you prevent starvation for low-priority jobs?"* | *"Our scheduler includes an age-based queuing factor that increases a job's priority over time, preventing starvation by large workloads."* |
| *"What happens if a node disconnects?"* | *"Nodes report heartbeats every 10 seconds. If 3 consecutive heartbeats are missed (>30s), the node is flagged as suspect. After 60s, it's marked unavailable and active allocations are requeued."* |
| *"Why not just use Kubernetes?"* | *"Kubernetes is designed for high-availability enterprise clusters with homogeneous network fabrics. DCCN is tailored for intermittently available, consumer-grade heterogeneous distributed hardware with low operational overhead."* |
