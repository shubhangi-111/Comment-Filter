from flask import Flask, request, render_template, redirect, url_for, flash
from model.predict import predict_comment

import pandas as pd
from pathlib import Path
from datetime import datetime
import subprocess
import sys
import re


app = Flask(__name__)

app.secret_key = "training-lab-secret-key"

DATA_FILE = Path("data/labelled_comments.csv")


# =========================
# DATASET COUNT
# =========================

def get_dataset_count():

    if not DATA_FILE.exists():
        return 0

    try:
        df = pd.read_csv(DATA_FILE)
        return len(df)

    except Exception:
        return 0


# =========================
# CATEGORY SUGGESTION
# =========================

def suggest_category(comment):

    text = comment.lower()


    threat_patterns = [
        r"\bkill\b",
        r"\bkilling\b",
        r"\bhurt\b",
        r"\bharm\b",
        r"\bshoot\b",
        r"\bshooting\b",
        r"\bstab\b",
        r"\bdie\b",
        r"\bdeath\b",
        r"\bfind you\b",
        r"\bcome for you\b"
    ]

    spam_patterns = [
        r"\bbuy\b.*\bfollowers\b",
        r"\bbuy\b.*\blikes\b",
        r"\bfree money\b",
        r"\bclick here\b",
        r"\bsubscribe\b.*\bnow\b",
        r"\bpromo\b",
        r"\bdiscount\b",
        r"\bwww\.",
        r"https?://"
    ]

    harassment_patterns = [
        r"\bshut up\b",
        r"\bget lost\b",
        r"\bgo away\b",
        r"\byou suck\b",
        r"\bno one likes you\b"
    ]

    abuse_patterns = [
        r"\bidiot\b",
        r"\bstupid\b",
        r"\bdumb\b",
        r"\bmoron\b",
        r"\bjerk\b",
        r"\bloser\b",
        r"\bdisgusting\b",
        r"\bpathetic\b"
    ]


    # Threat gets highest priority

    for pattern in threat_patterns:

        if re.search(pattern, text):
            return "threat"


    # Spam

    for pattern in spam_patterns:

        if re.search(pattern, text):
            return "spam"


    # Harassment

    for pattern in harassment_patterns:

        if re.search(pattern, text):
            return "harassment"


    # Abuse

    for pattern in abuse_patterns:

        if re.search(pattern, text):
            return "abuse"


    return ""


# =========================
# SAVE EXAMPLES
# =========================

def save_examples(rows):

    DATA_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    new_data = pd.DataFrame(rows)


    if DATA_FILE.exists():

        existing_data = pd.read_csv(DATA_FILE)

        existing_comments = set(
            existing_data["comment"]
            .astype(str)
            .str.strip()
            .str.lower()
        )


        new_data["_comparison"] = (
            new_data["comment"]
            .astype(str)
            .str.strip()
            .str.lower()
        )


        # Remove duplicates inside current batch

        new_data = new_data.drop_duplicates(
            subset=["_comparison"]
        )


        # Remove examples already in dataset

        new_data = new_data[
            ~new_data["_comparison"].isin(
                existing_comments
            )
        ]


        new_data = new_data.drop(
            columns=["_comparison"]
        )


        if new_data.empty:
            return 0


        new_data.to_csv(
            DATA_FILE,
            mode="a",
            header=False,
            index=False
        )


        return len(new_data)


    else:

        new_data.to_csv(
            DATA_FILE,
            index=False
        )

        return len(new_data)


# =========================
# MAIN TRAINING LAB
# =========================

@app.route("/", methods=["GET", "POST"])
def trainer():

    predictions = []


    # =========================
    # GET
    # =========================

    if request.method == "GET":

        return render_template(
            "trainer.html",
            predictions=[],
            dataset_count=get_dataset_count()
        )


    action = request.form.get("action")


    # =========================
    # ANALYZE ALL
    # =========================

    if action == "analyze":

        raw_comments = request.form.get(
            "comments",
            ""
        )


        comments = [
            line.strip()
            for line in raw_comments.splitlines()
            if line.strip()
        ]


        if not comments:

            flash(
                "Please enter at least one comment."
            )

            return redirect(
                url_for("trainer")
            )


        for comment in comments:

            result = predict_comment(comment)

            category = suggest_category(
                comment
            )


            predictions.append({

                "comment": comment,

                "label": result["label"],

                "confidence": round(
                    result["confidence"] * 100,
                    2
                ),

                "category": category

            })


        return render_template(
            "trainer.html",
            predictions=predictions,
            dataset_count=get_dataset_count()
        )


    # =========================
    # SAVE ALL
    # =========================

    elif action == "save":

        comments = request.form.getlist(
            "comment"
        )

        categories = request.form.getlist(
            "category"
        )


        labels = []

        for i in range(len(comments)):

            labels.append(
                request.form.get(
                    f"toxic_label_{i}"
                )
            )


        rows = []


        for comment, label, category in zip(
            comments,
            labels,
            categories
        ):

            if label not in ["0", "1"]:
                continue


            rows.append({

                "comment": comment,

                "toxic_label": int(label),

                "category": category,

                "source": "manual",

                "timestamp": datetime.now().isoformat(
                    timespec="seconds"
                )

            })


        if not rows:

            flash(
                "Nothing was saved. "
                "Please label your comments."
            )


        else:

            saved_count = save_examples(
                rows
            )

            duplicate_count = (
                len(rows) - saved_count
            )


            if saved_count > 0:

                message = (
                    f"✓ Saved {saved_count} "
                    f"new examples."
                )

                if duplicate_count > 0:

                    message += (
                        f" Skipped "
                        f"{duplicate_count} "
                        f"duplicate(s)."
                    )

                flash(message)


            else:

                flash(
                    "⚠ All submitted comments "
                    "already exist in the dataset."
                )


        return redirect(
            url_for("trainer")
        )


    # =========================
    # RETRAIN
    # =========================

    elif action == "retrain":

        result = subprocess.run(

            [
                sys.executable,
                "-m",
                "model.train"
            ],

            capture_output=True,

            text=True

        )


        if result.returncode == 0:

            flash(
                "✓ Model retrained successfully.\n\n"
                + result.stdout
            )

        else:

            flash(
                "❌ Retraining failed.\n\n"
                + result.stderr
            )


        return redirect(
            url_for("trainer")
        )


    return redirect(
        url_for("trainer")
    )


if __name__ == "__main__":

    app.run(
        debug=True,
        port=5001
    )