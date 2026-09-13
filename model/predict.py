import pickle
from preprocessing.clean_data import clean_text


with open("model/model.pkl", "rb") as f:
    model = pickle.load(f)

with open("model/vectorizer.pkl", "rb") as f:
    vectorizer = pickle.load(f)


def predict_comment(comment):
    cleaned = clean_text(comment)
    vectorized = vectorizer.transform([cleaned])

    prediction = model.predict(vectorized)[0]
    probability = model.predict_proba(vectorized)[0]

    confidence = max(probability)

    label = "Toxic" if prediction == 1 else "Non-Toxic"

    return {
        "label": label,
        "confidence": confidence
    }


if __name__ == "__main__":
    text = input("Enter comment: ")

    result = predict_comment(text)

    print("Result:", result["label"])
    print("Confidence:", round(result["confidence"] * 100, 2), "%")