
from pathlib import Path
from datetime import datetime
import json
import pickle
import re

import pandas as pd

from preprocessing.clean_data import clean_text
from model.registry import register_candidate

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
)


# ============================================================
# CONFIGURATION
# ============================================================

JIGSAW_FILE = Path(
    "data/jigsaw-unintended-bias-in-toxicity-classification/train.csv"
)

MANUAL_FILE = Path("data/labelled_comments.csv")

MODEL_DIR = Path("model")
VERSIONS_DIR = MODEL_DIR / "versions"

JIGSAW_SAMPLE_SIZE = 20000
TEST_SIZE = 0.20
RANDOM_STATE = 42

MAX_FEATURES = 5000
MAX_ITER = 1000


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def normalize_for_comparison(text):
    """Normalize comments for duplicate detection."""

    text = str(text).lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s]", "", text)

    return text.strip()


def validate_jigsaw(df):
    """Validate and prepare the Jigsaw dataset."""

    required_columns = {"comment_text", "target"}
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Jigsaw dataset is missing columns: {missing_columns}"
        )

    original_count = len(df)

    df = df.dropna(
        subset=["comment_text", "target"]
    ).copy()

    df["comment_text"] = (
        df["comment_text"].astype(str).str.strip()
    )

    df = df[df["comment_text"] != ""].copy()

    df["target"] = pd.to_numeric(
        df["target"],
        errors="coerce"
    )

    df = df.dropna(subset=["target"]).copy()

    df = df[df["target"].between(0, 1)].copy()

    df["label"] = (
        df["target"] >= 0.5
    ).astype(int)

    df["_comparison"] = df["comment_text"].apply(
        normalize_for_comparison
    )

    df = df[df["_comparison"] != ""].copy()

    df = df.drop_duplicates(
        subset=["_comparison"]
    ).copy()

    print("\nJIGSAW VALIDATION")
    print("-----------------")
    print("Original rows:", original_count)
    print("Valid rows:", len(df))
    print("Removed rows:", original_count - len(df))

    return df


def validate_manual(df):
    """Validate manually labelled comments."""

    required_columns = {"comment", "toxic_label"}
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Manual dataset is missing columns: {missing_columns}"
        )

    original_count = len(df)

    df = df.dropna(
        subset=["comment", "toxic_label"]
    ).copy()

    df["comment"] = (
        df["comment"].astype(str).str.strip()
    )

    df["toxic_label"] = pd.to_numeric(
        df["toxic_label"],
        errors="coerce"
    )

    df = df.dropna(
        subset=["toxic_label"]
    ).copy()

    df = df[
        df["toxic_label"].isin([0, 1])
    ].copy()

    df["toxic_label"] = df["toxic_label"].astype(int)

    df["_comparison"] = df["comment"].apply(
        normalize_for_comparison
    )

    df = df[
        (df["comment"] != "") &
        (df["_comparison"] != "")
    ].copy()

    df = df.drop_duplicates(
        subset=["_comparison"]
    ).copy()

    print("\nMANUAL DATA VALIDATION")
    print("----------------------")
    print("Original rows:", original_count)
    print("Valid rows:", len(df))
    print("Removed rows:", original_count - len(df))

    return df


# ============================================================
# 1. LOAD JIGSAW DATASET
# ============================================================

print("\nLoading Jigsaw dataset...")

if not JIGSAW_FILE.exists():
    raise FileNotFoundError(
        f"Jigsaw dataset not found: {JIGSAW_FILE}"
    )

df = pd.read_csv(JIGSAW_FILE)

print("Dataset loaded successfully.")

df = validate_jigsaw(df)

if len(df) < 100:
    raise ValueError(
        "Not enough valid Jigsaw examples to train."
    )

sample_size = min(
    JIGSAW_SAMPLE_SIZE,
    len(df)
)

df = df.sample(
    n=sample_size,
    random_state=RANDOM_STATE
).reset_index(drop=True)

print("\nJigsaw examples selected:", len(df))


# ============================================================
# 2. PREPARE JIGSAW DATA
# ============================================================

print("\nPreparing Jigsaw comments...")

X_jigsaw = df["comment_text"].apply(
    clean_text
).reset_index(drop=True)

y_jigsaw = df["label"].reset_index(drop=True)

jigsaw_comparison = (
    df["_comparison"].reset_index(drop=True)
)

valid_mask = X_jigsaw.str.strip() != ""

X_jigsaw = X_jigsaw[valid_mask].reset_index(drop=True)
y_jigsaw = y_jigsaw[valid_mask].reset_index(drop=True)

jigsaw_comparison = (
    jigsaw_comparison[valid_mask].reset_index(drop=True)
)

if y_jigsaw.nunique() < 2:
    raise ValueError(
        "Jigsaw dataset must contain both classes."
    )


# ============================================================
# 3. SPLIT JIGSAW DATA
# ============================================================

print("\nSplitting Jigsaw dataset...")

train_indices, test_indices = train_test_split(
    range(len(X_jigsaw)),
    test_size=TEST_SIZE,
    random_state=RANDOM_STATE,
    stratify=y_jigsaw
)

X_train = X_jigsaw.iloc[train_indices].reset_index(drop=True)
y_train = y_jigsaw.iloc[train_indices].reset_index(drop=True)

X_test = X_jigsaw.iloc[test_indices].reset_index(drop=True)
y_test = y_jigsaw.iloc[test_indices].reset_index(drop=True)

print("Jigsaw training examples:", len(X_train))
print("Jigsaw testing examples:", len(X_test))


# ============================================================
# 4. LOAD MANUAL DATA
# ============================================================

X_manual = pd.Series(dtype="object")
y_manual = pd.Series(dtype="int64")

if MANUAL_FILE.exists():

    print("\nLoading manually labelled examples...")

    manual_df = pd.read_csv(MANUAL_FILE)

    manual_df = validate_manual(manual_df)

    manual_before_overlap = len(manual_df)

    # Remove comments already present in Jigsaw.
    manual_df = manual_df[
        ~manual_df["_comparison"].isin(
            set(jigsaw_comparison)
        )
    ].copy()

    print(
        "Manual examples overlapping with Jigsaw removed:",
        manual_before_overlap - len(manual_df)
    )

    X_manual = manual_df["comment"].apply(
        clean_text
    )

    y_manual = manual_df["toxic_label"]

    manual_valid_mask = X_manual.str.strip() != ""

    X_manual = (
        X_manual[manual_valid_mask].reset_index(drop=True)
    )

    y_manual = (
        y_manual[manual_valid_mask].reset_index(drop=True)
    )

else:
    print("\nNo manual dataset found. Using Jigsaw only.")


# ============================================================
# 5. COMBINE TRAINING DATA
# ============================================================

print("\nPreparing final training data...")

X_train = pd.concat(
    [X_train, X_manual],
    ignore_index=True
)

y_train = pd.concat(
    [y_train, y_manual],
    ignore_index=True
)

print("Total training examples:", len(X_train))
print("Jigsaw test examples:", len(X_test))
print("Manual examples added:", len(X_manual))

if y_train.nunique() < 2:
    raise ValueError(
        "Training data must contain both classes."
    )


# ============================================================
# 6. TF-IDF VECTORIZATION
# ============================================================

print("\nStarting TF-IDF vectorization...")

vectorizer = TfidfVectorizer(
    max_features=MAX_FEATURES
)

X_train_vectorized = vectorizer.fit_transform(X_train)

X_test_vectorized = vectorizer.transform(X_test)

print("Vectorization complete.")
print("Vocabulary size:", len(vectorizer.vocabulary_))


# ============================================================
# 7. TRAIN MODEL
# ============================================================

print("\nTraining Logistic Regression model...")

model = LogisticRegression(
    max_iter=MAX_ITER,
    class_weight="balanced",
    random_state=RANDOM_STATE
)

model.fit(
    X_train_vectorized,
    y_train
)

print("Model training complete.")


# ============================================================
# 8. EVALUATE MODEL
# ============================================================

print("\nMODEL EVALUATION")
print("================")

y_pred = model.predict(X_test_vectorized)

accuracy = accuracy_score(
    y_test,
    y_pred
)

report = classification_report(
    y_test,
    y_pred,
    labels=[0, 1],
    target_names=["Non-Toxic", "Toxic"],
    output_dict=True,
    zero_division=0
)

matrix = confusion_matrix(
    y_test,
    y_pred,
    labels=[0, 1]
)

print(f"\nAccuracy: {accuracy:.4f}")

print("\nConfusion Matrix:")
print(matrix)

print("\nClassification Report:")
print(
    classification_report(
        y_test,
        y_pred,
        labels=[0, 1],
        target_names=["Non-Toxic", "Toxic"],
        zero_division=0
    )
)


# ============================================================
# 9. CREATE MODEL VERSION
# ============================================================

timestamp = datetime.now().strftime(
    "%Y%m%d_%H%M%S_%f"
)

version_id = f"v_{timestamp}"

version_dir = VERSIONS_DIR / version_id

version_dir.mkdir(
    parents=True,
    exist_ok=False
)

print("\nCreating model version:", version_id)


# ============================================================
# 10. SAVE VERSIONED ARTIFACTS
# ============================================================

model_path = version_dir / "model.pkl"
vectorizer_path = version_dir / "vectorizer.pkl"
metadata_path = version_dir / "metadata.json"

with open(model_path, "wb") as file:
    pickle.dump(model, file)

with open(vectorizer_path, "wb") as file:
    pickle.dump(vectorizer, file)


# ============================================================
# 11. SAVE TRAINING METADATA
# ============================================================

metadata = {
    "version": version_id,

    "created_at": datetime.now().astimezone().isoformat(),

    "status": "candidate",

    "model": {
        "algorithm": "LogisticRegression",
        "max_iter": MAX_ITER,
        "class_weight": "balanced",
        "random_state": RANDOM_STATE
    },

    "vectorizer": {
        "algorithm": "TfidfVectorizer",
        "max_features": MAX_FEATURES,
        "vocabulary_size": len(vectorizer.vocabulary_)
    },

    "dataset": {
        "jigsaw_sampled": len(df),
        "jigsaw_training": len(train_indices),
        "jigsaw_testing": len(test_indices),
        "manual_examples_added": len(X_manual),
        "total_training_examples": len(X_train)
    },

    "evaluation": {
        "test_dataset": "Jigsaw holdout",
        "accuracy": float(accuracy),
        "confusion_matrix": matrix.tolist(),
        "classification_report": report
    }
}

with open(metadata_path, "w", encoding="utf-8") as file:
    json.dump(
        metadata,
        file,
        indent=4
    )


# ============================================================
# 12. REGISTER CANDIDATE MODEL
# ============================================================

print("\nRegistering candidate model...")

register_candidate(metadata)


# ============================================================
# 13. TRAINING SUMMARY
# ============================================================

print("\nVERSION CREATED SUCCESSFULLY")
print("=============================")

print("Version:", version_id)
print("Model:", model_path)
print("Vectorizer:", vectorizer_path)
print("Metadata:", metadata_path)

print("\nTRAINING SUMMARY")
print("================")

print("Jigsaw examples used:", len(X_jigsaw))
print("Jigsaw test examples:", len(X_test))
print("Manual examples added:", len(X_manual))
print("Total training examples:", len(X_train))

print(f"Evaluation accuracy: {accuracy:.4f}")

print("\nModel status: CANDIDATE")
print("Active model was NOT modified.")

print("\nTraining pipeline completed successfully.")
