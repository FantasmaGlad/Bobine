"""Codes de refus de l'assistant de formatage : un code stable, un statut HTTP et un message simple.

L'interface traduit chaque code (`storage.format.refusal.<code>`) ; le message français ci-dessous sert de repli et au
journal. Aucun message ne contient de chemin système, de numéro de série ni de secret."""

from __future__ import annotations

from typing import Any

from app.devices.base import DeviceError

REFUSALS: dict[str, tuple[int, str]] = {
    "format_unsupported_platform": (501, "Le formatage n'est pas disponible sur cette plateforme."),
    "format_tool_missing": (501, "Un composant du système manque pour formater (udisks2 ou l'outil de ce format)."),
    "format_not_found": (404, "Support introuvable : il a peut-être été retiré."),
    "format_not_allowed": (409, "Ce support n'est pas autorisé au formatage dans cet environnement d'essai."),
    "format_phone": (409, "Un téléphone ou une tablette ne se formate pas depuis Bobine."),
    "format_not_removable": (409, "Seuls les supports amovibles (clé USB, carte SD, disque USB) peuvent être préparés."),
    "format_internal_disk": (409, "Ce disque est interne à la machine : Bobine ne le formate jamais."),
    "format_system_disk": (409, "Ce disque porte le système ou un montage système : Bobine ne le formate jamais."),
    "format_bobine_data": (409, "Ce support contient ou héberge les dossiers de données de Bobine : il ne peut pas être formaté."),
    "format_library_registered": (409, "Ce support est une bibliothèque externe enregistrée : désenregistrez-la d'abord."),
    "format_in_use": (409, "Un import, un export ou une lecture utilise ce support : attendez la fin ou annulez-le."),
    "format_busy_operation": (409, "Un autre formatage est déjà en cours : une seule opération destructive à la fois."),
    "format_read_only": (409, "Ce support est protégé en écriture (verrou matériel ou lecture seule) : il ne peut pas être formaté."),
    "format_encrypted_stack": (409, "Ce support est chiffré ou fait partie d'un ensemble RAID/LVM : Bobine ne le formate pas."),
    "format_image_not_allowed": (409, "Les images disque ne sont pas formatables ici."),
    "format_too_small": (409, "Ce support est trop petit pour être utilisé comme espace de médias."),
    "format_fs_unavailable": (409, "Ce format n'est pas disponible sur cette machine."),
    "format_fs_unknown": (400, "Format inconnu."),
    "format_label_invalid": (400, "Cette étiquette n'est pas valable pour ce format."),
    "format_confirmation_mismatch": (400, "Le texte saisi ne correspond pas au nom du support."),
    "format_ack_missing": (400, "Cochez la case pour confirmer que tout sera effacé."),
    "format_too_early": (409, "Prenez le temps de relire : la confirmation n'est pas encore possible."),
    "format_token_missing": (400, "Autorisation de formatage absente : recommencez la préparation."),
    "format_token_unknown": (409, "Autorisation de formatage inconnue ou périmée : recommencez la préparation."),
    "format_token_expired": (409, "L'autorisation de formatage a expiré : recommencez la préparation."),
    "format_token_used": (409, "Cette autorisation a déjà servi : recommencez la préparation."),
    "format_token_owner": (409, "Cette autorisation a été délivrée à un autre appareil : recommencez la préparation."),
    "format_identity_changed": (409, "Le support a changé depuis le plan (branchement, retrait ou remplacement) : rien n'a été effacé, recommencez."),
    "format_pin_required": (401, "Saisissez le code PIN d'administration pour formater."),
    "format_pin_invalid": (401, "Code PIN incorrect."),
    "format_not_authorized": (403, "Le système refuse cette opération (autorisation polkit manquante pour ce compte)."),
    "format_busy_mounted": (409, "Le support est encore utilisé par un autre programme (gestionnaire de fichiers, lecture) : fermez-le puis recommencez. Rien n'a été effacé."),
    "format_cannot_cancel": (409, "Trop tard pour annuler : l'effacement a commencé."),
    "format_job_not_found": (404, "Opération introuvable."),
    "format_failed": (502, "Le formatage a échoué."),
}


class FormatRefusal(DeviceError):
    """Refus (ou échec) de l'assistant de formatage ; `extra` transporte les actions proposées (ex. désenregistrer)."""

    def __init__(self, code: str, message: str | None = None, *, status: int | None = None, **extra: Any):
        default_status, default_message = REFUSALS.get(code, (409, "Opération de formatage refusée."))
        super().__init__(code, message or default_message, status or default_status)
        self.extra = extra
