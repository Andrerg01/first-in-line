"""Pydantic schemas for event API responses."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class EventListItem(BaseModel):
    """Minimal event representation returned in list responses."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    business_name: str | None
    event_name: str | None
    event_type: str
    category: str | None
    event_date: datetime | None
    city: str | None
    state: str | None
    status: str
    confidence_score: float | None
    possible_duplicate: bool
    duplicate_of_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class EventStatusUpdate(BaseModel):
    """Request body for updating an event's status."""

    status: Literal["candidate", "verified", "rejected", "needs_review", "merged", "expired"]


class EventMapItem(BaseModel):
    """Event representation optimized for map pin rendering."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    business_name: str | None
    event_name: str | None
    category: str | None
    event_date: datetime | None
    address: str | None
    city: str | None
    state: str | None
    status: str
    confidence_score: float | None
    possible_duplicate: bool
    lat: float
    lon: float
    created_at: datetime
    updated_at: datetime


class EventDetail(BaseModel):
    """Full event detail returned by the single-event endpoint."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    business_name: str | None
    event_name: str | None
    event_type: str
    category: str | None
    event_date: datetime | None
    address: str | None
    city: str | None
    state: str | None
    country: str | None
    lat: float | None
    lon: float | None
    promotion_text: str | None
    notes: str | None
    status: str
    confidence_score: float | None
    possible_duplicate: bool
    duplicate_of_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
