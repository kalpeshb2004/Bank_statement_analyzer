import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from datetime import datetime

load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME")

DATABASE_URL = URL.create(
    drivername="mysql+pymysql",
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=int(DB_PORT),
    database=DB_NAME,
)

DB_SSL_CA = os.getenv("DB_SSL_CA")  # local pe khali, cloud pe "certs/ca.pem"
connect_args = {"ssl": {"ca": DB_SSL_CA}} if DB_SSL_CA else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------- TABLES ----------

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255))
    email = Column(String(255), unique=True, index=True, nullable=True)  # API enforces required
    password_hash = Column(String(255), nullable=True)                   # API enforces required
    account_no = Column(String(50))
    bank_name = Column(String(100))
    branch = Column(String(255))
    ifsc = Column(String(20))
    address = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)

    statements = relationship("Statement", back_populates="user")


class Statement(Base):
    __tablename__ = "statements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    file_name = Column(String(255))
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    total_transactions = Column(Integer)

    # Bank account ki details (statement PDF se)
    holder_name = Column(String(255))
    account_no = Column(String(50))
    bank_name = Column(String(100))
    branch = Column(String(255))
    ifsc = Column(String(20))
    address = Column(String(500))

    user = relationship("User", back_populates="statements")
    transactions = relationship("Transaction", back_populates="statement")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    statement_id = Column(Integer, ForeignKey("statements.id"))
    date = Column(DateTime)
    description = Column(String(500))
    clean_merchant = Column(String(255))
    category = Column(String(100))
    withdrawal = Column(Float)
    deposit = Column(Float)
    balance = Column(Float)
    match_type = Column(String(50))

    statement = relationship("Statement", back_populates="transactions")


def init_db():
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully!")


if __name__ == "__main__":
    init_db()