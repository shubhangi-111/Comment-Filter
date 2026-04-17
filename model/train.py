import pandas as pd

df = pd.read_csv("data/jigsaw-unintended-bias-in-toxicity-classification/train.csv")
print("Data loaded")

df = df.dropna(subset=["comment_text"])
print("Nulls removed")

df = df.sample(20000, random_state=42)
print("Data sampled")

#print(df.columns)
#print(df.head())

df["label"] = df["target"].apply(lambda x: 1 if x >= 0.5 else 0)

X=df["comment_text"]
y=df["label"]

print("Starting vectorization...")



from sklearn.feature_extraction.text import TfidfVectorizer

vectorizer = TfidfVectorizer(max_features=5000)

X_vectorized = vectorizer.fit_transform(X)

print("Vectorization complete")



from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression

print("Splitting data...")

X_train, X_test, y_train, y_test = train_test_split(
    X_vectorized, y, test_size=0.2, random_state=42
)

print("Training model...")

model = LogisticRegression(max_iter=1000)
model.fit(X_train, y_train)

print("Model trained")



from sklearn.metrics import accuracy_score

print("Evaluating model...")

y_pred = model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)

print("Accuracy:", accuracy)



from sklearn.metrics import classification_report

print("Detailed report:")
print(classification_report(y_test, y_pred))



import pickle

with open("model/model.pkl", "wb") as f:
    pickle.dump(model, f)

with open("model/vectorizer.pkl", "wb") as f:
    pickle.dump(vectorizer, f)

print("Model and vectorizer saved")