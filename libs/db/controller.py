"""KrAIna database controller module."""
import datetime
from pathlib import Path
from typing import List, Union, Tuple

from sqlalchemy import (
    create_engine,
    select,
    update,
)
from sqlalchemy.orm import Session

from .model import Base, Conversations, Messages


class KrainaDbError(Exception):
    """Generic DB Exception."""

    pass


class ConversationNotFound(KrainaDbError):
    """Conversation ID not exists exception."""

    pass


class Db:
    """Database controller class."""

    def __init__(self):
        """
        Initialize a database based on the model.

        Database is created, if not exists.
        """
        self.engine = create_engine("sqlite:///" + str(Path(__file__).parent / "../../kraina.db"))
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

    def new_conversation(self, name: str = None, description: str = None):
        """
        Create a new conversation in the database and set the last conv_id.

        :param name: Name of the conversation
        :param description: Conversation description
        :return:
        """
        with Session(self.engine) as s:
            obj = Conversations(name=name, description=description)
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

    def list_conversations(self, active: Union[bool, None] = True, limit=10) -> List[Conversations]:
        """
        Get all conversations from the newest to oldest.

        :param active: Fileter by active state. If None passed, return all conversations.
        :param limit: How many conversations return
        :return: List of Conversations dataclass from db.model
        """
        with Session(self.engine) as s:
            if active is None:
                stmt = select(Conversations).order_by(Conversations.conversation_id)
            else:
                stmt = (
                    select(Conversations)
                    .where(Conversations.active == active)
                    .order_by(Conversations.conversation_id.desc())
                    .limit(limit)
                )
            ret = []
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
            data = s.execute(
                select(Conversations.name, Conversations.description).where(Conversations.conversation_id == conv_id)
            ).one()
            name, description = data
            messages = []
            for row in s.execute(
                select(Messages).where(Messages.conversation_id == conv_id).order_by(Messages.message_id)
            ):
                messages.append(row[0])
            return Conversations(name=name, description=description, messages=messages)

    def add_message(self, human: bool, message: str, conv_id: Union[int, None] = None):
        """
        Add a new message to the conversation.

        :param human: True if Human message, False if AI.
        :param message: Messgae to add
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
                    human=human,
                    message=message,
                    create_at=datetime.datetime.now(),
                )
            )
            s.commit()

    def add_messages(self, messages: List[Tuple[bool, str]], conv_id: Union[int, None] = None):
        """
        Add a list of messages to the conversation.

        :param messages: List of Tuple(human, message) to add
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
                        human=message[0],
                        message=message[1],
                        create_at=datetime.datetime.now(),
                    )
                )
            s.commit()
