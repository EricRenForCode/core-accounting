"""Account request/response schemas (§3.5)."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field
from uuid import UUID


class AccountSchema(BaseModel):
    """Flat account representation."""

    id: UUID
    code: str
    name: str
    parent_id: Optional[UUID] = None
    level: int = Field(..., ge=1, le=4)
    type: str  # asset/liability/equity/revenue/expense
    dc_type: str  # D/C
    is_cash: bool = False
    aux_types: list[str] = Field(default_factory=list)
    is_quantity: bool = False
    quantity_unit: Optional[str] = None
    is_enabled: bool = True
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AccountCreate(BaseModel):
    """POST /accounts request body."""

    code: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., min_length=1, max_length=100)
    parent_id: Optional[UUID] = None
    level: int = Field(..., ge=1, le=4)
    type: str = Field(..., pattern="^(asset|liability|equity|revenue|expense)$")
    dc_type: str = Field(..., pattern="^(D|C)$")
    is_cash: bool = False
    aux_types: list[str] = Field(default_factory=list)
    is_quantity: bool = False
    quantity_unit: Optional[str] = Field(None, max_length=20)
    is_enabled: bool = True


class AccountUpdate(BaseModel):
    """PUT /accounts/{id} request body."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    is_cash: Optional[bool] = None
    aux_types: Optional[list[str]] = None
    is_quantity: Optional[bool] = None
    quantity_unit: Optional[str] = Field(None, max_length=20)
    is_enabled: Optional[bool] = None


class AccountTreeNode(BaseModel):
    """Nested tree node for GET /accounts/tree."""

    id: UUID
    code: str
    name: str
    parent_id: Optional[UUID] = None
    level: int
    type: str
    dc_type: str
    is_cash: bool = False
    aux_types: list[str] = Field(default_factory=list)
    is_quantity: bool = False
    quantity_unit: Optional[str] = None
    is_enabled: bool
    children: List["AccountTreeNode"] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class AccountTreeResponse(BaseModel):
    """GET /accounts/tree response."""

    accounts: List[AccountTreeNode]
    total_count: int


class AccountListResponse(BaseModel):
    """GET /accounts response — flat list."""

    accounts: List[AccountSchema]
    total: int
