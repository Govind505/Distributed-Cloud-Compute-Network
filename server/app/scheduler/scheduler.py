"""Main scheduler service: coordinates filter -> rank -> reserve -> dispatch."""
import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.models.node import ComputeNode, NodeStatus, ResourceSnapshot
from app.models.job import Job, JobState, JobRequirement
from app.models.allocation import Allocation, AllocationState
from app.models.audit import AuditLog
from app.scheduler.filter import filter_nodes
from app.scheduler.ranker import rank_nodes


class SchedulerService:
    """Coordinates the filter-rank-reserve-dispatch scheduling pipeline."""

    async def schedule_job(self, job_id: uuid.UUID, db: AsyncSession) -> dict:
        """Attempt to schedule a single job.
        
        Returns a dict with scheduling result including node_id, score, breakdown.
        """
        # 1. Load the job with requirements
        result = await db.execute(
            select(Job)
            .options(selectinload(Job.requirements))
            .where(Job.id == job_id)
        )
        job = result.scalar_one_or_none()
        if not job:
            return {"success": False, "message": "Job not found"}

        if job.state not in (JobState.QUEUED, JobState.PENDING):
            return {"success": False, "message": f"Job is in state {job.state.value}, cannot schedule"}

        requirements = job.requirements
        if not requirements:
            return {"success": False, "message": "Job has no resource requirements"}

        # Mark job as scheduling
        job.state = JobState.SCHEDULING
        await db.flush()

        # 2. Load all online nodes
        nodes_result = await db.execute(
            select(ComputeNode).where(ComputeNode.status == NodeStatus.ONLINE)
        )
        nodes = list(nodes_result.scalars().all())

        if not nodes:
            job.state = JobState.QUEUED  # Return to queue
            await db.commit()
            return {"success": False, "message": "No online nodes available"}

        # 3. Load latest snapshot for each node
        snapshots = {}
        for node in nodes:
            snap_result = await db.execute(
                select(ResourceSnapshot)
                .where(ResourceSnapshot.node_id == node.id)
                .order_by(ResourceSnapshot.sampled_at.desc())
                .limit(1)
            )
            snap = snap_result.scalar_one_or_none()
            if snap:
                snapshots[str(node.id)] = snap

        # 4. Calculate reserved resources per node from active allocations
        reserved_resources = await self._get_reserved_resources(db)

        # 5. FILTER: Remove ineligible nodes
        eligible = filter_nodes(nodes, snapshots, requirements, reserved_resources)

        if not eligible:
            job.state = JobState.QUEUED  # Return to queue
            await db.commit()
            return {
                "success": False,
                "message": f"No eligible nodes out of {len(nodes)} online nodes",
                "nodes_checked": len(nodes),
            }

        # 6. RANK: Score eligible nodes
        ranked = rank_nodes(eligible, requirements, reserved_resources)

        # 7. RESERVE: Pick the best node and create allocation
        best_node, best_score, best_breakdown = ranked[0]

        # Count previous attempts for this job
        attempt_result = await db.execute(
            select(func.count()).select_from(Allocation).where(Allocation.job_id == job.id)
        )
        attempt_count = (attempt_result.scalar() or 0) + 1

        allocation = Allocation(
            job_id=job.id,
            node_id=best_node.id,
            score=best_score,
            score_breakdown=best_breakdown,
            attempt=attempt_count,
            state=AllocationState.RESERVED,
        )
        db.add(allocation)

        # Update job state
        job.state = JobState.ALLOCATED

        # Create audit log
        audit = AuditLog(
            actor_id=job.owner_id,
            action="job_scheduled",
            target_type="job",
            target_id=str(job.id),
            outcome="success",
            details={
                "node_id": str(best_node.id),
                "node_name": best_node.name,
                "score": best_score,
                "breakdown": best_breakdown,
                "nodes_checked": len(nodes),
                "nodes_eligible": len(eligible),
                "attempt": attempt_count,
            },
        )
        db.add(audit)

        await db.commit()

        return {
            "success": True,
            "message": f"Job scheduled on node '{best_node.name}' with score {best_score:.4f}",
            "job_id": str(job.id),
            "node_id": str(best_node.id),
            "node_name": best_node.name,
            "score": round(best_score, 4),
            "score_breakdown": best_breakdown,
            "nodes_checked": len(nodes),
            "nodes_eligible": len(eligible),
            "attempt": attempt_count,
            "all_rankings": [
                {
                    "node_id": str(n.id),
                    "node_name": n.name,
                    "score": round(s, 4),
                    "breakdown": b,
                }
                for n, s, b in ranked
            ],
        }

    async def _get_reserved_resources(self, db: AsyncSession) -> dict:
        """Get total reserved resources per node from active allocations."""
        active_states = [
            AllocationState.RESERVED,
            AllocationState.DISPATCHED,
            AllocationState.RUNNING,
        ]
        result = await db.execute(
            select(Allocation)
            .options(selectinload(Allocation.job).selectinload(Job.requirements))
            .where(Allocation.state.in_(active_states))
        )
        allocations = result.scalars().all()

        reserved = {}
        for alloc in allocations:
            node_id = str(alloc.node_id)
            req = alloc.job.requirements if alloc.job else None
            if req:
                if node_id not in reserved:
                    reserved[node_id] = {"cpu": 0, "ram": 0, "disk": 0, "gpu": 0}
                reserved[node_id]["cpu"] += req.cpu_cores
                reserved[node_id]["ram"] += req.ram_mb
                reserved[node_id]["disk"] += req.disk_mb
                reserved[node_id]["gpu"] += req.gpu_count

        return reserved

    async def schedule_all_queued(self, db: AsyncSession) -> list[dict]:
        """Attempt to schedule all queued jobs."""
        result = await db.execute(
            select(Job)
            .where(Job.state == JobState.QUEUED)
            .order_by(Job.priority.desc(), Job.created_at.asc())
        )
        queued_jobs = result.scalars().all()

        results = []
        for job in queued_jobs:
            schedule_result = await self.schedule_job(job.id, db)
            results.append(schedule_result)

        return results
