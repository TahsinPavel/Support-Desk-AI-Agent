import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, DateTime, Boolean, ForeignKey, Text, Float, JSON, Integer,
    UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from database import Base


# TENANT (Client / Organization)
class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    primary_phone = Column(String(50), nullable=True, unique=True)
    support_email = Column(String(255), nullable=True)
    timezone = Column(String(50), default="UTC")
    open_time = Column(String(10), nullable=True)
    close_time = Column(String(10), nullable=True)
    ai_provider = Column(String(50), default="openai")
    ai_system_prompt = Column(Text, nullable=True)
    faqs = Column(JSON, nullable=True)
    services = Column(JSON, nullable=True)
    escalation_phone = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # relationships
    channels = relationship("Channel", back_populates="tenant", cascade="all, delete-orphan")
    knowledge_base = relationship("KnowledgeBase", back_populates="tenant", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="tenant", cascade="all, delete-orphan")
    escalations = relationship("Escalation", back_populates="tenant", cascade="all, delete-orphan")
    analytics = relationship("Analytics", back_populates="tenant", cascade="all, delete-orphan")
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    voice_messages = relationship("VoiceMessage", back_populates="tenant", cascade="all, delete-orphan")

# USER (Tenant admins / operators)
class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True)
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    hashed_password = Column(String(255), nullable=True)
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="users")


# CHANNELS (per-tenant identities: phone/email/chat)

class Channel(Base):
    __tablename__ = "channels"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    type = Column(String(50), nullable=False)
    identifier = Column(String(255), nullable=False)
    description = Column(String(255), nullable=True)
    status = Column(String(50), default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="channels")
    messages = relationship("Message", back_populates="channel", cascade="all, delete-orphan")
    voice_messages = relationship("VoiceMessage", back_populates="channel", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint('tenant_id', 'type', 'identifier', name='uq_tenant_type_identifier'),)


# MESSAGES (single table for all channels)
class Message(Base):
    __tablename__ = "messages"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    channel_id = Column(UUID(as_uuid=True), ForeignKey("channels.id"), nullable=False)
    direction = Column(String(10), default="incoming")
    message_text = Column(Text, nullable=True)
    ai_response = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)
    status = Column(String(50), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    escalated_to_human = Column(Boolean, default=False)
    customer_contact = Column(String(255), nullable=True)

    tenant = relationship("Tenant", back_populates="messages")
    channel = relationship("Channel", back_populates="messages")
    escalation = relationship("Escalation", back_populates="message", uselist=False)


# KNOWLEDGE BASE

class KnowledgeBase(Base):
    __tablename__ = "knowledge_base"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    source_type = Column(String(50), default="manual")
    source_link = Column(String(255), nullable=True)
    embedding = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="knowledge_base")


# ESCALATIONS
class Escalation(Base):
    __tablename__ = "escalations"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id"), nullable=False)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    escalated_to = Column(String(255), nullable=False)
    reason = Column(String(255), nullable=True)
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    message = relationship("Message", back_populates="escalation")
    tenant = relationship("Tenant", back_populates="escalations")


# VOICE MESSAGES
class VoiceMessage(Base):
    __tablename__ = "voice_messages"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    channel_id = Column(UUID(as_uuid=True), ForeignKey("channels.id"), nullable=False)
    from_contact = Column(String(255), nullable=True)
    transcription = Column(Text, nullable=True)
    ai_response = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="voice_messages")
    channel = relationship("Channel", back_populates="voice_messages")


# ANALYTICS
class Analytics(Base):
    __tablename__ = "analytics"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    period_start = Column(DateTime, default=datetime.utcnow)
    total_messages = Column(Integer, default=0)
    ai_resolved = Column(Integer, default=0)
    escalated = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="analytics")
