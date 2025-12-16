from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings

engine = create_engine(
    settings.database_url.replace("+asyncpg", ""),
    pool_pre_ping=True
)

SessionLocal = sessionmaker(bind=engine)
