from typing import List, Literal, Optional
from pydantic import Field
from sqlmodel import Relationship
from datetime import datetime
import threading
import multiprocessing
import os
from textwrap import dedent
from jinja2 import Template
from loguru import logger

from ..core.db import SQLModelBase


class LogEntry(SQLModelBase, table=True):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    message: str
    logger_id: int = Field(foreign_key="Logger.id")
    thread_name: str = Field(default_factory=lambda: threading.current_thread().name)
    thread_id: int = Field(default_factory=lambda: threading.get_ident())
    process_id: int = Field(default_factory=os.getpid)
    process_name: str = Field(
        default_factory=lambda: multiprocessing.current_process().name
    )


class Logger(SQLModelBase, table=True):
    level: int = Field(default=20)  # INFO level
    _handlers: List[str] = Field(default_factory=list)
    log_entries: List[LogEntry] = Relationship(back_populates="logger")
    template: str = dedent(
        """\
        Logger(name={{ self.name }}, level={{ self.level }}):
        {% for entry in self.log_entries %}
        {{ entry.timestamp }} [{{ entry.level }}]: {{ entry.message }}
        {% endfor %}
        """
    )
    storage_cutoff: Optional[int] = 1000
    display_cutoff: Optional[int] = 1000

    @classmethod
    def ddl(cls) -> str:
        return dedent(
            """\
            CREATE TRIGGER IF NOT EXISTS prune_log_entries
            AFTER INSERT ON {cls.__tablename__}
            BEGIN
                DELETE FROM {cls.__tablename__}
                WHERE id IN (
                    SELECT id 
                    FROM {cls.__tablename__}
                    WHERE logger_id = NEW.logger_id
                    ORDER BY timestamp ASC
                    LIMIT (
                        SELECT CASE
                            WHEN Logger.storage_cutoff IS NOT NULL THEN
                                MAX(0, COUNT(*) - Logger.storage_cutoff)
                            ELSE
                                0
                        END
                        FROM {cls.__tablename__} AS log
                        LEFT JOIN Logger ON Logger.id = log.logger_id
                        WHERE log.logger_id = NEW.logger_id
                    )
                )
                AND EXISTS (
                    SELECT 1
                    FROM Logger
                    WHERE Logger.id = NEW.logger_id
                    AND Logger.storage_cutoff IS NOT NULL
                );
            END;
            """
        )

    @property
    def _displayed_entries(self) -> List[LogEntry]:
        if self.display_cutoff is None:
            return self.log_entries
        if not self.log_entries:
            return []
        return self.log_entries[-min(self.display_cutoff, len(self.log_entries)) :]

    def log(
        self,
        level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        message: str,
    ):
        self.log_entries.append(
            LogEntry(level=level, message=message, logger_id=self.id)
        )

    @property
    def _jinja_template(self) -> str:
        return Template(self.template)

    def __str__(self):
        return self._jinja_template.render(self=self)

    def __repr__(self):
        return self._jinja_template.render(self=self)

    def write(self, message: str) -> None:
        try:
            level, msg = message.split(":", 1)
            level = level.strip()
            msg = msg.strip()
        except ValueError:
            level = "INFO"
            msg = message.strip()

        if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            level = "INFO"

        self.log(level, msg)

    def add_loguru_sink(self) -> None:
        logger.add(self.write, level="DEBUG")
