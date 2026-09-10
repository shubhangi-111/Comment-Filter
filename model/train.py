import sys
import os
import pandas as pd
import pickle

# Ensure workspace root is in sys.path for relative imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, accuracy_score
from preprocessing.clean_data import clean_batch

print("Loading dataset...")
df = pd.read_csv("data/jigsaw-unintended-bias-in-toxicity-classification/train.csv")
print("Nulls removed")
df = df.dropna(subset=["comment_text"])

# Define toxic label threshold
df["label"] = df["target"].apply(lambda x: 1 if x >= 0.5 else 0)

# Create a balanced dataset by matching toxic and non-toxic sample sizes (~288k total)
toxic_df = df[df["label"] == 1]
nontoxic_df = df[df["label"] == 0].sample(n=len(toxic_df), random_state=42)

balanced_df = pd.concat([toxic_df, nontoxic_df]).sample(frac=1.0, random_state=42)
print(f"Balanced dataset created with {len(balanced_df)} samples ({len(toxic_df)} toxic, {len(nontoxic_df)} non-toxic)")

print("Cleaning text...")
X_cleaned = clean_batch(balanced_df["comment_text"].tolist())
y = balanced_df["label"].values

print("Starting vectorization (unigrams + bigrams, 40,000 max features)...")
vectorizer = TfidfVectorizer(max_features=40000, ngram_range=(1, 2), sublinear_tf=True)
X_vectorized = vectorizer.fit_transform(X_cleaned)
print("Vectorization complete")

print("Splitting train/test split...")
X_train, X_test, y_train, y_test = train_test_split(
    X_vectorized, y, test_size=0.15, random_state=42
)

print("Training model (LogisticRegression with balanced class weights)...")
model = LogisticRegression(C=2.5, max_iter=1000, class_weight="balanced")
model.fit(X_train, y_train)
print("Model trained successfully!")

print("Evaluating model performance...")
y_pred = model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)
print("Accuracy:", accuracy)

print("Detailed classification report:")
print(classification_report(y_test, y_pred, target_names=["Non-Toxic", "Toxic"]))

with open("model/model.pkl", "wb") as f:
    pickle.dump(model, f)

with open("model/vectorizer.pkl", "wb") as f:
    pickle.dump(vectorizer, f)

print("Model and vectorizer updated and saved to model/ directory!")