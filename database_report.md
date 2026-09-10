# Database Architecture Report: Creator Safety Shield

## 1. Database Executive Report

This report presents an architectural evaluation of the database layer in **Creator Safety Shield**, implemented via SQLAlchemy ORM supporting SQLite and PostgreSQL engines.

### Key Insights
- **Data Model Focus**: The system currently maintains three primary entities: `ModerationLog`, `UsageTracker`, and `Subscription`.
- **Primary Bottlenecks**: Per-item database session creation and commits during batch API processing, un-indexed text columns, missing user foreign key constraints in log tables, and non-atomic counter increments causing race conditions under concurrent write loads.
- **Persistence Footprint**: Standard relational database setup supporting simple transactional operations.

---

## 2. Schema Evaluation

### Entity & Attribute Analysis

#### A. `moderation_logs` Table
```sql
CREATE TABLE moderation_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    author_username VARCHAR(255) DEFAULT 'Anonymous',
    author_name VARCHAR(255) DEFAULT 'Anonymous User',
    comment_text TEXT NOT NULL,
    is_toxic BOOLEAN DEFAULT FALSE,
    label VARCHAR(50) DEFAULT 'Non-Toxic',
    category VARCHAR(255) DEFAULT 'Safe',
    confidence FLOAT DEFAULT 0.0,
    threat_detected BOOLEAN DEFAULT FALSE,
    platform VARCHAR(50) DEFAULT 'Web Playground',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

- **Schema Issues**:
  - **Missing User Isolation (`user_id`)**: The table lacks a `user_id` foreign key or column. All moderation logs across all users and tenants are stored in a single global flat structure.
  - **Text Length & Indexing**: `comment_text` has no size limitation or indexing strategy.
  - **Denormalized Categorization**: `category`, `label`, and `platform` are stored as raw strings rather than normalized enums or lookup references.

#### B. `usage_tracker` Table
```sql
CREATE TABLE usage_tracker (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id VARCHAR(255) UNIQUE NOT NULL,
    processed_count INTEGER DEFAULT 0,
    plan_tier VARCHAR(50) DEFAULT 'free'
);
```

- **Schema Strengths**: Unique index on `user_id` enables fast lookup for quota checks (`O(1)` index search).
- **Schema Weaknesses**: No audit trail or timestamping (`created_at`, `updated_at`) for tracking usage accrual over time or managing quota resets per billing period.

#### C. `subscriptions` Table
```sql
CREATE TABLE subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id VARCHAR(255) NOT NULL,
    plan_name VARCHAR(100) DEFAULT 'Creator Safety Shield ₹99',
    amount_inr INTEGER DEFAULT 99,
    status VARCHAR(50) DEFAULT 'active',
    razorpay_payment_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

- **Schema Weaknesses**: Lacks foreign key relationships back to `usage_tracker` or user identity modules. Lacks unique constraints on active subscription per user.

---

## 3. Data Flow & Query Assessment

### Query Inventory & Efficiency Analysis

| Function / Workflow | SQL Operation | Index Utilization | Execution Risk / Efficiency Rating |
| :--- | :--- | :--- | :--- |
| `get_user_usage(user_id)` | `SELECT ... WHERE user_id = :id` | `user_id` Index | **High Efficiency** (`O(1)` point lookup). |
| `get_recent_moderation_logs()` | `SELECT ... ORDER BY id DESC LIMIT N` | Primary Key Index | **Medium-High Efficiency** (PK scan; lacks filtering by user). |
| `log_moderation_event()` | `INSERT INTO moderation_logs ...` | None | **Inefficient in Batches** (Called per item inside a loop, resulting in $N$ separate DB connection opens and commits). |
| `increment_usage_count()` | `SELECT` then `UPDATE` | `user_id` Index | **Concurrency Vulnerability** (Read-modify-write pattern causes lost updates or lock contention). |
| `get_usage_stats()` | `SELECT SUM(processed_count) FROM usage_tracker` | Full Table Scan | **Degrades at Scale** (Scans entire `usage_tracker` table as user base grows). |
| `clear_moderation_logs()` | `DELETE FROM moderation_logs` | Table Scan | **Destructive Global Operation** (Deletes all logs across all users without scoping). |

---

## 4. Scaling & Operational Risks

### 1. N+1 Session & Commit Amplification in Batch Pipeline
In `api_moderate_batch`, the code loops over comments and calls `log_moderation_event()` for each item:
```python
for pred, meta in zip(batch_preds, metadata):
    # Opens a new SessionLocal() context and issues DB commit on every loop iteration
    log_moderation_event(meta["user"], meta["name"], pred["comment"], pred, platform=platform)
```
- **Impact**: Batch processing 100 comments issues 100 distinct SQL INSERT transactions and 100 connection acquire/release cycles, creating extreme transaction log I/O overhead.

### 2. Concurrency Race Conditions on Quota Counters
In `increment_usage_count()`:
```python
record = db.query(UsageTracker).filter(UsageTracker.user_id == user_id).first()
if record:
    record.processed_count += count
db.commit()
```
- **Impact**: Under concurrent API requests for the same `user_id`, two parallel threads reading the same initial `processed_count` will overwrite each other's updates, leading to inaccurate usage billing and quota leaks.

### 3. Lack of Multi-Tenant Data Scoping
`ModerationLog` does not record `user_id`. Querying recent logs fetches all logs globally:
```python
logs = db.query(ModerationLog).order_by(ModerationLog.id.desc()).limit(limit).all()
```
- **Impact**: Prevents filtering harassment logs per creator/user without performing post-query filtering or modifying schema.

### 4. Unindexed Aggregate Metrics
`get_usage_stats()` executes a full table sum over `usage_tracker.processed_count` on public dashboard renders.
- **Impact**: Increases query execution time linearly ($O(N)$) with the total number of registered users.

---

## 5. Architectural Recommendations

### 1. Bulk Insertion Pattern for Batch API
Replace loop-based insertion with a single bulk insert transaction:
```python
def log_moderation_events_bulk(events_data):
    with SessionLocal() as db:
        objects = [ModerationLog(**data) for data in events_data]
        db.bulk_save_objects(objects)
        db.commit()
```

### 2. Atomic Database Counter Updates
Eliminate read-modify-write race conditions by executing atomic SQL updates:
```python
def increment_usage_count_atomic(user_id, count=1, plan_tier="free"):
    with SessionLocal() as db:
        updated = db.query(UsageTracker).filter(UsageTracker.user_id == user_id).update(
            {UsageTracker.processed_count: UsageTracker.processed_count + count},
            synchronize_session=False
        )
        if not updated:
            record = UsageTracker(user_id=user_id, processed_count=count, plan_tier=plan_tier)
            db.add(record)
        db.commit()
```

### 3. Multi-Tenant Schema Refactoring
Add `user_id` and composite indexes to `moderation_logs`:
```sql
ALTER TABLE moderation_logs ADD COLUMN user_id VARCHAR(255);
CREATE INDEX idx_moderation_user_created ON moderation_logs (user_id, created_at DESC);
```

### 4. Data Lifecycle Management
- **Partitioning & Archiving**: Implement a retention policy (e.g., auto-archiving logs older than 90 days for free tier users) to prevent `moderation_logs` table bloat.
- **Indexing Strategy**: Add composite index `(user_id, created_at)` to support user-scoped history pagination.
