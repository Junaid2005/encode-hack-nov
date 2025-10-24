from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

from .models import Case, Address, Transaction


DATA_DIR = Path(os.getenv("CASE_DATA_DIR", Path(__file__).resolve().parents[2] / "data"))
DB_PATH = Path(os.getenv("CASE_DB_PATH", DATA_DIR / "cases.db"))


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


@contextmanager
def _conn():
    _ensure_data_dir()
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    with _conn() as c:
        cur = c.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS cases (
                case_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS case_addresses (
                case_id TEXT NOT NULL,
                address TEXT NOT NULL,
                risk_score REAL,
                entity TEXT,
                tags TEXT,
                PRIMARY KEY (case_id, address)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS case_transactions (
                case_id TEXT NOT NULL,
                tx_id TEXT NOT NULL,
                block_height INTEGER,
                asset_id TEXT,
                amount REAL,
                address TEXT,
                timestamp TEXT,
                PRIMARY KEY (case_id, tx_id)
            )
            """
        )
        c.commit()


def create_case(name: str, description: Optional[str] = None) -> Case:
    init_db()
    now = datetime.utcnow().isoformat()
    case = Case(name=name, description=description)
    with _conn() as c:
        cur = c.cursor()
        cur.execute(
            "INSERT INTO cases (case_id, name, description, created_at, updated_at) VALUES (?,?,?,?,?)",
            (case.case_id, case.name, case.description, now, now),
        )
        c.commit()
    return case


def list_cases() -> List[Case]:
    init_db()
    with _conn() as c:
        cur = c.cursor()
        cur.execute("SELECT case_id, name, description, created_at, updated_at FROM cases ORDER BY created_at DESC")
        rows = cur.fetchall()
    out: List[Case] = []
    for case_id, name, description, created_at, updated_at in rows:
        out.append(
            Case(
                case_id=case_id,
                name=name,
                description=description,
                created_at=datetime.fromisoformat(created_at),
                updated_at=datetime.fromisoformat(updated_at),
            )
        )
    return out


def get_case(case_id: str) -> Optional[Case]:
    init_db()
    with _conn() as c:
        cur = c.cursor()
        cur.execute("SELECT case_id, name, description, created_at, updated_at FROM cases WHERE case_id=?", (case_id,))
        row = cur.fetchone()
        if not row:
            return None
        case = Case(
            case_id=row[0],
            name=row[1],
            description=row[2],
            created_at=datetime.fromisoformat(row[3]),
            updated_at=datetime.fromisoformat(row[4]),
            addresses=[],
            transactions=[],
        )
        cur.execute(
            "SELECT address, risk_score, entity, tags FROM case_addresses WHERE case_id=?",
            (case.case_id,),
        )
        for addr, risk, entity, tags_json in cur.fetchall():
            tags = json.loads(tags_json) if tags_json else []
            case.addresses.append(Address(address=addr, risk_score=risk, entity=entity, tags=tags))

        cur.execute(
            "SELECT tx_id, block_height, asset_id, amount, address, timestamp FROM case_transactions WHERE case_id=?",
            (case.case_id,),
        )
        for tx_id, block_height, asset_id, amount, address, ts in cur.fetchall():
            case.transactions.append(
                Transaction(
                    tx_id=tx_id,
                    block_height=block_height,
                    asset_id=asset_id,
                    amount=amount or 0.0,
                    address=address,
                    timestamp=datetime.fromisoformat(ts) if ts else None,
                )
            )
    return case


def add_addresses(case_id: str, addresses: Iterable[Address]) -> int:
    init_db()
    count = 0
    with _conn() as c:
        cur = c.cursor()
        now = datetime.utcnow().isoformat()
        for a in addresses:
            cur.execute(
                "INSERT OR REPLACE INTO case_addresses (case_id, address, risk_score, entity, tags) VALUES (?,?,?,?,?)",
                (case_id, a.address, a.risk_score, a.entity, json.dumps(a.tags)),
            )
            count += 1
        cur.execute("UPDATE cases SET updated_at=? WHERE case_id=?", (now, case_id))
        c.commit()
    return count


def add_transactions(case_id: str, txs: Iterable[Transaction]) -> int:
    init_db()
    count = 0
    with _conn() as c:
        cur = c.cursor()
        now = datetime.utcnow().isoformat()
        for t in txs:
            cur.execute(
                "INSERT OR REPLACE INTO case_transactions (case_id, tx_id, block_height, asset_id, amount, address, timestamp) VALUES (?,?,?,?,?,?,?)",
                (
                    case_id,
                    t.tx_id,
                    t.block_height,
                    t.asset_id,
                    t.amount,
                    t.address,
                    t.timestamp.isoformat() if t.timestamp else None,
                ),
            )
            count += 1
        cur.execute("UPDATE cases SET updated_at=? WHERE case_id=?", (now, case_id))
        c.commit()
    return count

