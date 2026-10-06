import uuid
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models.user import User
from app.models.node import ComputeNode, NodeStatus, ResourceSnapshot
from app.schemas.node import NodeRegister, NodeResponse, NodeUpdate, HeartbeatRequest, SnapshotResponse
from app.utils.dependencies import get_current_user, require_provider, require_admin

router = APIRouter(prefix="/nodes", tags=["Compute Nodes"])


@router.post("/register", response_model=NodeResponse, status_code=status.HTTP_201_CREATED)
async def register_node(
    node_data: NodeRegister,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_provider),
):
    """Register a new compute node."""
    node = ComputeNode(
        provider_id=current_user.id,
        name=node_data.name,
        hostname=node_data.hostname,
        ip_address=node_data.ip_address,
        cpu_cores=node_data.cpu_cores,
        ram_total_mb=node_data.ram_total_mb,
        disk_total_mb=node_data.disk_total_mb,
        gpu_model=node_data.gpu_model,
        gpu_count=node_data.gpu_count,
        gpu_vram_mb=node_data.gpu_vram_mb,
        labels=node_data.labels or {},
        status=NodeStatus.PENDING_APPROVAL,
    )
    db.add(node)
    await db.commit()
    await db.refresh(node)
    return node


@router.get("/", response_model=list[NodeResponse])
async def list_nodes(
    status_filter: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all compute nodes."""
    query = select(ComputeNode)
    if status_filter:
        try:
            ns = NodeStatus(status_filter)
            query = query.where(ComputeNode.status == ns)
        except ValueError:
            pass
    result = await db.execute(query.order_by(ComputeNode.created_at.desc()))
    return result.scalars().all()


@router.get("/{node_id}", response_model=NodeResponse)
async def get_node(
    node_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific compute node."""
    result = await db.execute(select(ComputeNode).where(ComputeNode.id == node_id))
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return node


@router.put("/{node_id}", response_model=NodeResponse)
async def update_node(
    node_id: uuid.UUID,
    update_data: NodeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Update a compute node (admin only)."""
    result = await db.execute(select(ComputeNode).where(ComputeNode.id == node_id))
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    if update_data.name is not None:
        node.name = update_data.name
    if update_data.status is not None:
        try:
            node.status = NodeStatus(update_data.status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {[s.value for s in NodeStatus]}")
    if update_data.labels is not None:
        node.labels = update_data.labels
    await db.commit()
    await db.refresh(node)
    return node


@router.post("/{node_id}/heartbeat", response_model=SnapshotResponse)
async def submit_heartbeat(
    node_id: uuid.UUID,
    heartbeat: HeartbeatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_provider),
):
    """Submit a heartbeat with resource telemetry from a node agent."""
    result = await db.execute(select(ComputeNode).where(ComputeNode.id == node_id))
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    if node.provider_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your node")

    # Update node last_seen and status
    node.last_seen = datetime.now(timezone.utc)
    if node.status == NodeStatus.SUSPECT:
        node.status = NodeStatus.ONLINE

    # Create resource snapshot
    snapshot = ResourceSnapshot(
        node_id=node_id,
        cpu_usage_percent=heartbeat.cpu_usage_percent,
        ram_free_mb=heartbeat.ram_free_mb,
        disk_free_mb=heartbeat.disk_free_mb,
        gpu_utilization_percent=heartbeat.gpu_utilization_percent,
        gpu_vram_free_mb=heartbeat.gpu_vram_free_mb,
        active_containers=heartbeat.active_containers,
        rtt_ms=0.0,  # Will be calculated from actual RTT
    )
    db.add(snapshot)
    await db.commit()
    await db.refresh(snapshot)
    return snapshot


@router.post("/{node_id}/approve", response_model=NodeResponse)
async def approve_node(
    node_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Approve a pending node (admin only)."""
    result = await db.execute(select(ComputeNode).where(ComputeNode.id == node_id))
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    if node.status != NodeStatus.PENDING_APPROVAL:
        raise HTTPException(status_code=400, detail="Node is not pending approval")
    node.status = NodeStatus.ONLINE
    await db.commit()
    await db.refresh(node)
    return node
