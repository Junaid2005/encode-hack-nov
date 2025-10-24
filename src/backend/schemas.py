from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str


class HyperSyncQuery(BaseModel):
    """Flexible schema for HyperSync query.

    Accepts arbitrary fields (extra=allow) while hinting common keys.
    """

    model_config = ConfigDict(extra="allow")

    from_block: Optional[int] = None
    to_block: Optional[int] = None
    inputs: Optional[List[Dict[str, Any]]] = None
    field_selection: Optional[Dict[str, Any]] = None


class QueryRequest(BaseModel):
    query: Dict[str, Any] = Field(default_factory=dict)


class FetchResponse(BaseModel):
    data: List[Dict[str, Any]]


class Aggregates(BaseModel):
    total_amount: float
    by_asset: Dict[str, float]
    by_address: Dict[str, float]
    tx_count_by_address: Dict[str, int]


class ProcessedResponse(BaseModel):
    total_records: int
    aggregates: Aggregates
    sample: List[Dict[str, Any]] = Field(default_factory=list)


class AnalysisFindings(BaseModel):
    large_transfers: List[Dict[str, Any]] = Field(default_factory=list)
    high_frequency_addresses: List[Dict[str, Any]] = Field(default_factory=list)
    concentration_risks: List[Dict[str, Any]] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    findings: AnalysisFindings
    summary: str


class CombinedResponse(BaseModel):
    processed: ProcessedResponse
    analysis: AnalyzeResponse


# --- HyperSync meta-aware responses (per context.txt) ---

class HyperSyncMeta(BaseModel):
    archive_height: Optional[int] = None
    next_block: Optional[int] = None
    total_execution_time: Optional[int] = None
    rollback_guard: Optional[Dict[str, Any]] = None
    # Allow carrying through any vendor-specific extras without validation errors
    model_config = ConfigDict(extra="allow")


class QueryResult(BaseModel):
    data: List[Dict[str, Any]] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)
