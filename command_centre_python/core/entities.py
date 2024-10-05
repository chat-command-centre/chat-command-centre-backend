from __future__ import annotations
from datetime import datetime
from typing import ClassVar, Optional, Dict, Any, Literal, List
from pydantic import Field
from sqlmodel import SQLModel, Field as SQLField, Relationship

from .db import SQLModelBase


class EntityBase(SQLModelBase, table=True):
    __tablename__: ClassVar[str] = "entities"
    __type__: ClassVar[str] = Field(discriminator="type")

    name: str
    description: str

    def __init_subclass__(cls, **kwargs):
        cls.__type__ = cls.__name__
        return super().__init_subclass__(**kwargs)


class DataSource(EntityBase, table=True):
    __tablename__ = "data_sources"
    data_entries: List["DataEntry"] = Relationship(back_populates="data_source")


class DataEntry(EntityBase, table=True):
    __tablename__ = "data_entries"
    data_source_id: Optional[int] = SQLField(
        default=None, foreign_key="data_sources.id", index=True
    )
    data_source: Optional["DataSource"] = Relationship(back_populates="data_entries")
    data: Dict[str, Any] = Field(default_factory=dict)

    async def save(self):
        await super().save()
        # Notify the dispatcher about the new data
        await semantic_dispatcher.monitor_data_sources()


class Event(EntityBase, table=True):
    __tablename__ = "events"
    parent_id: Optional[int] = SQLField(default=None, foreign_key="events.id")
    parent: Optional["Event"] = Relationship()
    status: Literal["pending", "active", "success", "failure"] = "pending"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class Service(EntityBase, table=True):
    __tablename__ = "services"
    state: Literal["running", "stopped"] = "stopped"

    def start(self):
        self.state = "running"

    def stop(self):
        self.state = "stopped"


class Context(EntityBase, table=True):
    __tablename__ = "contexts"
    system_id: Optional[int] = SQLField(default=None, foreign_key="system_bases.id")
    system: Optional["SystemBase"] = Relationship()
    secrets: Dict[str, str] = Field(default_factory=dict)
    variables: Dict[str, str] = Field(default_factory=dict)


class CloudDataSource(DataSource):
    provider: str  # e.g., 'AWS', 'Azure', 'GCP'
    service: str  # e.g., 'S3', 'EC2', 'BlobStorage'
    credentials: Dict[str, Any] = Field(default_factory=dict)
    config: Dict[str, Any] = Field(default_factory=dict)
