"""Attente de la fin de copie d'un fichier déposé."""
import os
import time


def wait_for_file_to_copy(file_path: str, stable_secs: int = 3, timeout: int = 300) -> bool:
    """
    Attend que la taille du fichier se stabilise (indiquant que la copie/l'upload est terminé).
    """
    last_size = -1
    stable_since = 0
    start_time = time.time()

    while time.time() - start_time < timeout:
        if not os.path.exists(file_path):
            time.sleep(0.5)
            continue

        try:
            current_size = os.path.getsize(file_path)
        except OSError:
            time.sleep(0.5)
            continue

        if current_size == last_size and current_size > 0:
            stable_since += 1
            if stable_since >= stable_secs:
                return True
        else:
            last_size = current_size
            stable_since = 0

        time.sleep(1)

    return False
