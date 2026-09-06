"""Point d'entrée figé par PyInstaller en `BobineBackend.exe` (cf.
`packaging/windows/bobine.spec`). Équivalent de
`uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1` en
développement, mais invoqué programmatiquement : `python -m uvicorn`
dépend d'un point d'entrée console-script qui n'existe plus une fois le
tout figé dans un seul exécutable.

Import direct de `app.main:app` (plutôt que la chaîne `"app.main:app"`
qu'accepte aussi `uvicorn.run`) : PyInstaller analyse statiquement les
imports pour décider quoi embarquer — une chaîne de caractères passée à
`uvicorn.run` ne lui apprend rien, et le paquet `app` se retrouvait
absent du binaire figé (`ModuleNotFoundError: No module named 'app'`,
constaté à l'exécution réelle). Un objet d'app importé directement reste
valide avec `workers=1` (aucun rechargement à chaud ni sous-process
supplémentaire à réimporter — seul `workers > 1` exige une chaîne, pour
que chaque worker puisse réimporter l'app dans son propre process).
"""

import multiprocessing

import uvicorn

from app.main import app

if __name__ == "__main__":
    # No-op sur Linux/hors gel (cf. doc Python) ; requis sur Windows/macOS
    # frozen si une dépendance venait à utiliser `multiprocessing` en interne
    # (aucun usage direct ici avec workers=1, mais un import manquant de ce
    # garde-fou provoquerait un boot loop silencieux si jamais le cas se
    # présentait — coût nul de le poser dès maintenant).
    multiprocessing.freeze_support()
    uvicorn.run(app, host="0.0.0.0", port=8000, workers=1)
