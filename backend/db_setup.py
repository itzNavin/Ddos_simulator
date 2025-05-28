# backend/db_setup.py

import os
import datetime
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    DateTime,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()


class RequestLog(Base):
    __tablename__ = "request_logs"
    id = Column(Integer, primary_key=True)
    timestamp = Column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )
    traffic_type = Column(String, nullable=False)    # 'normal'|'ddos'
    features = Column(String, nullable=False)        # JSON string of sim_data
    classification = Column(String, nullable=False)  # '0' or '1'


def init_db(db_path: str = None):
    """
    Create engine, bind metadata, and return a Session factory.
    """
    if db_path is None:
        # Place database.db beside this script
        base_dir = os.path.dirname(__file__)
        db_file = os.path.join(base_dir, "database.db")
        db_path = f"sqlite:///{db_file}"

    engine = create_engine(db_path, echo=False)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


if __name__ == "__main__":
    Session = init_db()
    print("✅ database.db & request_logs table created.")
