"""Ambiance radio : playlist par défaut de chaque sortie, lancement, retour à l'ambiance."""

import logging

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import (
    RadioPlaylist,
    RadioTrack,
    Setting,
)
from app.radio_manager import DEFAULT_RADIO_CHANNEL, get_all_radio_managers, get_radio_manager, normalize_radio_channel

logger = logging.getLogger(__name__)


def radio_track_dict(track) -> dict:
    """Forme d'une piste radio dans l'état du RadioPlaybackManager (`order`,
    `current_track`, file d'attente) : source UNIQUE, partagée avec
    api/routes/playback.py (les deux copies d'avant dérivaient l'une de l'autre).
    Le style (`genre`) sert à l'affichage de la file « À suivre »."""
    return {
        "id": track.id,
        "title": track.title,
        "artist": track.artist,
        "album": track.album,
        "genre": track.genre,
        "duration_seconds": track.duration_seconds,
        "cover_url": f"/radio/tracks/{track.id}/cover" if track.cover_path else None,
        # Support externe : permet au moteur de sauter un morceau dont le support est débranché (registre en mémoire).
        "storage_id": getattr(track, "storage_id", None),
    }


def radio_default_playlist_key(radio_channel: str) -> str:
    """Clé `settings` de l'ambiance par défaut d'UNE sortie radio (aucune
    migration de schéma : la table `settings` est une simple paire clé/valeur)."""
    return f"radio_default_playlist_id_{normalize_radio_channel(radio_channel)}"


def get_radio_default_playlist_override(db: Session, radio_channel: str) -> int | None:
    """Identifiant de l'ambiance propre à la sortie, ou None si aucune n'a été choisie."""
    row = db.query(Setting).filter(Setting.key == radio_default_playlist_key(radio_channel)).first()
    if row is None or not row.value:
        return None
    try:
        return int(row.value)
    except (TypeError, ValueError):
        return None


def set_radio_default_playlist_override(db: Session, radio_channel: str, playlist_id: int | None) -> None:
    """Enregistre (ou efface, avec None) l'ambiance propre à une sortie."""
    key = radio_default_playlist_key(radio_channel)
    row = db.query(Setting).filter(Setting.key == key).first()
    if playlist_id is None:
        if row is not None:
            db.delete(row)
    elif row is not None:
        row.value = str(playlist_id)
    else:
        db.add(Setting(key=key, value=str(playlist_id)))
    db.commit()


def resolve_radio_default_playlist(db: Session, radio_channel: str) -> RadioPlaylist | None:
    """Ambiance par défaut d'une sortie : le choix propre à la sortie s'il existe
    encore, sinon la playlist marquée `is_default` (comportement d'avant les deux
    sorties, donc aucune migration), sinon None (repli : toute la bibliothèque)."""
    override_id = get_radio_default_playlist_override(db, radio_channel)
    if override_id is not None:
        playlist = db.query(RadioPlaylist).filter(RadioPlaylist.id == override_id).first()
        if playlist is not None:
            return playlist
    return db.query(RadioPlaylist).filter(RadioPlaylist.is_default == True).first()  # noqa: E712


def is_cable_output_radio(db: Session) -> bool:
    """Vrai si la sortie câblée est actuellement basculée sur la radio."""
    from app.api.routes.settings.display import get_display_output_value

    return get_display_output_value(db, "cable") == "radio"


def _radio_output_is_audible(db: Session, radio_channel: str) -> bool:
    """La sortie réseau est toujours « audible » (n'importe quel appareil peut
    ouvrir son poste) ; la sortie câblée ne diffuse la radio que lorsque
    l'écran câblé est basculé sur Radio."""
    if normalize_radio_channel(radio_channel) != "radio_cable":
        return True
    return is_cable_output_radio(db)


async def _launch_radio_target(
    db: Session, playlist_id: int, radio_channel: str = DEFAULT_RADIO_CHANNEL, *, start_paused: bool = False,
) -> None:
    """Lance une playlist radio EN BOUCLE sur UNE sortie : utilisé aussi
    bien par l'auto-boot (ambiance par défaut) que par une programmation
    Planning radio (fenêtre ou 24/7) — les deux doivent boucler plutôt que
    s'arrêter en silence en fin de playlist. `start_paused` charge la playlist
    sans la lancer (sortie qui ne diffuse pas la radio en ce moment)."""
    playlist = db.query(RadioPlaylist).filter(RadioPlaylist.id == playlist_id).first()
    if not playlist:
        logger.warning(f"Cible programmée introuvable : playlist radio {playlist_id}")
        return
    sorted_items = sorted(playlist.items, key=lambda item: item.position)
    tracks = [radio_track_dict(item.track) for item in sorted_items if item.track]
    if not tracks:
        logger.warning(f"Playlist radio {playlist_id} vide, rien à lancer")
        return
    await get_radio_manager(radio_channel).load_playlist(
        playlist.id, playlist.name, tracks, repeat="playlist", start_paused=start_paused,
    )


async def _launch_radio_shuffle_all(
    db: Session, radio_channel: str = DEFAULT_RADIO_CHANNEL, *, start_paused: bool = False,
) -> str | None:
    """Ambiance par défaut « de secours » : joue TOUTE la bibliothèque radio,
    mélangée et en boucle infinie. Utilisé quand AUCUNE ambiance n'est définie
    pour la sortie, pour ne jamais laisser la radio muette.

    Playlist VIRTUELLE (playlist_id=None, comme la commande `radio_shuffle_all`
    de api/routes/playback.py) : rien n'est persisté en base, la liste est
    recomposée à chaque lancement — elle reflète donc toujours l'état courant de
    la bibliothèque, sans playlist figée à resynchroniser à chaque import.
    Renvoie le nom lancé, ou None si la bibliothèque est vide."""
    tracks = [radio_track_dict(t) for t in db.query(RadioTrack).all()]
    if not tracks:
        return None
    # shuffle=True + repeat="playlist" : aléatoire ET boucle infinie (deux
    # réglages indépendants côté RadioPlaybackManager), comme `radio_shuffle_all`.
    await get_radio_manager(radio_channel).load_playlist(
        None, "Toute la bibliothèque", tracks, shuffle=True, repeat="playlist", start_paused=start_paused,
    )
    return "Toute la bibliothèque"


async def start_radio_ambiance(
    db: Session, radio_channel: str = DEFAULT_RADIO_CHANNEL, *, start_paused: bool = False,
) -> str | None:
    """Charge l'ambiance par défaut d'une sortie (choix propre à la sortie, sinon
    playlist `is_default`, sinon toute la bibliothèque en aléatoire). Renvoie le
    nom lancé, ou None si rien n'est disponible. Point UNIQUE partagé par
    l'auto-démarrage, la fin de fenêtre de planning et la bascule de la sortie
    câblée vers Radio."""
    playlist = resolve_radio_default_playlist(db, radio_channel)
    if playlist is not None:
        await _launch_radio_target(db, playlist.id, radio_channel, start_paused=start_paused)
        return playlist.name
    return await _launch_radio_shuffle_all(db, radio_channel, start_paused=start_paused)


async def activate_radio_output(db: Session, radio_channel: str) -> None:
    """Rend une sortie radio audible : reprend une lecture en pause, ou démarre
    l'ambiance si le moteur est à l'arrêt. Ne touche pas à une lecture en cours."""
    manager = get_radio_manager(radio_channel)
    state = manager.state["state"]
    if state == "idle":
        name = await start_radio_ambiance(db, radio_channel)
        if name is None:
            logger.info(f"Sortie {manager.channel} : bibliothèque radio vide, rien à lancer")
    elif state == "paused":
        await manager.play()


async def autostart_default_radio_playlist() -> None:
    """Auto-démarrage au boot : si un moteur radio est au repos et
    `radio_autostart_on_boot` est actif, charge son ambiance par défaut. À
    appeler une fois au démarrage du service — si une lecture est déjà en
    cours (ex. relancée par une commande arrivée entre-temps), l'état n'est
    plus "idle" et cet appel ne fait rien.

    La sortie réseau démarre comme avant. La sortie câblée ne démarre QUE si
    l'écran câblé est basculé sur Radio : jamais de musique sans écran radio
    pour la porter.

    CORRECTIF historique : avec 4 workers
    uvicorn, cette fonction était appelée par CHACUN à son propre démarrage,
    calculant chacun son propre tirage aléatoire — d'où des changements de
    piste qui semblaient incessants. Process unique (voir
    `docs/ARCHITECTURE.md` §1) : `main.py` n'appelle plus
    cette fonction qu'une seule fois, le problème ne peut plus se poser."""
    from app.config import settings as runtime_settings

    if not runtime_settings.radio_autostart_on_boot:
        return
    db = SessionLocal()
    try:
        for radio_channel, manager in get_all_radio_managers().items():
            if manager.state["state"] != "idle":
                continue
            if not _radio_output_is_audible(db, radio_channel):
                continue
            name = await start_radio_ambiance(db, radio_channel)
            if name is not None:
                logger.info(f"Auto-démarrage radio ({radio_channel}) : « {name} »")
            else:
                logger.info(f"Auto-démarrage radio ({radio_channel}) : bibliothèque vide, rien à lancer")
    finally:
        db.close()


async def _revert_radio_to_default(db: Session, radio_channel: str = DEFAULT_RADIO_CHANNEL) -> None:
    """Fin de fenêtre radio : retour à l'ambiance par défaut de la sortie, ou
    arrêt si rien n'est disponible (bibliothèque vide). Une sortie qui ne
    diffuse pas la radio en ce moment est rechargée en pause."""
    paused = not _radio_output_is_audible(db, radio_channel)
    if await start_radio_ambiance(db, radio_channel, start_paused=paused) is None:
        await get_radio_manager(radio_channel).stop()
