#!/usr/bin/env python3
"""
init_port_db.py - Initialize and optionally seed the SQLite porting & evidence database.

Creates tables for functions, cross-references, recovered types, kernel imports,
HLE overrides, unsupported APIs, unresolved dependencies, and sourced evidence.
Optionally imports kernel imports from `xbe_inspect.py --json` output.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS functions (
    addr INTEGER PRIMARY KEY,
    size INTEGER NOT NULL DEFAULT 0,
    hash TEXT,
    name TEXT NOT NULL,
    signature TEXT,
    calling_conv TEXT DEFAULT 'unknown',
    status TEXT NOT NULL DEFAULT 'unknown'
        CHECK (status IN ('unknown', 'decoded', 'verified', 'overridden', 'stubbed')),
    confidence TEXT NOT NULL DEFAULT 'low'
        CHECK (confidence IN ('low', 'medium', 'high')),
    source TEXT NOT NULL DEFAULT 'manual',
    notes TEXT
);

CREATE TABLE IF NOT EXISTS xrefs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_addr INTEGER NOT NULL,
    to_addr INTEGER NOT NULL,
    xref_type TEXT NOT NULL DEFAULT 'call',
    source TEXT NOT NULL DEFAULT 'static'
);

CREATE TABLE IF NOT EXISTS types (
    name TEXT PRIMARY KEY,
    size INTEGER,
    definition TEXT NOT NULL,
    confidence TEXT NOT NULL DEFAULT 'low'
        CHECK (confidence IN ('low', 'medium', 'high')),
    source TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS imports (
    ordinal INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    thunk_vaddr INTEGER,
    status TEXT NOT NULL DEFAULT 'unimplemented'
        CHECK (status IN ('implemented', 'stubbed', 'unimplemented', 'not_needed')),
    test_ref TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS overrides (
    addr INTEGER PRIMARY KEY,
    impl_symbol TEXT NOT NULL,
    reason TEXT NOT NULL,
    verified INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS unsupported_apis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subsystem TEXT NOT NULL,
    api_name TEXT NOT NULL,
    first_seen_addr INTEGER,
    impact TEXT NOT NULL DEFAULT 'unknown',
    notes TEXT
);

CREATE TABLE IF NOT EXISTS unresolved_dependencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    blocking_tier INTEGER DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'open'
);

CREATE TABLE IF NOT EXISTS evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim TEXT NOT NULL,
    source TEXT NOT NULL,
    method TEXT NOT NULL CHECK (method IN ('static', 'dynamic', 'documentation', 'conformance')),
    confidence TEXT NOT NULL CHECK (confidence IN ('low', 'medium', 'high')),
    recorded_at TEXT NOT NULL,
    agent TEXT NOT NULL
);
"""


def init_db(db_path: Path, xbe_json: Path | None = None) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        if xbe_json is not None:
            data = json.loads(xbe_json.read_text(encoding="utf-8"))
            imports = data.get("kernel_imports", [])
            for imp in imports:
                ordinal = int(imp["ordinal"])
                name = str(imp["name"])
                thunk_vaddr = int(imp["thunk_vaddr"], 16)
                conn.execute(
                    """
                    INSERT INTO imports (ordinal, name, thunk_vaddr, status)
                    VALUES (?, ?, ?, 'unimplemented')
                    ON CONFLICT(ordinal) DO UPDATE SET
                        name = excluded.name,
                        thunk_vaddr = excluded.thunk_vaddr
                    """,
                    (ordinal, name, thunk_vaddr),
                )
            entry_addr = int(data["entry_point"], 16)
            conn.execute(
                """
                INSERT OR IGNORE INTO functions (addr, name, status, confidence, source, notes)
                VALUES (?, 'xbe_entry_point', 'decoded', 'high', 'xbe_inspect', 'Decoded XBE entry point')
                """,
                (entry_addr,),
            )
        conn.commit()
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize the Xbox porting SQLite evidence DB.")
    parser.add_argument("db", type=Path, help="Output SQLite database path (e.g., reports/port.db)")
    parser.add_argument(
        "--from-xbe-json",
        type=Path,
        default=None,
        help="Optional xbe_inspect.py JSON report to seed kernel imports and entry point",
    )
    args = parser.parse_args()

    if args.from_xbe_json is not None and not args.from_xbe_json.is_file():
        print(f"Error: XBE JSON not found: {args.from_xbe_json}", file=sys.stderr)
        return 1

    init_db(args.db, args.from_xbe_json)
    print(f"Initialized database: {args.db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
