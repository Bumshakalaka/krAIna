"""KrAIna database model."""
import datetime
from typing import Any, List

from sqlalchemy import JSON, MetaData, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class."""

    type_annotation_map = {dict[str, Any]: JSON}
    metadata = MetaData(
        # https://docs.sqlalchemy.org/en/20/core/constraints.html#configuring-a-naming-convention-for-a-metadata-collection
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )

    def __repr__(self):
        return (
            f"{self.__tablename__}("
            + ", ".join([f"{v}:{k}" for v, k in self.__dict__.items() if not v.startswith("_")])
            + ")"
        )


class Conversations(Base):
    """Conversations table."""

    __tablename__ = "conversations"
    conversation_id: Mapped[int] = mapped_column(primary_key=True, index=True)
    description: Mapped[str] = mapped_column(nullable=True)
    name: Mapped[str] = mapped_column(nullable=True)
    active: Mapped[bool] = mapped_column(default=True)
    assistant: Mapped[str] = mapped_column(nullable=True)
    messages: Mapped[List["Messages"]] = relationship(back_populates="conversation")


class Messages(Base):
    """Messages table"""

    __tablename__ = "messages"
    message_id: Mapped[int] = mapped_column(primary_key=True, index=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.conversation_id"), index=True)
    type: Mapped[int]
    message: Mapped[str]
    create_at: Mapped[datetime.datetime] = mapped_column(comment="Timestamp as float")
    conversation: Mapped["Conversations"] = relationship(back_populates="messages")
