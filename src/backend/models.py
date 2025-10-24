from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from uuid import uuid4


class Transaction(BaseModel):
    tx_id: str
    block_height: Optional[int] = None
    asset_id: Optional[str] = None
    amount: float = 0.0
    address: Optional[str] = None  # input.address (sender or related actor)
    timestamp: Optional[datetime] = None


class Address(BaseModel):
    address: str
    risk_score: Optional[float] = None  # 0.0 (low) .. 1.0 (high)
    entity: Optional[str] = None  # Known entity name if resolved
    tags: List[str] = Field(default_factory=list)


class Case(BaseModel):
    case_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    addresses: List[Address] = Field(default_factory=list)
    transactions: List[Transaction] = Field(default_factory=list)
