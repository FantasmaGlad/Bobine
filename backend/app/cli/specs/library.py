from __future__ import annotations

from .model import Arg, Call, Spec
from .route import route
from .fields import provided


SPECS: tuple[Spec, ...] = (
    Spec("library", "set", "modifier titre, programme, release ou description d'une vidéo",
         lambda c, a: Call("PUT", f"/api/videos/{a.video_id}", provided(a, ("title", "program", "release", "description"))),
         ("PUT /api/videos/{video_id}",),
         (Arg(("video_id",), "identifiant de la vidéo", int), Arg(("--title",)), Arg(("--program",)), Arg(("--release",)), Arg(("--description",))),
         lambda p, a: f"Vidéo {a.video_id} mise à jour : {p.get('title')}", needs_one_of=("title", "program", "release", "description")),
    Spec("library", "rm", "supprimer une vidéo et son fichier (elle quitte aussi les playlists et le planning)",
         lambda c, a: Call("DELETE", f"/api/videos/{a.video_id}"), ("DELETE /api/videos/{video_id}",),
         (Arg(("video_id",), "identifiant de la vidéo", int),),
         lambda p, a: f"Vidéo {a.video_id} supprimée.", confirm="Supprimer la vidéo {video_id} et son fichier ?"),
    route("library", "programs", "GET", "/api/videos/programs", "programmes connus"),
    route("library", "rendition", "POST", "/api/videos/{video_id}/web-rendition", "créer la version web légère"),
    route("library", "rendition-rm", "DELETE", "/api/videos/{video_id}/web-rendition", "retirer la version web légère"),
    route("library", "thumbnail", "PUT", "/api/videos/{video_id}/thumbnail", "remplacer la miniature", files=("file",)),
    route("library", "normalize", "POST", "/api/videos/{video_id}/normalize", "réencoder pour une lecture universelle"),
    route("library", "subtitles", "GET", "/api/videos/{video_id}/subtitles", "lister les sous-titres"),
    route("library", "subtitle-add", "POST", "/api/videos/{video_id}/subtitles", "ajouter des sous-titres .srt ou .vtt",
          files=("file",), body=("language_code", "language_label")),
    route("library", "subtitle-rm", "DELETE", "/api/videos/{video_id}/subtitles/{subtitle_id}", "retirer des sous-titres",
          confirm="Retirer les sous-titres {subtitle_id} ?"),
    route("library", "chapters", "GET", "/api/videos/{video_id}/chapters", "lister les chapitres"),
    route("library", "chapters-set", "PUT", "/api/videos/{video_id}/chapters", "remplacer les chapitres",
          body=("chapters:json",), pos=("chapters",)),
    route("library", "chapters-import", "POST", "/api/videos/{video_id}/chapters/import", "importer des chapitres d'un fichier",
          files=("file",)),
    route("library", "chapters-embedded", "POST", "/api/videos/{video_id}/chapters/from-file", "lire les chapitres du fichier vidéo"),
    route("library", "chapters-export", "GET", "/api/videos/{video_id}/chapters/export", "exporter les chapitres"),
)
