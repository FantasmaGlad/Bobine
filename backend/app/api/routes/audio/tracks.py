"""API des pistes d'un cours audio : ordre et modification."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AudioCourse, AudioTrack

from .schemas import AudioCourseDetailResponse, AudioTrackResponse, AudioTrackUpdate, TrackReorderInput

router = APIRouter()


@router.put("/{course_id}/tracks/reorder", response_model=AudioCourseDetailResponse)
def reorder_tracks(course_id: int, payload: TrackReorderInput, db: Session = Depends(get_db)):
    """Réordonnancement des pistes par glisser-déposer."""
    course = db.query(AudioCourse).filter(AudioCourse.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Cours audio non trouvé")

    tracks_by_id = {t.id: t for t in course.tracks}
    if set(payload.track_ids) != set(tracks_by_id.keys()):
        raise HTTPException(status_code=422, detail="La liste fournie ne correspond pas exactement aux pistes du cours")

    for position, track_id in enumerate(payload.track_ids):
        tracks_by_id[track_id].position = position

    db.commit()
    db.refresh(course)
    return course


@router.put("/{course_id}/tracks/{track_id}", response_model=AudioTrackResponse)
def update_audio_track(
    course_id: int,
    track_id: int,
    payload: AudioTrackUpdate,
    db: Session = Depends(get_db),
):
    course = db.query(AudioCourse).filter(AudioCourse.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Cours audio non trouvé")
    track = (
        db.query(AudioTrack)
        .filter(AudioTrack.id == track_id, AudioTrack.audio_course_id == course_id)
        .first()
    )
    if not track:
        raise HTTPException(status_code=404, detail="Piste audio non trouvée")

    if payload.title is not None and payload.title.strip():
        track.title = payload.title.strip()
    if payload.number is not None:
        track.number = payload.number
    if payload.clear_background:
        track.background_id = None
    elif payload.background_id is not None:
        track.background_id = payload.background_id

    db.commit()
    db.refresh(track)
    return track
