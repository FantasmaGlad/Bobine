"""API des cours audio : liste, pistes, programmes, fiche, modification et suppression."""

import logging
import os
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, contains_eager, joinedload, selectinload

from app.api.paging import Window, window
from app.api.responses import Message
from app.database import get_db
from app.models import AudioCourse, AudioTrack

from .schemas import AudioCourseDetailResponse, AudioCourseResponse, AudioCourseUpdate, AudioTrackWithCourseResponse, summary

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=List[AudioCourseResponse])
def list_audio_courses(db: Session = Depends(get_db), page: Window = Depends(window)):
    courses = page.rows(
        db.query(AudioCourse)
        .options(selectinload(AudioCourse.tracks), joinedload(AudioCourse.background))
        .order_by(AudioCourse.imported_at.desc(), AudioCourse.id.desc())
    )
    return [summary(c) for c in courses]


@router.get("/tracks", response_model=List[AudioTrackWithCourseResponse])
def list_all_tracks(db: Session = Depends(get_db), page: Window = Depends(window)):
    """Toutes les pistes de tous les cours audio, à plat, avec leur contexte de cours d'origine."""
    tracks = page.rows(
        db.query(AudioTrack)
        .join(AudioCourse, AudioTrack.audio_course_id == AudioCourse.id)
        .options(contains_eager(AudioTrack.course), joinedload(AudioTrack.background))
        .order_by(AudioCourse.title.asc(), AudioTrack.position.asc(), AudioTrack.id.asc())
    )
    return [
        {
            "id": t.id,
            "number": t.number,
            "title": t.title,
            "duration_seconds": t.duration_seconds,
            "course_id": t.course.id,
            "course_title": t.course.title,
            "course_program": t.course.program,
            "available": t.available,
            "background_id": t.background_id,
            "background_title": t.background_title,
            "background_is_image": t.background_is_image,
        }
        for t in tracks
    ]


@router.get("/programs", response_model=List[str])
def list_audio_programs(db: Session = Depends(get_db)):
    """Catégories (programmes) réellement présentes parmi les cours audio, triées."""
    rows = (
        db.query(AudioCourse.program)
        .filter(AudioCourse.program.isnot(None), AudioCourse.program != "")
        .distinct()
        .all()
    )
    return sorted({r[0] for r in rows}, key=str.casefold)


@router.get("/{course_id}", response_model=AudioCourseDetailResponse)
def get_audio_course(course_id: int, db: Session = Depends(get_db)):
    course = (
        db.query(AudioCourse)
        .options(selectinload(AudioCourse.tracks).joinedload(AudioTrack.background))
        .filter(AudioCourse.id == course_id)
        .first()
    )
    if not course:
        raise HTTPException(status_code=404, detail="Cours audio non trouvé")
    return course


@router.put("/{course_id}", response_model=AudioCourseDetailResponse)
def update_audio_course(course_id: int, payload: AudioCourseUpdate, db: Session = Depends(get_db)):
    course = db.query(AudioCourse).filter(AudioCourse.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Cours audio non trouvé")

    if payload.title is not None and payload.title.strip():
        course.title = payload.title.strip()
    if payload.program is not None:
        course.program = payload.program
    if payload.release is not None:
        course.release = payload.release
    if payload.clear_background:
        course.background_id = None
    elif payload.background_id is not None:
        course.background_id = payload.background_id

    db.commit()
    db.refresh(course)
    return course


@router.delete("/{course_id}", response_model=Message)
def delete_audio_course(course_id: int, db: Session = Depends(get_db)):
    course = db.query(AudioCourse).filter(AudioCourse.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Cours audio non trouvé")

    for track in course.tracks:
        if track.file_path and track.storage_id is None:
            p = Path(track.file_path)
            if p.exists():
                try:
                    os.remove(p)
                    if p.parent.exists() and not any(p.parent.iterdir()):
                        p.parent.rmdir()
                except Exception as e:
                    logger.error(f"Impossible de supprimer la piste {p}: {e}")

    db.delete(course)
    db.commit()
    return {"message": "Cours audio supprimé avec succès"}
