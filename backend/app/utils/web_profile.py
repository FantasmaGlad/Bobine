"""Profil vidéo « lisible partout » et version compatible navigateurs.

Contexte : l'import d'un cours conserve le codec d'origine (H.264, HEVC, VP9 —
cf. `video_utils.COMPATIBLE_COURSE_VIDEO_CODECS`) : c'est voulu pour la sortie
HDMI locale (4K 60 i/s natif, décodage matériel). Mais un navigateur tiers
(Firefox sous Windows sans l'extension HEVC, Firefox pour Android, vieux
poste sans décodage matériel…) peut ne PAS savoir lire ce fichier. Plutôt que
de dégrader l'original, on garde les deux :

- l'ORIGINAL reste la référence (HDMI, kiosque local) ;
- une VERSION WEB (H.264 High 8 bits 4:2:0, ≤ 1080p, AAC stéréo, MP4 faststart)
  peut être produite en tâche de fond, à priorité réduite, et servie aux
  clients qui ne savent pas décoder l'original (`GET …/stream?accept=…`).

Ce module est PUR (aucune E/S) sauf `build_web_rendition_command`, qui ne fait
que construire la ligne de commande ffmpeg.
"""

from __future__ import annotations

# Un H.264 « 8 bits 4:2:0 » est décodé partout : c'est la définition du profil sûr.
_SAFE_CODEC = "h264"
_SAFE_PIX_FMTS = {"yuv420p", "yuvj420p", "nv12"}

# Identifiants annoncés par le client dans `?accept=` (voir
# frontend/src/lib/clientCodecSupport.ts) — un par capacité de décodage testée.
ACCEPT_H264 = "h264"
ACCEPT_HEVC = "hevc"
ACCEPT_VP9 = "vp9"
ACCEPT_AV1 = "av1"
ACCEPT_HIGH_BITDEPTH = "hi10"  # H.264 10 bits / 4:2:2 / 4:4:4

_CODEC_TO_ACCEPT = {"h264": ACCEPT_H264, "hevc": ACCEPT_HEVC, "vp9": ACCEPT_VP9, "av1": ACCEPT_AV1}


def web_playback_issues(
    codec: str | None,
    pix_fmt: str | None,
    width: int | None,
    height: int | None,
    fps: float | None,
) -> list[str]:
    """Raisons pour lesquelles le fichier peut ne pas être lu partout.

    Deux familles, volontairement distinguées par leur préfixe :
    - `decode:*` — le navigateur peut être INCAPABLE de décoder (codec, 10 bits,
      chroma 4:2:2/4:4:4) : seules ces raisons déclenchent la version web
      automatiquement ;
    - `perf:*` — décodable mais lourd (UHD à cadence élevée) : informatif
      (badge, diagnostic), jamais imposé à un client capable, pour ne pas
      dégrader le 4K 60 i/s de la sortie HDMI.
    Liste vide = profil sûr."""
    issues: list[str] = []
    if codec and codec.lower() != _SAFE_CODEC:
        issues.append(f"decode:codec-{codec.lower()}")
    if pix_fmt and pix_fmt.lower() not in _SAFE_PIX_FMTS:
        issues.append("decode:pixel-format")
    if height and fps:
        if height > 1080 and fps > 31:
            issues.append("perf:uhd-high-fps")
        elif fps > 60.5:
            issues.append("perf:high-fps")
    return issues


def client_can_decode(issues: list[str], accept: set[str]) -> bool:
    """Vrai si un client ayant annoncé `accept` sait décoder le fichier.
    Les raisons `perf:*` ne comptent pas (cf. `web_playback_issues`)."""
    for issue in issues:
        if not issue.startswith("decode:"):
            continue
        if issue.startswith("decode:codec-"):
            if _CODEC_TO_ACCEPT.get(issue.removeprefix("decode:codec-")) not in accept:
                return False
        elif issue == "decode:pixel-format" and ACCEPT_HIGH_BITDEPTH not in accept:
            return False
    return True


def parse_accept(raw: str | None) -> set[str] | None:
    """`?accept=h264,hevc` -> {"h264","hevc"} ; absent -> None (client qui ne
    négocie pas : on sert toujours l'original, comportement historique)."""
    if raw is None:
        return None
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def choose_rendition(
    *,
    issues: list[str],
    web_ready: bool,
    profile: str | None,
    accept: set[str] | None,
) -> str:
    """`"web"` ou `"original"`.

    `profile=web` / `profile=original` : choix explicite (préférence de
    l'utilisateur, diagnostic). Sinon, négociation par capacités annoncées.
    Sans version web prête on sert toujours l'original."""
    if profile == "original":
        return "original"
    if not web_ready:
        return "original"
    if profile == "web":
        return "web"
    if accept is not None and not client_can_decode(issues, accept):
        return "web"
    return "original"


def build_web_rendition_command(
    ffmpeg_bin: str,
    source: str,
    output: str,
    height: int | None,
    fps: float | None,
    has_audio: bool,
) -> list[str]:
    """Ligne de commande ffmpeg de la version web.

    H.264 High niveau 4.2, 8 bits 4:2:0, CRF 22 `veryfast` : lisible par tous
    les navigateurs, rapide à produire sur un CPU modeste ; réduite à 1080p
    si plus grande (le décodage logiciel d'un 4K est précisément ce qui fait
    ramer un poste sans accélération), cadence plafonnée à 60 i/s, audio AAC
    stéréo, `faststart` pour démarrer la lecture sans attendre la fin du
    téléchargement."""
    filters = []
    if height and height > 1080:
        filters.append("scale=-2:1080:flags=lanczos")
    if fps and fps > 60.5:
        filters.append("fps=60")
    command = [
        ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
        "-i", source,
        "-map", "0:v:0",
    ]
    if has_audio:
        command += ["-map", "0:a:0"]
    command += ["-sn", "-dn", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                "-profile:v", "high", "-level", "4.2", "-pix_fmt", "yuv420p"]
    if filters:
        command += ["-vf", ",".join(filters)]
    if has_audio:
        command += ["-c:a", "aac", "-b:a", "160k", "-ac", "2"]
    command += ["-movflags", "+faststart", output]
    return command
