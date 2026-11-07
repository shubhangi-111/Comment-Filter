
from pathlib import Path
import json


MODEL_DIR = Path(__file__).resolve().parent
REGISTRY_FILE = MODEL_DIR / "registry.json"

LEGACY_MODEL = "legacy"


def load_registry():
    """
    Load the model registry.
    If it doesn't exist, initialize it with the existing legacy model.
    """

    if not REGISTRY_FILE.exists():

        registry = {
            "active_version": LEGACY_MODEL,
            "versions": []
        }

        save_registry(registry)

        return registry

    with open(REGISTRY_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def save_registry(registry):
    """
    Save registry safely using a temporary file.
    """

    temporary_file = REGISTRY_FILE.with_suffix(".tmp")

    with open(temporary_file, "w", encoding="utf-8") as file:
        json.dump(
            registry,
            file,
            indent=4
        )

    temporary_file.replace(REGISTRY_FILE)


def register_candidate(metadata):
    """
    Register a newly trained model as a candidate.
    Never changes the active model.
    """

    registry = load_registry()

    version = metadata["version"]

    versions = registry["versions"]

    # Avoid duplicate entries for the same version.
    versions = [
        item for item in versions
        if item["version"] != version
    ]

    evaluation = metadata.get("evaluation", {})

    toxic_metrics = evaluation.get("classification_report", {}).get(
        "Toxic", {}
    )

    candidate = {
        "version": version,
        "status": "candidate",
        "created_at": metadata.get("created_at"),

        "metrics": {
            "accuracy": evaluation.get("accuracy"),
            "toxic_precision": toxic_metrics.get("precision"),
            "toxic_recall": toxic_metrics.get("recall"),
            "toxic_f1": toxic_metrics.get("f1-score")
        },

        "paths": {
            "model": f"versions/{version}/model.pkl",
            "vectorizer": f"versions/{version}/vectorizer.pkl",
            "metadata": f"versions/{version}/metadata.json"
        }
    }

    versions.append(candidate)

    registry["versions"] = versions

    # Deliberately do not change active_version.
    save_registry(registry)

    print("\nModel registered as candidate:", version)
    print("Active model remains:", registry["active_version"])


def get_active_model_paths():
    """
    Return paths for the currently active model.
    """

    registry = load_registry()

    active_version = registry.get("active_version")

    # Existing model files are treated as the legacy active model.
    if active_version == LEGACY_MODEL:

        return {
            "version": LEGACY_MODEL,
            "model": MODEL_DIR / "model.pkl",
            "vectorizer": MODEL_DIR / "vectorizer.pkl"
        }

    active_entry = next(
        (
            item for item in registry["versions"]
            if item["version"] == active_version
        ),
        None
    )

    if active_entry is None:
        raise RuntimeError(
            f"Active model version '{active_version}' "
            "was not found in the registry."
        )

    model_path = MODEL_DIR / active_entry["paths"]["model"]
    vectorizer_path = MODEL_DIR / active_entry["paths"]["vectorizer"]

    if not model_path.exists() or not vectorizer_path.exists():
        raise FileNotFoundError(
            f"Artifacts for active model '{active_version}' are missing."
        )

    return {
        "version": active_version,
        "model": model_path,
        "vectorizer": vectorizer_path
    }


def list_versions():
    """
    Print all registered model versions.
    """

    registry = load_registry()

    print("\nMODEL REGISTRY")
    print("==============")

    print("Active version:", registry["active_version"])

    if not registry["versions"]:
        print("No candidate versions registered.")
        return

    for item in registry["versions"]:

        print("\nVersion:", item["version"])
        print("Status:", item["status"])

        metrics = item.get("metrics", {})

        print("Accuracy:", metrics.get("accuracy"))
        print("Toxic precision:", metrics.get("toxic_precision"))
        print("Toxic recall:", metrics.get("toxic_recall"))
        print("Toxic F1:", metrics.get("toxic_f1"))


if __name__ == "__main__":
    list_versions()
