import os
from pathlib import Path
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Float, DateTime, func
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = Path(__file__).resolve().parent.parent
SQLITE_DB_PATH = BASE_DIR / "data" / "app_v2.db"

# Database URL setup
database_url = os.environ.get("DATABASE_URL")
if not database_url:
    SQLITE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    database_url = f"sqlite:///{SQLITE_DB_PATH}"
else:
    # SQLAlchemy 1.4+ requires postgresql:// instead of postgres://
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

# SQLite needs specific connect args for threads
is_sqlite = database_url.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}

if is_sqlite:
    engine = create_engine(database_url, connect_args=connect_args)
else:
    engine = create_engine(
        database_url,
        connect_args=connect_args,
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=3600
    )
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class ModerationLog(Base):
    __tablename__ = "moderation_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(255), index=True, nullable=True)
    author_username = Column(String(255), default="Anonymous")
    author_name = Column(String(255), default="Anonymous User")
    comment_text = Column(String, nullable=False)
    is_toxic = Column(Boolean, default=False)
    label = Column(String(50), default="Non-Toxic")
    category = Column(String(255), default="Safe")
    confidence = Column(Float, default=0.0)
    threat_detected = Column(Boolean, default=False)
    platform = Column(String(50), default="Web Playground")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class UsageTracker(Base):
    __tablename__ = "usage_tracker"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(255), unique=True, index=True, nullable=False)
    processed_count = Column(Integer, default=0)
    plan_tier = Column(String(50), default="free")

class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(255), index=True, nullable=False)
    plan_name = Column(String(100), default="Creator Safety Shield ₹99")
    amount_inr = Column(Integer, default=99)
    status = Column(String(50), default="active")
    razorpay_payment_id = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


from sqlalchemy import text

def init_db():
    if is_sqlite:
        print("[DB] Local SQLite development mode detected. Resetting database tables for a clean test run...")
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("[DB] Database initialized successfully with SQLAlchemy.")

def log_moderation_event(author_username, author_name, comment_text, prediction, platform="Web Playground", user_id=None):
    with SessionLocal() as db:
        log_entry = ModerationLog(
            user_id=user_id,
            author_username=author_username,
            author_name=author_name,
            comment_text=comment_text,
            is_toxic=prediction.get("is_toxic", False),
            label=prediction.get("label", "Non-Toxic"),
            category=prediction.get("category", "Safe"),
            confidence=prediction.get("confidence", 0.0),
            threat_detected=prediction.get("threat_detected", False),
            platform=platform
        )
        db.add(log_entry)
        db.commit()

def log_moderation_events_bulk(events, user_id=None):
    if not events:
        return
    with SessionLocal() as db:
        objects = [
            ModerationLog(
                user_id=user_id,
                author_username=e.get("author_username", "Anonymous"),
                author_name=e.get("author_name", "Anonymous User"),
                comment_text=e.get("comment_text", ""),
                is_toxic=e.get("prediction", {}).get("is_toxic", False),
                label=e.get("prediction", {}).get("label", "Non-Toxic"),
                category=e.get("prediction", {}).get("category", "Safe"),
                confidence=e.get("prediction", {}).get("confidence", 0.0),
                threat_detected=e.get("prediction", {}).get("threat_detected", False),
                platform=e.get("platform", "Web Playground")
            ) for e in events
        ]
        db.bulk_save_objects(objects)
        db.commit()

def get_recent_moderation_logs(limit=50, user_id=None):
    with SessionLocal() as db:
        query = db.query(ModerationLog)
        if user_id and user_id != "system_admin":
            query = query.filter(ModerationLog.user_id == user_id)
        logs = query.order_by(ModerationLog.id.desc()).limit(limit).all()
        return [
            {
                "id": l.id,
                "user_id": l.user_id,
                "author_username": l.author_username,
                "author_name": l.author_name,
                "comment_text": l.comment_text,
                "is_toxic": l.is_toxic,
                "label": l.label,
                "category": l.category,
                "confidence": l.confidence,
                "threat_detected": l.threat_detected,
                "platform": l.platform,
                "created_at": l.created_at.isoformat() if l.created_at else None
            } for l in logs
        ]

def clear_moderation_logs(user_id=None):
    with SessionLocal() as db:
        query = db.query(ModerationLog)
        if user_id and user_id != "system_admin":
            query = query.filter(ModerationLog.user_id == user_id)
        query.delete(synchronize_session=False)
        db.commit()

def get_user_usage(user_id):
    with SessionLocal() as db:
        record = db.query(UsageTracker).filter(UsageTracker.user_id == user_id).first()
        if record:
            return {"user_id": user_id, "processed_count": record.processed_count, "plan_tier": record.plan_tier}
        return {"user_id": user_id, "processed_count": 0, "plan_tier": "free"}

def increment_usage_count(user_id, count=1, plan_tier="free"):
    with SessionLocal() as db:
        updated = db.query(UsageTracker).filter(UsageTracker.user_id == user_id).update(
            {UsageTracker.processed_count: UsageTracker.processed_count + count},
            synchronize_session=False
        )
        if not updated:
            record = UsageTracker(user_id=user_id, processed_count=count, plan_tier=plan_tier)
            db.add(record)
        db.commit()

def get_usage_stats():
    # Helper to return global usage for the frontend dashboard
    with SessionLocal() as db:
        total = db.query(func.sum(UsageTracker.processed_count)).scalar() or 0
        return {"processed_count": int(total), "limit_count": 25000}

def record_subscription(user_id, razorpay_payment_id, plan_name="Creator Pro Safety Shield ₹99", amount_inr=99):
    with SessionLocal() as db:
        sub = Subscription(
            user_id=user_id,
            plan_name=plan_name,
            amount_inr=amount_inr,
            status="active",
            razorpay_payment_id=razorpay_payment_id
        )
        db.add(sub)
        usage = db.query(UsageTracker).filter(UsageTracker.user_id == user_id).first()
        if usage:
            usage.plan_tier = "pro"
        else:
            usage = UsageTracker(user_id=user_id, processed_count=0, plan_tier="pro")
            db.add(usage)
        db.commit()
