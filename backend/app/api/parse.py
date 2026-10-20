from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional

from app.services.parser import parse_directory
from app.services.graph import (create_parse_job, update_parse_job, get_parse_job,
                                 store_nodes, store_edges, get_graph_summary)
from app.models.graph import ParseRequest, ParseJob, GraphSummary


router = APIRouter(prefix="/parse", tags=["parse"])


class ParseResponse(BaseModel):
    job_id: int
    status: str
    message: str


@router.post("", response_model=ParseResponse)
async def parse_codebase(request: ParseRequest, background_tasks: BackgroundTasks):
    job_id = create_parse_job(request.root_path)

    background_tasks.add_task(
        run_parse_job,
        job_id,
        request.root_path,
        request.include_patterns,
        request.exclude_patterns,
        request.languages,
    )

    return ParseResponse(
        job_id=job_id,
        status="pending",
        message=f"Parse job {job_id} started for {request.root_path}"
    )


async def run_parse_job(job_id: int, root_path: str, include_patterns: Optional[list[str]],
                        exclude_patterns: Optional[list[str]], languages: Optional[list[str]]):
    update_parse_job(job_id, "running")

    try:
        nodes, edges, stats = parse_directory(
            root_path, job_id, include_patterns, exclude_patterns, languages
        )

        node_ids = store_nodes(job_id, nodes)
        node_id_map = {i: node_ids[i] for i in range(len(nodes))}

        adjusted_edges = []
        for edge in edges:
            if edge.source_id >= 0 and edge.target_id >= 0:
                adjusted_edges.append(edge)

        store_edges(job_id, adjusted_edges)

        update_parse_job(job_id, "completed", stats=stats)
    except Exception as e:
        update_parse_job(job_id, "failed", error_message=str(e))


@router.get("/{job_id}", response_model=ParseJob)
async def get_parse_job_status(job_id: int):
    job = get_parse_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Parse job not found")
    return job


@router.get("/{job_id}/summary", response_model=GraphSummary)
async def get_parse_job_summary(job_id: int):
    summary = get_graph_summary(job_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Parse job not found")
    return summary