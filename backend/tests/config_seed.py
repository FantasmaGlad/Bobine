from datetime import datetime, timezone

from app.database import SessionLocal, init_db
from app.models import (
    AudioCourse, AudioPlaylist, AudioPlaylistItem, AudioTrack, Background, ImportSource, OverrideAction, Playlist,
    PlaylistItem, RadioAnnouncement, RadioAnnouncementRule, RadioAnnouncementRuleType, RadioPlaylist,
    RadioPlaylistItem, RadioTag, RadioTrack, Schedule, ScheduleOverride, ScheduleTargetType, ScheduleType, Video,
)

MODELS = (
    ScheduleOverride, Schedule, AudioPlaylistItem, AudioPlaylist, AudioTrack, AudioCourse, PlaylistItem, Playlist,
    RadioPlaylistItem, RadioPlaylist, RadioAnnouncementRule, RadioAnnouncement, Video, Background,
)


def clean():
    with SessionLocal() as db:
        for model in MODELS + (RadioTrack, RadioTag):
            db.query(model).delete()
        db.commit()


def seed():
    init_db()
    clean()
    with SessionLocal() as db:
        background = Background(file_path="/media/fonds/lagon.mp4", title="Lagon")
        video = Video(file_path="/media/videos/rpm-110.mp4", title="RPM 110", program="RPM", release="110",
                      source=ImportSource.upload)
        db.add_all([background, video])
        db.flush()
        playlist = Playlist(name="Lundi soir")
        playlist.items = [PlaylistItem(video_id=video.id, position=0)]
        twin = Playlist(name="Lundi soir")
        course = AudioCourse(title="Échauffement", program="BODYPUMP", release="120")
        db.add_all([playlist, twin, course])
        db.flush()
        track = AudioTrack(audio_course_id=course.id, number=1, title="Warm Up", file_path="/media/audio/bp120-01.mp3",
                           position=0)
        db.add(track)
        db.flush()
        mix = AudioPlaylist(name="Mix pump")
        mix.items = [AudioPlaylistItem(audio_track_id=track.id, position=0, background_id=background.id)]
        tag = RadioTag(name="calme")
        song = RadioTrack(file_path="/media/radio/aube.mp3", title="Aube", artist="Nils", album="Matin",
                          source=ImportSource.upload, tags=[tag])
        db.add_all([mix, song])
        db.flush()
        ambiance = RadioPlaylist(name="Ambiance", is_default=True)
        ambiance.items = [RadioPlaylistItem(radio_track_id=song.id, position=0)]
        db.add_all([
            ambiance,
            RadioAnnouncement(file_path="/media/rappels/bouteille.mp3", description="Pensez à votre bouteille"),
            RadioAnnouncementRule(rule_type=RadioAnnouncementRuleType.fixed_times, times_of_day='["09:00"]',
                                  target="both"),
        ])
        db.flush()
        schedule = Schedule(target_type=ScheduleTargetType.playlist, target_id=playlist.id,
                            schedule_type=ScheduleType.recurring, recurrence_rule='{"days_of_week": [0], "time": "18:30"}',
                            channel="cable")
        schedule.overrides = [ScheduleOverride(occurrence_date=datetime(2026, 12, 21, tzinfo=timezone.utc),
                                               action=OverrideAction.cancelled)]
        db.add(schedule)
        db.commit()


def drop_twin():
    with SessionLocal() as db:
        twins = db.query(Playlist).filter(Playlist.name == "Lundi soir").order_by(Playlist.id).all()
        db.delete(twins[-1])
        db.commit()
