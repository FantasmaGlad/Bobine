"""Enchaînement d'une playlist vidéo et attente entre deux cours."""
import asyncio
import logging
from app.storage.availability import media_available
from app.playback.constants import PlaybackStateEnum

logger = logging.getLogger(__name__)


class PlaylistMixin:
    async def load_playlist(
        self,
        playlist_id: int,
        playlist_name: str,
        playlist_items: list[dict],
        client_ts: float | None = None,
        scheduled: bool = False,
        start_index: int = 0,
        start_position: float = 0.0,
    ):
        """Lance une playlist à la vidéo `start_index` (la première, sauf reprise d'une programmation interrompue)."""
        self._cancel_waiting()

        self.state["playlist_id"] = playlist_id
        self.state["playlist_name"] = playlist_name
        self.state["playlist_items"] = playlist_items
        self.state["playlist_index"] = start_index
        self.state["playlist_waiting_remaining"] = None

        if not playlist_items or start_index >= len(playlist_items):
            await self.stop(client_ts)
            return

        first_item = playlist_items[start_index]
        await self.load(
            video_id=first_item["id"],
            title=first_item["title"],
            duration_seconds=first_item["duration_seconds"],
            program=first_item.get("program"),
            release=first_item.get("release"),
            client_ts=client_ts,
            keep_playlist=True,
            thumbnail_url=first_item.get("thumbnail_url"),
            description=first_item.get("description"),
            audio_channels=first_item.get("audio_channels"),
            audio_codec=first_item.get("audio_codec"),
            fps=first_item.get("fps"),
            bitrate_kbps=first_item.get("bitrate_kbps"),
            width=first_item.get("width"),
            height=first_item.get("height"),
            scheduled=scheduled,
            start_position=start_position,
        )

    async def _run_waiting_period(self):
        this_task = asyncio.current_task()
        try:
            remaining = self.state["playlist_waiting_remaining"] or 0.0
            while remaining > 0:
                await asyncio.sleep(1.0)
                if self._waiting_task is not this_task:
                    return
                remaining -= 1.0
                self.state["playlist_waiting_remaining"] = max(0.0, remaining)
                await self._emit("playlist_waiting_tick")

            if self._waiting_task is not this_task:
                return
            self._waiting_task = None
            await self._play_next_video()
        except asyncio.CancelledError:
            pass

    async def _play_next_video(self, client_ts: float | None = None):
        self._cancel_waiting()

        idx = self.state["playlist_index"]
        items = self.state["playlist_items"]
        if idx is None or items is None:
            await self.stop(client_ts)
            return

        next_idx = idx + 1
        while next_idx < len(items) and not media_available(items[next_idx].get("storage_id")):
            next_idx += 1
        if next_idx < len(items):
            self.state["playlist_index"] = next_idx
            next_item = items[next_idx]
            await self.load(
                video_id=next_item["id"],
                title=next_item["title"],
                duration_seconds=next_item["duration_seconds"],
                program=next_item.get("program"),
                release=next_item.get("release"),
                client_ts=client_ts,
                keep_playlist=True,
                thumbnail_url=next_item.get("thumbnail_url"),
                description=next_item.get("description"),
                audio_channels=next_item.get("audio_channels"),
                audio_codec=next_item.get("audio_codec"),
                fps=next_item.get("fps"),
                bitrate_kbps=next_item.get("bitrate_kbps"),
                width=next_item.get("width"),
                height=next_item.get("height"),
                scheduled=self.state.get("scheduled_launch", False),
            )
        else:
            await self.stop(client_ts)

    async def next_video(self, client_ts: float | None = None):
        """Passe immédiatement à la vidéo suivante de la playlist active."""
        if self.state["playlist_items"] is None or self.state["playlist_index"] is None:
            return
        await self._play_next_video(client_ts)

    async def previous_video(self, client_ts: float | None = None):
        """Revient immédiatement à la vidéo précédente de la playlist active."""
        idx = self.state["playlist_index"]
        items = self.state["playlist_items"]
        if idx is None or items is None or idx - 1 < 0:
            return

        prev_idx = idx - 1
        self.state["playlist_index"] = prev_idx
        prev_item = items[prev_idx]

        self._cancel_waiting()

        await self.load(
            video_id=prev_item["id"],
            title=prev_item["title"],
            duration_seconds=prev_item["duration_seconds"],
            program=prev_item.get("program"),
                release=prev_item.get("release"),
            client_ts=client_ts,
            keep_playlist=True,
            thumbnail_url=prev_item.get("thumbnail_url"),
            description=prev_item.get("description"),
            audio_channels=prev_item.get("audio_channels"),
            audio_codec=prev_item.get("audio_codec"),
            fps=prev_item.get("fps"),
            bitrate_kbps=prev_item.get("bitrate_kbps"),
            width=prev_item.get("width"),
            height=prev_item.get("height"),
            scheduled=self.state.get("scheduled_launch", False),
        )

    async def skip_waiting(self, client_ts: float | None = None):
        """Passe immédiatement le compte à rebours d'attente intercalée."""
        if self.state["state"] != PlaybackStateEnum.playlist_waiting.value:
            return
        await self._play_next_video(client_ts)
