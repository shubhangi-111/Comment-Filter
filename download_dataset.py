import os
import pandas as pd

DATA_DIR = os.path.join("data", "jigsaw-unintended-bias-in-toxicity-classification")
CSV_PATH = os.path.join(DATA_DIR, "train.csv")

os.makedirs(DATA_DIR, exist_ok=True)

if os.path.exists(CSV_PATH) and os.path.getsize(CSV_PATH) > 0:
    print(f"Dataset CSV already exists at {CSV_PATH} ({os.path.getsize(CSV_PATH)} bytes).")
else:
    print("Downloading Civil Comments dataset from HuggingFace...")
    from datasets import load_dataset

    ds = load_dataset("google/civil_comments", split="train")
    print(f"Dataset loaded: {len(ds)} records. Converting to pandas DataFrame...")
    df = pd.DataFrame(ds)

    if "text" in df.columns and "comment_text" not in df.columns:
        df = df.rename(columns={"text": "comment_text"})
    if "toxicity" in df.columns and "target" not in df.columns:
        df = df.rename(columns={"toxicity": "target"})

    print(f"Saving dataset CSV to {CSV_PATH}...")
    df.to_csv(CSV_PATH, index=False)
    print("Dataset successfully downloaded and formatted!")
