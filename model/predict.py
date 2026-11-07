
import pickle

from preprocessing.clean_data import clean_text
from model.registry import get_active_model_paths


# ============================================================
# LOAD ACTIVE MODEL
# ============================================================

active_model = get_active_model_paths()

print("Loading model version:", active_model["version"])

with open(active_model["model"], "rb") as file:
    model = pickle.load(file)

with open(active_model["vectorizer"], "rb") as file:
    vectorizer = pickle.load(file)


# ============================================================
# PREDICTION FUNCTION
# ============================================================

def predict_comment(comment):

    cleaned = clean_text(comment)

    vectorized = vectorizer.transform([cleaned])

    prediction = model.predict(vectorized)[0]

    probability = model.predict_proba(vectorized)[0]

    confidence = max(probability)

    label = "Toxic" if prediction == 1 else "Non-Toxic"

    return {
        "label": label,
        "confidence": confidence,
        "model_version": active_model["version"]
    }


# ============================================================
# MANUAL TESTING
# ============================================================

if __name__ == "__main__":

    while True:

        text = input("\nEnter a comment (or type 'exit'): ")

        if text.lower().strip() == "exit":
            break

        result = predict_comment(text)

        print("\nResult:", result["label"])

        print(
            "Confidence:",
            round(result["confidence"] * 100, 2),
            "%"
        )

        print(
            "Model version:",
            result["model_version"]
        )
