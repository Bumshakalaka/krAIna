"""KrAIna database controller module."""

import datetime
import enum
import os
from functools import lru_cache
from pathlib import Path
from typing import List, Union, Tuple

import yaml
from sqlalchemy import create_engine, select, update, delete, and_, Engine, event
from sqlalchemy.orm import Session

from .model import Base, Conversations, Messages
from ..utils import kraina_db


class KrainaDbError(Exception):
    """Generic DB Exception."""

    pass


class ConversationNotFound(KrainaDbError):
    """Conversation ID not exists exception."""

    pass


class LlmMessageType(enum.IntEnum):
    SYSTEM = 0
    HUMAN = 1
    AI = 2
    TOOL = 3
    FUNCTION = 4
    CHAT = 5


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """
    Enabling Foreign Key Support

    https://www.sqlite.org/foreignkeys.html
    https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#foreign-key-support

    :param dbapi_connection:
    :param connection_record:
    :return:
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA optimize")
    cursor.close()


class Db:
    """Database controller class."""

    def __init__(self):
        """
        Initialize a database based on the model.

        Database is created, if not exists.
        """
        self.engine = create_engine("sqlite:///" + kraina_db())
        Base.metadata.create_all(self.engine)

        """handle current conversation_id"""
        self.conv_id: Union[int, None] = None

    def is_conversation_active(self, conv_id: Union[int, None] = None) -> bool:
        """
        Return true if conversation_id is active, otherwise False.

        :param conv_id: conversation_id. If None, use the last known conv_id
        :return:
        """
        conv_id = self.conv_id if conv_id is None else conv_id
        with Session(self.engine) as s:
            data = s.execute(select(Conversations.active).where(Conversations.conversation_id == conv_id)).scalar()
        return bool(data)

    @lru_cache
    def is_conversation_id_valid(self, conv_id: Union[int, None] = None) -> bool:
        """
        Return true if conversation_id is valid, otherwise False.

        :param conv_id: Conversation_id. If None, use the last known conv_id
        :return:
        """
        conv_id = self.conv_id if conv_id is None else conv_id
        with Session(self.engine) as s:
            data = s.execute(
                select(Conversations.conversation_id).where(Conversations.conversation_id == conv_id)
            ).scalar()
        return bool(data)

    def new_conversation(self, name: str = None, description: str = None, assistant: str = None):
        """
        Create a new conversation in the database and set the last conv_id.

        :param name: Name of the conversation
        :param description: Conversation description
        :param assistant: Used Assistant
        :return:
        """
        with Session(self.engine) as s:
            obj = Conversations(name=name, description=description, assistant=assistant)
            s.add(obj)
            s.commit()
            s.refresh(obj)
        self.conv_id = obj.conversation_id

    def update_conversation(self, conv_id: Union[int, None] = None, **kwargs):
        """
        Update the conversation description.

        :param conv_id: Conversation_id. If None, use the last known conv_id
        :param kwargs: Possible values: name, description, active
        :return:
        """
        conv_id = self.conv_id if conv_id is None else conv_id
        if not self.is_conversation_id_valid(conv_id):
            raise ConversationNotFound(f"Conversation_id={conv_id} not found")
        with Session(self.engine) as s:
            s.execute(update(Conversations).where(Conversations.conversation_id == conv_id).values(**kwargs))
            s.commit()

    def delete_conversation(self, conv_id: Union[int, None] = None):
        """
        Delete the conversation.

        :param conv_id: Conversation_id. If None, use the last known conv_id
        :return:
        """
        conv_id = self.conv_id if conv_id is None else conv_id
        if not self.is_conversation_id_valid(conv_id):
            raise ConversationNotFound(f"Conversation_id={conv_id} not found")
        with Session(self.engine) as s:
            s.execute(delete(Conversations).where(Conversations.conversation_id == conv_id))
            s.commit()

    def list_conversations(self, active: Union[bool, None] = True, limit=10) -> List[Conversations]:
        """
        Get all conversations.

        First get all conversations with priority > 0 and sort from the newest to oldest
        and than from the higher to lower prio.
        Next, get all other conversations depends on active

        :param active: Fileter by active state. If None passed, return all conversations.
        :param limit: How many conversations return
        :return: List of Conversations dataclass from db.model
        """
        with Session(self.engine) as s:
            # Get all conversation with prio > 0 first
            stmt = select(Conversations).order_by(Conversations.priority.desc(), Conversations.conversation_id.desc())
            if active is None:
                stmt = stmt.where(Conversations.priority > 0)
            else:
                stmt = stmt.where(and_(Conversations.active == active, Conversations.priority > 0))
            ret = []
            for row in s.execute(stmt):
                ret.append(row[0])

            stmt = (
                select(Conversations)
                .where(Conversations.priority == 0)
                .order_by(Conversations.conversation_id.desc())
                .limit(limit)
            )
            if active is not None:
                stmt = stmt.where(and_(Conversations.active == active, Conversations.priority == 0))
            for row in s.execute(stmt):
                ret.append(row[0])
            return ret

    def get_conversation(self, conv_id: Union[int, None] = None) -> Conversations:
        """
        Get all messages from the conversation.

        :param conv_id: Conversation_id. If None, use the last known conv_id
        :return: Conversations dataclass from db.model
        """
        conv_id = self.conv_id if conv_id is None else conv_id
        if not self.is_conversation_id_valid(conv_id):
            raise ConversationNotFound(f"Conversation_id={conv_id} not found")
        with Session(self.engine) as s:
            conv = s.execute(select(Conversations).where(Conversations.conversation_id == conv_id)).one()[0]
            len(conv.messages)
            return conv

    def add_message(self, message_type: LlmMessageType, message: str, conv_id: Union[int, None] = None):
        """
        Add a new message to the conversation.

        :param message_type: Message type
        :param message: Message to add
        :param conv_id: Conversation_id. If None, use the last known conv_id
        :return:
        """
        conv_id = self.conv_id if conv_id is None else conv_id
        if not self.is_conversation_id_valid(conv_id):
            raise ConversationNotFound(f"Conversation_id={conv_id} not found")
        with Session(self.engine) as s:
            conv_obj = s.execute(select(Conversations).where(Conversations.conversation_id == conv_id)).scalar()
            conv_obj.messages.append(
                Messages(
                    type=message_type,
                    message=message.strip(),
                    create_at=datetime.datetime.now(),
                )
            )
            s.commit()

    def add_messages(self, messages: List[Tuple[LlmMessageType, str]], conv_id: Union[int, None] = None):
        """
        Add a list of messages to the conversation.

        :param messages: List of Tuple(message_type, message) to add
        :param conv_id: Conversation_id. If None, use the last known conv_id
        :return:
        """
        conv_id = self.conv_id if conv_id is None else conv_id
        if not self.is_conversation_id_valid(conv_id):
            raise ConversationNotFound(f"Conversation_id={conv_id} not found")
        with Session(self.engine) as s:
            conv_obj = s.execute(select(Conversations).where(Conversations.conversation_id == conv_id)).scalar()
            for message in messages:
                conv_obj.messages.append(
                    Messages(
                        type=message[0],
                        message=message[1].strip(),
                        create_at=datetime.datetime.now(),
                    )
                )
            s.commit()
