
from pathlib import Path
import argparse
import json

from model.registry import load_registry, save_registry


# ============================================================
# CONFIGURATION
# ============================================================

MODEL_DIR = Path(__file__).resolve().parent

EVALUATION_FILE = (
    MODEL_DIR / "evaluations" / "latest_comparison.json"
)

VERSIONS_DIR = MODEL_DIR / "versions"

LEGACY_VERSION = "legacy"

# Initial promotion safeguards.
MIN_TOXIC_RECALL = 0.60
MIN_TOXIC_PRECISION = 0.30


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def load_evaluation():

    if not EVALUATION_FILE.exists():
        raise FileNotFoundError(
            "No evaluation report found. "
            "Run python -m model.evaluate first."
        )

    with open(EVALUATION_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def find_result(report, version):

    for result in report.get("results", []):

        if result.get("version") == version:
            return result

    return None


def find_registry_entry(registry, version):

    for entry in registry.get("versions", []):

        if entry.get("version") == version:
            return entry

    return None


def validate_artifacts(entry):

    if entry is None:
        raise ValueError("Model is not registered.")

    paths = entry.get("paths", {})

    required = ["model", "vectorizer", "metadata"]

    for key in required:

        if key not in paths:
            raise ValueError(
                f"Missing {key} path in registry."
            )

        path = MODEL_DIR / paths[key]

        if not path.exists():
            raise FileNotFoundError(
                f"Missing model artifact: {path}"
            )

    return True


# ============================================================
# 1. DISPLAY STATUS
# ============================================================

def show_status():

    registry = load_registry()

    print("\nMODEL MANAGEMENT STATUS")
    print("=======================")

    print(
        "Active model:",
        registry.get("active_version")
    )

    print(
        "Previous active model:",
        registry.get("previous_active_version", "None")
    )

    for entry in registry.get("versions", []):

        print("\nVersion:", entry["version"])
        print("Status:", entry["status"])

        metrics = entry.get("metrics", {})

        print("Accuracy:", metrics.get("accuracy"))
        print("Toxic precision:", metrics.get("toxic_precision"))
        print("Toxic recall:", metrics.get("toxic_recall"))
        print("Toxic F1:", metrics.get("toxic_f1"))


# ============================================================
# 2. PROMOTE CANDIDATE
# ============================================================

def promote_candidate(version):

    registry = load_registry()

    current_active = registry.get("active_version")

    if version == current_active:
        raise ValueError(
            "This model is already active."
        )

    candidate = find_registry_entry(
        registry,
        version
    )

    if candidate is None:
        raise ValueError(
            f"Candidate '{version}' is not registered."
        )

    if candidate.get("status") != "candidate":
        raise ValueError(
            "Only candidate models can be promoted."
        )

    validate_artifacts(candidate)

    # Load the most recent evaluation report.
    report = load_evaluation()

    # Ensure the comparison was performed against
    # the currently active model.
    if report.get("active_version") != current_active:
        raise RuntimeError(
            "Evaluation report is outdated. "
            "Run python -m model.evaluate again."
        )

    candidate_result = find_result(
        report,
        version
    )

    active_result = find_result(
        report,
        current_active
    )

    if candidate_result is None or active_result is None:
        raise ValueError(
            "Both active and candidate models must "
            "appear in the latest evaluation report."
        )

    metrics = candidate_result["metrics"]
    active_metrics = active_result["metrics"]

    recall = metrics["toxic_recall"]
    precision = metrics["toxic_precision"]
    f1 = metrics["toxic_f1"]

    active_f1 = active_metrics["toxic_f1"]

    # --------------------------------------------------------
    # PROMOTION CHECKS
    # --------------------------------------------------------

    checks = {
        "Minimum toxic recall": (
            recall >= MIN_TOXIC_RECALL
        ),

        "Minimum toxic precision": (
            precision >= MIN_TOXIC_PRECISION
        ),

        "Improved toxic F1": (
            f1 > active_f1
        )
    }

    print("\nPROMOTION ELIGIBILITY")
    print("=====================")

    for name, passed in checks.items():

        print(
            f"{name}: {'PASS' if passed else 'FAIL'}"
        )

    if not all(checks.values()):

        print("\nPromotion rejected.")
        print("Active model remains:", current_active)

        return False

    # --------------------------------------------------------
    # PROMOTION
    # --------------------------------------------------------

    previous_entry = find_registry_entry(
        registry,
        current_active
    )

    if previous_entry is not None:
        previous_entry["status"] = "archived"

    candidate["status"] = "active"

    registry["previous_active_version"] = current_active
    registry["active_version"] = version

    save_registry(registry)

    print("\nPROMOTION SUCCESSFUL")
    print("====================")

    print("Previous active:", current_active)
    print("New active model:", version)

    return True


# ============================================================
# 3. ROLLBACK
# ============================================================

def rollback_model():

    registry = load_registry()

    current_active = registry.get("active_version")

    previous_active = registry.get(
        "previous_active_version"
    )

    if not previous_active:
        raise ValueError(
            "No previous active model is available for rollback."
        )

    if previous_active == current_active:
        raise ValueError(
            "Previous model is already active."
        )

    # Validate the target model.
    if previous_active == LEGACY_VERSION:

        legacy_model = MODEL_DIR / "model.pkl"
        legacy_vectorizer = MODEL_DIR / "vectorizer.pkl"

        if not legacy_model.exists() or not legacy_vectorizer.exists():
            raise FileNotFoundError(
                "Legacy model artifacts are missing."
            )

    else:

        previous_entry = find_registry_entry(
            registry,
            previous_active
        )

        validate_artifacts(previous_entry)

    # Update statuses.
    current_entry = find_registry_entry(
        registry,
        current_active
    )

    previous_entry = find_registry_entry(
        registry,
        previous_active
    )

    if current_entry is not None:
        current_entry["status"] = "archived"

    if previous_entry is not None:
        previous_entry["status"] = "active"

    registry["active_version"] = previous_active
    registry["previous_active_version"] = current_active

    save_registry(registry)

    print("\nROLLBACK SUCCESSFUL")
    print("===================")

    print("Previous active:", current_active)
    print("Restored model:", previous_active)


# ============================================================
# 4. COMMAND LINE INTERFACE
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description="Manage Comment Filter model versions."
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True
    )

    subparsers.add_parser(
        "status",
        help="Display model registry status."
    )

    promote_parser = subparsers.add_parser(
        "promote",
        help="Promote an eligible candidate model."
    )

    promote_parser.add_argument(
        "version",
        help="Candidate model version ID."
    )

    subparsers.add_parser(
        "rollback",
        help="Restore the previously active model."
    )

    args = parser.parse_args()

    try:

        if args.command == "status":
            show_status()

        elif args.command == "promote":
            promote_candidate(args.version)

        elif args.command == "rollback":
            rollback_model()

    except (ValueError, FileNotFoundError, RuntimeError, KeyError) as error:

        print("\nOPERATION FAILED")
        print("================")
        print(error)


if __name__ == "__main__":
    main()
