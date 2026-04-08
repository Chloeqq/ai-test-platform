from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.page_object_recorder import (
    RecorderSessionCreateCasePayload,
    RecorderSessionCreate,
    RecorderSessionHeartbeatPayload,
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


@router.get("/sessions/{session_id}")
def get_recorder_session(
    session_id: str,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = page_object_recorder_service.get_recorder_session(db, session_id=session_id)
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
