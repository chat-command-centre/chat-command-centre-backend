from typing import List, Optional
from pydantic import Field
from sqlmodel import SQLModel, Field as SQLField, Relationship
from ...core.db import SQLModelBase


class Contact(SQLModelBase, table=True):
    first_name: str
    last_name: str
    contact_methods: List["ContactMethod"] = Relationship(back_populates="contact")


class ContactMethod(SQLModelBase, table=True):
    contact_id: int = Field(foreign_key="contact.id")
    contact: Contact = Relationship(back_populates="contact_methods")
    value: str


class EmailAddress(ContactMethod):
    pass


class PhoneNumber(ContactMethod):
    pass


class Address(ContactMethod):
    pass


class Website(ContactMethod):
    pass


class SocialMediaHandle(ContactMethod):
    pass


class TwitterHandle(SocialMediaHandle):
    pass


class InstagramHandle(SocialMediaHandle):
    pass


class FacebookHandle(SocialMediaHandle):
    pass


class LinkedInHandle(SocialMediaHandle):
    pass


class TikTokHandle(SocialMediaHandle):
    pass


class YouTubeHandle(SocialMediaHandle):
    pass
