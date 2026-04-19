import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Railway usa postgres://, SQLAlchemy necesita postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL) if DATABASE_URL else None

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine) if engine else None

Base = declarative_base()


def get_db():
    if not SessionLocal:
        raise RuntimeError("DATABASE_URL no configurada")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    if engine:
        Base.metadata.create_all(bind=engine)
        print("[DB] Tablas creadas correctamente")
    else:
        print("[DB] Sin DATABASE_URL — saltando init")
