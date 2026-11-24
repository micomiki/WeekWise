import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from .models import Base

load_dotenv(Path(__file__).resolve().parents[2] / '.env')
URL = os.getenv('DATABASE_URL', 'sqlite:///./weekwise.db')
engine = create_engine(URL, connect_args={'check_same_thread': False} if URL.startswith('sqlite') else {}, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False)

def get_db():
    with SessionLocal() as db:
        yield db

def init_db():
    Base.metadata.create_all(bind=engine)
