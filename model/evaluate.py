
from pathlib import Path
from datetime import datetime
import json
import pickle
import re

import pandas as pd

from preprocessing.clean_data import clean_text
from model.registry import load_registry

from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
)


# ============================================================
# CONFIGURATION
# ============================================================

JIGSAW_FILE = Path(
    "data/jigsaw-unintended-bias-in-toxicity-classification/train.csv"
)

MODEL_DIR = Path(__file__).resolve().parent
VERSIONS_DIR = MODEL_DIR / "versions"

EVALUATION_DIR = MODEL_DIR / "evaluations"

JIGSAW_SAMPLE_SIZE = 20000
TEST_SIZE = 0.20
RANDOM_STATE = 42


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def normalize_for_comparison(text):

    text = str(text).lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s]", "", text)

    return text.strip()


def prepare_test_data():

    print("\nLoading Jigsaw evaluation dataset...")

    if not JIGSAW_FILE.exists():
        raise FileNotFoundError(
            f"Jigsaw dataset not found: {JIGSAW_FILE}"
        )

    df = pd.read_csv(JIGSAW_FILE)

    required_columns = {"comment_text", "target"}

    missing = required_columns - set(df.columns)

    if missing:
        raise ValueError(
            f"Missing Jigsaw columns: {missing}"
        )

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

    df = df.dropna(
        subset=["target"]
    ).copy()

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

    df = df.sample(
        n=min(JIGSAW_SAMPLE_SIZE, len(df)),
        random_state=RANDOM_STATE
    ).reset_index(drop=True)

    X = df["comment_text"].apply(
        clean_text
    ).reset_index(drop=True)

    y = df["label"].reset_index(drop=True)

    valid_mask = X.str.strip() != ""

    X = X[valid_mask].reset_index(drop=True)
    y = y[valid_mask].reset_index(drop=True)

    if y.nunique() < 2:
        raise ValueError(
            "Evaluation data must contain both classes."
        )

    _, test_indices = train_test_split(
        range(len(X)),
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=y
    )

    X_test = X.iloc[test_indices].reset_index(drop=True)
    y_test = y.iloc[test_indices].reset_index(drop=True)

    print("Evaluation examples:", len(X_test))

    return X_test, y_test


def evaluate_model(model_path, vectorizer_path, X_test, y_test):

    with open(model_path, "rb") as file:
        model = pickle.load(file)

    with open(vectorizer_path, "rb") as file:
        vectorizer = pickle.load(file)

    X_vectorized = vectorizer.transform(X_test)

    predictions = model.predict(X_vectorized)

    matrix = confusion_matrix(
        y_test,
        predictions,
        labels=[0, 1]
    )

    tn, fp, fn, tp = matrix.ravel()

    return {
        "accuracy": float(
            accuracy_score(y_test, predictions)
        ),

        "toxic_precision": float(
            precision_score(
                y_test,
                predictions,
                pos_label=1,
                zero_division=0
            )
        ),

        "toxic_recall": float(
            recall_score(
                y_test,
                predictions,
                pos_label=1,
                zero_division=0
            )
        ),

        "toxic_f1": float(
            f1_score(
                y_test,
                predictions,
                pos_label=1,
                zero_division=0
            )
        ),

        "confusion_matrix": matrix.tolist(),

        "true_negatives": int(tn),
        "false_positives": int(fp),
        "false_negatives": int(fn),
        "true_positives": int(tp)
    }


# ============================================================
# 1. PREPARE EVALUATION DATA
# ============================================================

X_test, y_test = prepare_test_data()


# ============================================================
# 2. LOAD MODEL REGISTRY
# ============================================================

print("\nLoading model registry...")

registry = load_registry()

active_version = registry.get("active_version")

registered_versions = registry.get("versions", [])

print("Active version:", active_version)
print("Registered candidates:", len(registered_versions))


# ============================================================
# 3. BUILD MODEL LIST
# ============================================================

models_to_evaluate = []

# Include the active legacy model.
if active_version == "legacy":

    models_to_evaluate.append({
        "version": "legacy",
        "status": "active",
        "model_path": MODEL_DIR / "model.pkl",
        "vectorizer_path": MODEL_DIR / "vectorizer.pkl",
        "comparison_warning": (
            "Potential evaluation leakage: legacy training "
            "may have included examples from this test split."
        )
    })

else:

    active_entry = next(
        (
            item for item in registered_versions
            if item["version"] == active_version
        ),
        None
    )

    if active_entry is None:
        raise RuntimeError(
            "Active model is missing from the registry."
        )

    models_to_evaluate.append({
        "version": active_version,
        "status": "active",
        "model_path": MODEL_DIR / active_entry["paths"]["model"],
        "vectorizer_path": MODEL_DIR / active_entry["paths"]["vectorizer"],
        "comparison_warning": None
    })


# Include all registered non-active candidates.
for entry in registered_versions:

    if entry["version"] == active_version:
        continue

    models_to_evaluate.append({
        "version": entry["version"],
        "status": entry["status"],
        "model_path": MODEL_DIR / entry["paths"]["model"],
        "vectorizer_path": MODEL_DIR / entry["paths"]["vectorizer"],
        "comparison_warning": None
    })


# ============================================================
# 4. EVALUATE EACH MODEL
# ============================================================

print("\nMODEL COMPARISON")
print("================")

results = []

for item in models_to_evaluate:

    version = item["version"]

    print("\nEvaluating:", version)

    model_path = item["model_path"]
    vectorizer_path = item["vectorizer_path"]

    if not model_path.exists():
        print("Model file missing. Skipping.")
        continue

    if not vectorizer_path.exists():
        print("Vectorizer file missing. Skipping.")
        continue

    metrics = evaluate_model(
        model_path,
        vectorizer_path,
        X_test,
        y_test
    )

    result = {
        "version": version,
        "status": item["status"],
        "comparison_warning": item["comparison_warning"],
        "metrics": metrics
    }

    results.append(result)

    print(f"Accuracy: {metrics['accuracy']:.4f}")
    print(f"Toxic precision: {metrics['toxic_precision']:.4f}")
    print(f"Toxic recall: {metrics['toxic_recall']:.4f}")
    print(f"Toxic F1: {metrics['toxic_f1']:.4f}")

    print("False positives:", metrics["false_positives"])
    print("False negatives:", metrics["false_negatives"])


# ============================================================
# 5. SORT RESULTS BY TOXIC F1
# ============================================================

results.sort(
    key=lambda item: item["metrics"]["toxic_f1"],
    reverse=True
)


# ============================================================
# 6. SAVE COMPARISON REPORT
# ============================================================

EVALUATION_DIR.mkdir(
    parents=True,
    exist_ok=True
)

timestamp = datetime.now().strftime(
    "%Y%m%d_%H%M%S"
)

report = {
    "evaluated_at": datetime.now().astimezone().isoformat(),

    "evaluation_dataset": "Jigsaw holdout",

    "evaluation_examples": len(X_test),

    "active_version": active_version,

    "ranking_metric": "toxic_f1",

    "results": results
}

report_path = (
    EVALUATION_DIR /
    f"comparison_{timestamp}.json"
)

latest_path = (
    EVALUATION_DIR /
    "latest_comparison.json"
)

with open(report_path, "w", encoding="utf-8") as file:
    json.dump(
        report,
        file,
        indent=4
    )

with open(latest_path, "w", encoding="utf-8") as file:
    json.dump(
        report,
        file,
        indent=4
    )


# ============================================================
# 7. DISPLAY FINAL RANKING
# ============================================================

print("\nFINAL MODEL RANKING")
print("===================")

for rank, item in enumerate(results, start=1):

    metrics = item["metrics"]

    print(f"\nRank {rank}: {item['version']}")

    print("Status:", item["status"])

    print(
        f"Accuracy: {metrics['accuracy']:.4f}"
    )

    print(
        f"Toxic precision: {metrics['toxic_precision']:.4f}"
    )

    print(
        f"Toxic recall: {metrics['toxic_recall']:.4f}"
    )

    print(
        f"Toxic F1: {metrics['toxic_f1']:.4f}"
    )


# ============================================================
# 8. FINAL SUMMARY
# ============================================================

print("\nEVALUATION COMPLETED")
print("====================")

print("Models evaluated:", len(results))
print("Active model:", active_version)

print("Detailed report:", report_path)
print("Latest report:", latest_path)

print("\nNo models were promoted or modified.")
