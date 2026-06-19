from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Property(Base):
    __tablename__ = "properties"

    id = Column(Integer, primary_key=True, autoincrement=True)
    link = Column(String, unique=True, nullable=False, index=True)
    datum = Column(String)
    plattform = Column(String)
    plz = Column(String, index=True)
    ort = Column(String, index=True)
    adresse = Column(String)
    groesse = Column(String)
    preis = Column(String)
    bplan = Column(String)
    anbieter = Column(String)
    status = Column(String, index=True, default="Neu")
    propstack_id = Column(String)
    notizen = Column(Text)
    haustyp = Column(String)
    is_expired = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SeenUrl(Base):
    __tablename__ = "seen_urls"

    url = Column(String, primary_key=True)


class UpdateRun(Base):
    __tablename__ = "update_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    status = Column(String, default="running")  # running | success | error
    log_text = Column(Text, default="")


class ThinkImmoSession(Base):
    __tablename__ = "thinkimmo_session"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cookie_value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow)
