"""Bibliothèque radio, étiquettes, playlists et annonces."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, ForeignKey, Integer, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, ExternalMediaMixin, ImportSource, RadioAnnouncementRuleType, RadioCoverSource, UidMixin, utcnow

radio_track_tags = Table(
    "radio_track_tags",
    Base.metadata,
    Column("radio_track_id", Integer, ForeignKey("radio_tracks.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("radio_tags.id", ondelete="CASCADE"), primary_key=True),
)


class RadioTrack(UidMixin, ExternalMediaMixin, Base):
    __uid_prefix__ = "rtk"
    """Un morceau de musique de la bibliothèque radio. Les
    champs de navigation (artiste/album/album_artist/genre) alimentent les vues
    « artiste/album » et « tags/genres » par regroupement dérivé — pas de tables
    Artiste/Album dédiées en v1."""
    __tablename__ = "radio_tracks"

    id: Mapped[int] = mapped_column(primary_key=True)
    file_path: Mapped[str] = mapped_column(unique=True)
    title: Mapped[str]
    artist: Mapped[str | None]
    album: Mapped[str | None]
    album_artist: Mapped[str | None]
    track_number: Mapped[int | None]
    disc_number: Mapped[int | None]
    year: Mapped[int | None]
    genre: Mapped[str | None]
    duration_seconds: Mapped[float | None]
    cover_path: Mapped[str | None]
    cover_source: Mapped[RadioCoverSource] = mapped_column(default=RadioCoverSource.none)
    source: Mapped[ImportSource]
    imported_at: Mapped[datetime] = mapped_column(default=utcnow)
    storage_id: Mapped[int | None] = mapped_column(ForeignKey("external_volumes.id", ondelete="SET NULL"), index=True)
    rel_path: Mapped[str | None]

    tags: Mapped[list["RadioTag"]] = relationship(secondary=radio_track_tags, back_populates="tracks", passive_deletes=True)


class RadioTag(UidMixin, Base):
    __uid_prefix__ = "tag"
    """Étiquette libre applicable aux morceaux radio :
    ambiance, tempo, occasion… saisie/gérée depuis l'admin, indépendante du
    `genre` ID3 porté par le morceau."""
    __tablename__ = "radio_tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)

    tracks: Mapped[list["RadioTrack"]] = relationship(secondary=radio_track_tags, back_populates="tags", passive_deletes=True)


class RadioPlaylist(UidMixin, Base):
    __uid_prefix__ = "rpl"
    """Playlist radio créée à la main. `is_default` désigne la
    playlist d'ambiance qui tourne en boucle 24/7 : une seule à la
    fois, garantie applicativement (aucune contrainte SQL). `cover_path` est
    optionnel — sinon l'UI dérive la pochette du premier morceau."""
    __tablename__ = "radio_playlists"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    is_default: Mapped[bool] = mapped_column(default=False)
    cover_path: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    items: Mapped[list["RadioPlaylistItem"]] = relationship(
        back_populates="playlist", order_by="RadioPlaylistItem.position", cascade="all, delete-orphan", passive_deletes=True
    )


class RadioPlaylistItem(Base):
    __tablename__ = "radio_playlist_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    playlist_id: Mapped[int] = mapped_column(ForeignKey("radio_playlists.id", ondelete="CASCADE"))
    radio_track_id: Mapped[int] = mapped_column(ForeignKey("radio_tracks.id", ondelete="CASCADE"))
    position: Mapped[int]

    playlist: Mapped[RadioPlaylist] = relationship(back_populates="items")
    track: Mapped[RadioTrack] = relationship()


class RadioAnnouncement(UidMixin, Base):
    __uid_prefix__ = "ann"
    """Rappel de bienséance intercalé dans la musique : fichier
    audio + `description` OBLIGATOIRE (le texte dit par l'annonce, pour gérer
    facilement le pool depuis l'admin). `enabled` retire un rappel du tirage
    sans le supprimer."""
    __tablename__ = "radio_announcements"

    id: Mapped[int] = mapped_column(primary_key=True)
    file_path: Mapped[str] = mapped_column(unique=True)
    description: Mapped[str]
    duration_seconds: Mapped[float | None]
    enabled: Mapped[bool] = mapped_column(default=True)
    imported_at: Mapped[datetime] = mapped_column(default=utcnow)


class RadioAnnouncementRule(UidMixin, Base):
    __uid_prefix__ = "rul"
    """Règle de déclenchement des rappels. Les règles définissent
    QUAND déclencher ; le rappel joué est tiré AU HASARD parmi les
    `radio_announcements` actifs.
    Seul le champ correspondant au `rule_type` est renseigné :
    - `every_n_tracks`  -> `n_tracks`      (insertion à la fin du morceau)
    - `every_x_minutes` -> `interval_minutes` (fondu immédiat / duck)
    - `fixed_times`     -> `times_of_day`  (JSON ["09:00","09:30"], fondu immédiat)
    """
    __tablename__ = "radio_announcement_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    rule_type: Mapped[RadioAnnouncementRuleType]
    n_tracks: Mapped[int | None]
    interval_minutes: Mapped[int | None]
    times_of_day: Mapped[str | None]
    enabled: Mapped[bool] = mapped_column(default=True)
    target: Mapped[str] = mapped_column(default="radio_network", server_default="radio_network")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
