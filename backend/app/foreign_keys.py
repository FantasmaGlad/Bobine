"""Clés étrangères SQLite : mise en conformité des bases existantes avant leur activation.

SQLite ne modifie jamais la contrainte d'une table existante : une base créée avant les règles `ondelete` du modèle
garde des clés sans action, qui refuseraient une suppression une fois les clés activées. Chaque table dont les
règles diffèrent du modèle est donc reconstruite (procédure documentée par SQLite : nouvelle table, copie, échange),
après retrait des lignes orphelines qu'une base sans contrôle a pu accumuler.
"""
from __future__ import annotations

import logging
import re
import sqlite3

from sqlalchemy import Engine, Table

from app.models import Base

logger = logging.getLogger(__name__)


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _expected_actions(table: Table) -> dict[tuple[str, str], str]:
    """(colonne, table parente) -> action attendue à la suppression du parent."""
    return {
        (fk.parent.name, fk.column.table.name): (fk.ondelete or "NO ACTION").upper()
        for fk in table.foreign_keys
    }


def _current_actions(cur: sqlite3.Cursor, table: str) -> dict[tuple[str, str], str]:
    return {(row[3], row[2]): row[6].upper() for row in cur.execute(f"PRAGMA foreign_key_list({_quote(table)})")}


def _remove_orphans(cur: sqlite3.Cursor, table: Table) -> int:
    """Retire les lignes qui visent un parent disparu : la colonne est vidée si elle le permet, la ligne supprimée sinon."""
    fixed = 0
    for fk in table.foreign_keys:
        child, col, parent, ref = table.name, fk.parent.name, fk.column.table.name, fk.column.name
        orphan = f"{_quote(col)} IS NOT NULL AND {_quote(col)} NOT IN (SELECT {_quote(ref)} FROM {_quote(parent)})"
        if fk.parent.nullable:
            cur.execute(f"UPDATE {_quote(child)} SET {_quote(col)} = NULL WHERE {orphan}")
        else:
            cur.execute(f"DELETE FROM {_quote(child)} WHERE {orphan}")
        fixed += cur.rowcount
    return fixed


_ACTION = r"(?:\s+ON\s+DELETE\s+(?:SET\s+NULL|SET\s+DEFAULT|CASCADE|RESTRICT|NO\s+ACTION))?"
_TABLE_FK = re.compile(r'FOREIGN\s+KEY\s*\(\s*"?(\w+)"?\s*\)\s*REFERENCES\s+"?(\w+)"?\s*\(\s*"?(\w+)"?\s*\)' + _ACTION, re.I)
_COLUMN_FK = re.compile(
    r'(?P<head>(?:^|[(,])\s*"?(?P<column>\w+)"?\s[^,()]*?)REFERENCES\s+"?(?P<parent>\w+)"?\s*\(\s*"?(?P<ref>\w+)"?\s*\)' + _ACTION,
    re.I,
)


def with_delete_rules(sql: str, actions: dict[tuple[str, str], str]) -> str:
    """Instruction de création de la table, avec la règle de suppression du modèle sur chacune de ses clés.

    Le reste de la définition (colonnes, types, contraintes) est gardé tel quel : une base ancienne peut contenir des
    valeurs que le modèle actuel refuserait, et ces données doivent survivre à la reconstruction."""
    def table_level(m: re.Match) -> str:
        column, parent, ref = m.group(1), m.group(2), m.group(3)
        return f"FOREIGN KEY({column}) REFERENCES {parent} ({ref}) ON DELETE {actions.get((column, parent), 'NO ACTION')}"

    def column_level(m: re.Match) -> str:
        action = actions.get((m.group("column"), m.group("parent")), "NO ACTION")
        return f"{m.group('head')}REFERENCES {m.group('parent')} ({m.group('ref')}) ON DELETE {action}"

    return _COLUMN_FK.sub(column_level, _TABLE_FK.sub(table_level, sql))


def _rebuild(cur: sqlite3.Cursor, table: Table) -> None:
    """Recrée la table avec les règles de suppression du modèle, en gardant sa définition, ses données et ses index."""
    name = table.name
    temp = f"{name}__fk_rebuild"
    sql = cur.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)).fetchone()[0]
    indexes = [row[0] for row in cur.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'index' AND tbl_name = ? AND sql IS NOT NULL", (name,)
    )]
    ddl = with_delete_rules(sql, _expected_actions(table))
    ddl = re.sub(r'^\s*CREATE\s+TABLE\s+("[^"]+"|\S+)', f"CREATE TABLE {_quote(temp)}", ddl, count=1, flags=re.I)
    cur.execute(f"DROP TABLE IF EXISTS {_quote(temp)}")
    cur.execute(ddl)
    cur.execute(f"INSERT INTO {_quote(temp)} SELECT * FROM {_quote(name)}")
    cur.execute(f"DROP TABLE {_quote(name)}")
    cur.execute(f"ALTER TABLE {_quote(temp)} RENAME TO {_quote(name)}")
    for index_sql in indexes:
        cur.execute(index_sql)


# Vrai une fois la base alignée : les connexions suivantes activent alors le contrôle des clés (database.py). Une base
# qu'on n'a pas pu aligner reste sans contrôle plutôt que de refuser des suppressions ou d'empêcher le démarrage.
enforced = False


def align_foreign_keys(engine: Engine) -> None:
    """Met les tables existantes en conformité avec les clés du modèle, puis active le contrôle. Idempotent ; ne fait
    rien sur une base neuve. Un échec est journalisé et laisse la base telle qu'elle était, sans contrôle des clés."""
    global enforced
    try:
        _align(engine)
        enforced = True
    except Exception:
        logger.exception("Clés étrangères non alignées : la base reste sans contrôle des clés")
    finally:
        engine.dispose()  # les connexions déjà ouvertes suivent l'état d'avant : les suivantes suivront `enforced`


def suspend(engine: Engine) -> None:
    """Coupe le contrôle des clés avant de remplacer ou de migrer la base ; `align_foreign_keys` le rétablit."""
    global enforced
    enforced = False
    engine.dispose()


def _alignable(cur: sqlite3.Cursor, table: Table) -> bool:
    """Faux pour une table d'un schéma ancien qui n'a pas les colonnes de clé du modèle : elle reste telle quelle."""
    columns = {row[1] for row in cur.execute(f"PRAGMA table_info({_quote(table.name)})")}
    missing = sorted(fk.parent.name for fk in table.foreign_keys if fk.parent.name not in columns)
    if missing:
        logger.warning("Clés étrangères : table %s d'un schéma ancien (colonnes absentes : %s), laissée telle quelle",
                       table.name, ", ".join(missing))
    return not missing


def _align(engine: Engine) -> None:
    raw = engine.raw_connection()
    try:
        conn = raw.driver_connection
        previous = conn.isolation_level
        conn.isolation_level = None  # transactions explicites : les PRAGMA de clés ne s'appliquent qu'hors transaction
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_keys=OFF")
        existing = {row[0] for row in cur.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        tables = [
            t for t in Base.metadata.sorted_tables if t.name in existing and t.foreign_keys and _alignable(cur, t)
        ]
        try:
            cur.execute("BEGIN IMMEDIATE")
        except sqlite3.Error:
            conn.isolation_level = previous
            raise
        try:
            orphans = sum(_remove_orphans(cur, t) for t in tables)
            rebuilt = []
            for table in tables:
                if _current_actions(cur, table.name) != _expected_actions(table):
                    _rebuild(cur, table)
                    rebuilt.append(table.name)
            # Contrôle limité aux tables du modèle : une table d'un schéma ancien garde ses lignes et ses clés.
            problems = [row for t in tables for row in cur.execute(f"PRAGMA foreign_key_check({_quote(t.name)})")]
            if problems:
                raise RuntimeError(f"clés étrangères incohérentes après migration : {problems[:5]}")
            cur.execute("COMMIT")
        except Exception:
            cur.execute("ROLLBACK")
            raise
        finally:
            conn.isolation_level = previous
        if orphans or rebuilt:
            logger.info("Clés étrangères : %d ligne(s) orpheline(s) corrigée(s), tables reconstruites : %s",
                        orphans, ", ".join(rebuilt) or "aucune")
    finally:
        raw.close()
