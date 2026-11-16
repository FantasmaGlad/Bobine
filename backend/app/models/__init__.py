"""Modèles SQLAlchemy de Bobine, un module par domaine ; importer ce paquet enregistre toutes les tables."""

from .audio import AudioCourse, AudioPlaylist, AudioPlaylistItem, AudioTrack, Background
from .base import Base, ImportSource, OverrideAction, RadioAnnouncementRuleType, RadioCoverSource, ScheduleTargetType, ScheduleType, UidMixin
from .radio import RadioAnnouncement, RadioAnnouncementRule, RadioPlaylist, RadioPlaylistItem, RadioTag, RadioTrack, radio_track_tags
from .runtime import ActivityLog, CourseRating, PlaybackSession, PlaybackState, ScheduledLaunch, Setting, SystemMetricsHistory
from .schedule import Schedule, ScheduleOverride
from .storage import ExternalVolume, StorageImport
from .video import Playlist, PlaylistItem, Video, VideoChapter, VideoSubtitle

__all__ = [
    "Base",
    "UidMixin",
    "ImportSource",
    "ScheduleType",
    "ScheduleTargetType",
    "OverrideAction",
    "RadioCoverSource",
    "RadioAnnouncementRuleType",
    "ExternalVolume",
    "StorageImport",
    "Video",
    "VideoSubtitle",
    "VideoChapter",
    "Playlist",
    "PlaylistItem",
    "Background",
    "AudioCourse",
    "AudioTrack",
    "AudioPlaylist",
    "AudioPlaylistItem",
    "radio_track_tags",
    "RadioTrack",
    "RadioTag",
    "RadioPlaylist",
    "RadioPlaylistItem",
    "RadioAnnouncement",
    "RadioAnnouncementRule",
    "Schedule",
    "ScheduleOverride",
    "PlaybackState",
    "ScheduledLaunch",
    "Setting",
    "ActivityLog",
    "CourseRating",
    "PlaybackSession",
    "SystemMetricsHistory",
]
