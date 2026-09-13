from pathlib import Path
import pandas as pd
import pickle

from preprocessing.clean_data import clean_text
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report


# -------------------------
# 1. Load data
# -------------------------

df = pd.read_csv(
    "data/jigsaw-unintended-bias-in-toxicity-classification/train.csv"
)

print("Data loaded")

df = df.dropna(subset=["comment_text"])

print("Nulls removed")

df = df.sample(20000, random_state=42)

print("Data sampled")


# -------------------------
# 2. Create labels
# -------------------------

df["label"] = df["target"].apply(
    lambda x: 1 if x >= 0.5 else 0
)

X = df["comment_text"].apply(clean_text)
y = df["label"]

# -------------------------
# 2.5 Add manually labelled examples
# -------------------------

manual_file = "data/labelled_comments.csv"

if Path(manual_file).exists():

    manual_df = pd.read_csv(manual_file)

    manual_df = manual_df.dropna(
        subset=["comment", "toxic_label"]
    )

    manual_X = manual_df["comment"].apply(clean_text)
    manual_y = manual_df["toxic_label"]

    X = pd.concat([
        X,
        manual_X
    ], ignore_index=True)

    y = pd.concat([
        y,
        manual_y
    ], ignore_index=True)

    print(
        f"Added {len(manual_df)} manually labelled examples"
    )

# -------------------------
# 3. Split data
# -------------------------

print("Splitting data...")

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42,
    stratify=y
)


# -------------------------
# 4. TF-IDF
# -------------------------

print("Starting vectorization...")

vectorizer = TfidfVectorizer(max_features=5000)

X_train_vectorized = vectorizer.fit_transform(X_train)
X_test_vectorized = vectorizer.transform(X_test)

print("Vectorization complete")


# -------------------------
# 5. Train model
# -------------------------

print("Training model...")

model = LogisticRegression(
    max_iter=1000,
    class_weight="balanced"
)

model.fit(X_train_vectorized, y_train)

print("Model trained")


# -------------------------
# 6. Evaluate
# -------------------------

print("Evaluating model...")

y_pred = model.predict(X_test_vectorized)

accuracy = accuracy_score(y_test, y_pred)

print("Accuracy:", accuracy)

print("Detailed report:")
print(classification_report(y_test, y_pred))


# -------------------------
# 7. Save artifacts
# -------------------------

with open("model/model.pkl", "wb") as f:
    pickle.dump(model, f)

with open("model/vectorizer.pkl", "wb") as f:
    pickle.dump(vectorizer, f)

print("Model and vectorizer saved")