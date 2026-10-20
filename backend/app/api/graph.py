from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from app.services.graph import (get_nodes, get_edges, get_graph_summary,
                                 export_graph_json, export_graph_graphml, export_graph_dot)
from app.models.graph import GraphNodesResponse, GraphEdgesResponse, GraphSummary


router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/nodes", response_model=GraphNodesResponse)
async def list_nodes(
    job_id: int = Query(..., description="Parse job ID"),
    node_type: Optional[str] = Query(None, description="Filter by node type"),
    name: Optional[str] = Query(None, description="Filter by name (partial match)"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    nodes, total = get_nodes(job_id, node_type, name, limit, offset)
    return GraphNodesResponse(nodes=nodes, total=total, limit=limit, offset=offset)


@router.get("/edges", response_model=GraphEdgesResponse)
async def list_edges(
    job_id: int = Query(..., description="Parse job ID"),
    source_id: Optional[int] = Query(None, description="Filter by source node ID"),
    target_id: Optional[int] = Query(None, description="Filter by target node ID"),
    edge_type: Optional[str] = Query(None, description="Filter by edge type"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    edges, total = get_edges(job_id, source_id, target_id, edge_type, limit, offset)
    return GraphEdgesResponse(edges=edges, total=total, limit=limit, offset=offset)


@router.get("/summary", response_model=GraphSummary)
async def graph_summary(job_id: int = Query(..., description="Parse job ID")):
    summary = get_graph_summary(job_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Parse job not found")
    return summary


@router.get("/export/json")
async def export_json(job_id: int = Query(..., description="Parse job ID")):
    return export_graph_json(job_id)


@router.get("/export/graphml")
async def export_graphml(job_id: int = Query(..., description="Parse job ID")):
    from fastapi.responses import Response
    content = export_graph_graphml(job_id)
    return Response(content=content, media_type="application/xml")


@router.get("/export/dot")
async def export_dot(job_id: int = Query(..., description="Parse job ID")):
    from fastapi.responses import Response
    content = export_graph_dot(job_id)
    return Response(content=content, media_type="text/plain")