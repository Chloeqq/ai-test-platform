from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.page_object import RecorderSessionBatchDeletePayload
from app.schemas.page_object_recorder import (
    RecorderSessionCreate,
    RecorderSessionCreateCasePayload,
    RecorderSessionHeartbeatPayload,
    RecorderSessionReplayPayload,
    RecorderSessionStopPayload,
)
from app.services import page_object_recorder_service

router = APIRouter(prefix="/api/page-objects/recorder", tags=["page-objects-recorder"])


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
def create_recorder_session(
    payload: RecorderSessionCreate,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = page_object_recorder_service.create_recorder_session(db, payload)
    return {"item": item}


@router.get("/sessions")
def list_recorder_sessions(
    project_code: str = Query(default="mall", min_length=2, max_length=20),
    client: str = Query(default="web", min_length=2, max_length=10),
    page_code: str = Query(default="", max_length=40),
    status_text: str = Query(default="", alias="status", max_length=20),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return page_object_recorder_service.list_recorder_sessions(
        db,
        project_code=project_code,
        client=client,
        page_code=page_code,
        status_text=status_text,
        limit=limit,
        offset=offset,
    )


@router.get("/sessions/{session_id}")
def get_recorder_session(
    session_id: str,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = page_object_recorder_service.get_recorder_session(db, session_id=session_id)
    return {"item": item}


@router.post("/sessions/batch/delete")
def batch_delete_recorder_sessions(
    payload: RecorderSessionBatchDeletePayload,
    project_code: str = Query(default="mall", min_length=2, max_length=20),
    client: str = Query(default="web", min_length=2, max_length=10),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = page_object_recorder_service.batch_delete_recorder_sessions(
        db,
        project_code=project_code,
        client=client,
        session_ids=payload.session_ids,
        delete_artifacts=payload.delete_artifacts,
    )
    return {"item": item}


@router.get("/sessions/{session_id}/playback")
def get_recorder_session_playback(
    session_id: str,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = page_object_recorder_service.get_recorder_session_playback(db, session_id=session_id)
    return {"item": item}


@router.post("/sessions/{session_id}/replay")
def replay_recorder_session(
    session_id: str,
    payload: RecorderSessionReplayPayload | None = None,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = page_object_recorder_service.replay_recorder_session(
        db,
        session_id=session_id,
        timeout_seconds=(payload.timeout_seconds if payload else 120),
    )
    return {"item": item}


@router.post("/sessions/{session_id}/heartbeat")
def heartbeat_recorder_session(
    session_id: str,
    payload: RecorderSessionHeartbeatPayload,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = page_object_recorder_service.heartbeat_recorder_session(db, session_id=session_id, payload=payload)
    return {"item": item}


@router.post("/sessions/{session_id}/stop")
def stop_recorder_session(
    session_id: str,
    payload: RecorderSessionStopPayload,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = page_object_recorder_service.stop_recorder_session(db, session_id=session_id, payload=payload)
    return item


@router.post("/artifacts/cleanup")
def cleanup_orphan_recorder_artifacts(
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = page_object_recorder_service.cleanup_orphan_recorder_artifacts(db)
    return {"item": item}


@router.post("/sessions/{session_id}/cases/draft", status_code=status.HTTP_201_CREATED)
def create_test_case_draft_from_recorder_session(
    session_id: str,
    payload: RecorderSessionCreateCasePayload,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = page_object_recorder_service.create_test_case_draft_from_session(
        db,
        session_id=session_id,
        payload=payload,
    )
    return {"item": item}
