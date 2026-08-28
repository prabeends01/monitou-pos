import uuid
from datetime import datetime

from pydantic import BaseModel


class PlanColumn(BaseModel):
    code: str
    name: str
    setup_price: str
    annual_amc: str
    is_current: bool
    is_recommended: bool


class ComparisonFeatureRow(BaseModel):
    code: str
    name: str
    module: str
    enabled_by_plan: dict[str, bool]  # plan_code -> enabled


class PlanComparisonResponse(BaseModel):
    plans: list[PlanColumn]
    features: list[ComparisonFeatureRow]


class UpgradeRequestCreate(BaseModel):
    requested_plan_code: str
    note: str | None = None


class UpgradeRequestRead(BaseModel):
    id: uuid.UUID
    requested_plan_code: str
    status: str
    note: str | None
    requested_at: datetime
