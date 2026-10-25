"""
Watchdog Service: Monitors node health, handles heartbeat timeouts,
marks suspect/offline nodes, and triggers failover reallocation.
"""
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models.node import ComputeNode, NodeStatus
from app.models.job import Job, JobState
from app.models.allocation import Allocation, AllocationState
from app.models.audit import AuditLog

HEARTBEAT_SUSPECT_TIMEOUT_SECONDS = 45
HEARTBEAT_OFFLINE_TIMEOUT_SECONDS = 90


class WatchdogService:
    """Monitors node heartbeats and manages failover reallocation."""

    async def check_nodes_health(self, db: AsyncSession) -> dict:
        """Scan all online and suspect nodes for missed heartbeats."""
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(ComputeNode)
            .options(selectinload(ComputeNode.allocations))
            .where(ComputeNode.status.in_([NodeStatus.ONLINE, NodeStatus.SUSPECT]))
        )
        nodes = result.scalars().all()

        suspect_count = 0
        offline_count = 0
        requeued_jobs = 0

        for node in nodes:
            if not node.last_seen:
                continue

            last_seen_utc = (
                node.last_seen.replace(tzinfo=timezone.utc)
                if node.last_seen.tzinfo is None
                else node.last_seen
            )
            elapsed_seconds = (now - last_seen_utc).total_seconds()

            if elapsed_seconds > HEARTBEAT_OFFLINE_TIMEOUT_SECONDS:
                if node.status != NodeStatus.OFFLINE:
                    node.status = NodeStatus.OFFLINE
                    offline_count += 1

                    # Audit event
                    db.add(AuditLog(
                        actor_id=None,
                        action="node_offline_detected",
                        target_type="compute_node",
                        target_id=str(node.id),
                        outcome="warning",
                        details={"node_name": node.name, "elapsed_seconds": elapsed_seconds},
                    ))

                    # Requeue affected running/reserved workloads
                    for alloc in node.allocations:
                        if alloc.state in (AllocationState.RESERVED, AllocationState.DISPATCHED, AllocationState.RUNNING):
                            alloc.state = AllocationState.FAILED
                            job_res = await db.execute(select(Job).where(Job.id == alloc.job_id))
                            job = job_res.scalar_one_or_none()
                            if job and job.state in (JobState.ALLOCATED, JobState.RUNNING):
                                job.state = JobState.QUEUED
                                requeued_jobs += 1

            elif elapsed_seconds > HEARTBEAT_SUSPECT_TIMEOUT_SECONDS:
                if node.status != NodeStatus.SUSPECT:
                    node.status = NodeStatus.SUSPECT
                    suspect_count += 1

        await db.commit()
        return {
            "scanned": len(nodes),
            "marked_suspect": suspect_count,
            "marked_offline": offline_count,
            "requeued_jobs": requeued_jobs,
        }
