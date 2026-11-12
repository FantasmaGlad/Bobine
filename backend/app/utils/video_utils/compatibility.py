"""Ce qu'il faut faire d'un média importé pour qu'il soit lisible partout (aucun, remux, transcodage)."""
from pathlib import Path
from app.utils.video_utils.container import is_faststart_mp4


# Codecs vidéo dont la robustesse a été validée sur le Wyse 5070.
# Restreint à H.264 pour l'instant : HEVC/VP9 ont été validés en lecture continue mais pas spécifiquement
# en boucle (un fond animé redémarre le décodeur toutes les quelques
# secondes, sollicitation plus dure qu'une lecture linéaire) — à élargir
# seulement après un vrai test de boucle sur le matériel cible.
COMPATIBLE_VIDEO_CODECS = {"h264"}


# Codecs supplémentaires validés pour une vidéo de COURS (lue une seule fois,
# en continu — jamais en boucle) : plus permissive que la liste stricte
# ci-dessus, réservée aux fonds animés. — avant ce
# correctif, `strict_video_codec=False` ne rétrécissait pas cette liste, il
# sautait la vérification du codec vidéo EN ENTIER (n'importe quel codec,
# même jamais testé sur ce matériel — AV1, MPEG-2, VC-1...— passait pour
# "compatible"). Un cours dans un codec hors de cette liste déclenche
# maintenant un réencodage à l'import, comme pour un fond animé non conforme,
# plutôt que d'être importé tel quel sans avertissement.
COMPATIBLE_COURSE_VIDEO_CODECS = COMPATIBLE_VIDEO_CODECS | {"hevc", "vp9"}


def check_compatibility(metadata: dict, file_path: str, strict_video_codec: bool = False) -> dict:
    """
    Vérifie la compatibilité de la vidéo par rapport aux règles de lecture directe du navigateur.
    Retourne si le fichier est directement lisible ou s'il nécessite une normalisation.

    `strict_video_codec` : à
    activer uniquement pour les fonds animés, qui bouclent indéfiniment et
    sollicitent donc le décodeur matériel bien plus durement (redémarrage à
    chaque tour) qu'une vidéo de cours lue une seule fois en continu. Pour un
    cours (False), la liste blanche reste appliquée mais élargie à HEVC/VP9
    (COMPATIBLE_COURSE_VIDEO_CODECS) plutôt que d'être ignorée : un codec
    jamais validé sur ce matériel déclenche quand même un réencodage.
    """
    if metadata["is_drm"]:
        return {
            "is_compatible": False,
            "needs_normalization": False,
            "actions": [],
            "error": "Le fichier vidéo est protégé par DRM (FairPlay, etc.) et ne peut pas être lu."
        }

    ext = Path(file_path).suffix.lower()
    is_mp4_container = ext in (".mp4", ".m4v")
    is_audio_compatible = metadata["audio_codec"] is None or metadata["audio_codec"] == "aac"
    # Un flux vidéo absent (audio seul) n'a rien à réencoder ; sinon le codec
    # doit être dans la liste blanche correspondante (stricte pour un fond
    # animé, élargie HEVC/VP9 pour un cours — jamais totalement ignorée).
    allowed_video_codecs = COMPATIBLE_VIDEO_CODECS if strict_video_codec else COMPATIBLE_COURSE_VIDEO_CODECS
    is_video_codec_compatible = metadata["codec"] is None or metadata["codec"] in allowed_video_codecs

    needs_audio_recode = metadata["audio_codec"] is not None and metadata["audio_codec"] != "aac"
    needs_container_recode = not is_mp4_container
    needs_video_recode = not is_video_codec_compatible
    # un conteneur/codec par ailleurs déjà compatible peut quand même
    # avoir son atome moov en fin de fichier (export non "web optimisé") — un
    # défaut invisible en local mais bloquant sur le réseau. Seul un
    # conteneur MP4 est concerné (un remux container->mp4 ci-dessous produit
    # déjà du faststart via normalize_video).
    needs_faststart_remux = (
        is_mp4_container and metadata.get("codec") is not None and not is_faststart_mp4(file_path)
    )

    actions = []
    if needs_video_recode:
        actions.append("recode_video")
    if needs_audio_recode:
        actions.append("recode_audio")
    if needs_container_recode:
        actions.append("recode_container")
    if needs_faststart_remux and not needs_container_recode:
        actions.append("remux_faststart")

    is_compatible = is_mp4_container and is_audio_compatible and is_video_codec_compatible

    return {
        "is_compatible": is_compatible,
        "needs_normalization": len(actions) > 0,
        "actions": actions,
        "error": None
    }
