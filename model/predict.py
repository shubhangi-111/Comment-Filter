import pickle
from preprocessing.clean_data import clean_text

with open("model/model.pkl", "rb") as f:
    model = pickle.load(f)

with open("model/vectorizer.pkl", "rb") as f:
    vectorizer = pickle.load(f)


def predict_comment(comment):
    cleaned = clean_text(comment)
    vectorized = vectorizer.transform([cleaned])
    prediction = model.predict(vectorized)

    return "Toxic" if prediction[0] == 1 else "Non-Toxic"

if __name__ == "__main__":
    text = input("Enter comment: ")
    print("Result:", predict_comment(text))