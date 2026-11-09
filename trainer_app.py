from flask import (
    Flask,
    request,
    render_template,
    redirect,
    url_for,
    flash,
    send_from_directory
)

from model.predict import predict_comment

import pandas as pd
from pathlib import Path
from datetime import datetime
import subprocess
import sys
import re
import uuid
import json

import pytesseract
from PIL import Image


app = Flask(__name__)

app.secret_key = "training-lab-secret-key"


# ============================================================
# PATHS
# ============================================================

DATA_FILE = Path("data/labelled_comments.csv")

UPLOAD_FOLDER = Path("uploads")

ALLOWED_EXTENSIONS = {
    "jpg",
    "jpeg",
    "png"
}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


# ============================================================
# TESSERACT CONFIGURATION
# ============================================================

TESSERACT_PATH = Path(
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

if TESSERACT_PATH.exists():

    pytesseract.pytesseract.tesseract_cmd = str(
        TESSERACT_PATH
    )


# ============================================================
# DATASET HELPERS
# ============================================================

def get_dataset_count():

    if not DATA_FILE.exists():
        return 0

    try:

        df = pd.read_csv(DATA_FILE)

        return len(df)

    except Exception:

        return 0


# ============================================================
# MODEL VERSION DASHBOARD
# ============================================================

REGISTRY_FILE = Path("model/registry.json")
LATEST_EVALUATION_FILE = Path(
    "model/evaluations/latest_comparison.json"
)


def _read_json_file(filepath):

    if not filepath.exists():
        return {}

    try:

        with filepath.open("r", encoding="utf-8") as file:
            data = json.load(file)

        return data if isinstance(data, dict) else {}

    except (OSError, json.JSONDecodeError):

        return {}


def _metric_value(metrics, *keys):

    if not isinstance(metrics, dict):
        return None

    for key in keys:

        value = metrics.get(key)

        if value is not None:

            try:
                return float(value)
            except (TypeError, ValueError):
                return value

    return None


def _format_metric(value):

    if value is None:
        return "—"

    try:

        number = float(value)

        if number <= 1:
            return f"{number * 100:.2f}%"

        return f"{number:.2f}%"

    except (TypeError, ValueError):

        return str(value)


def get_model_dashboard():

    registry = _read_json_file(REGISTRY_FILE)
    evaluation = _read_json_file(LATEST_EVALUATION_FILE)

    active_version = registry.get("active_version", "legacy")
    versions = registry.get("versions", {})

    if not isinstance(versions, dict):
        versions = {}

    active_metadata = versions.get(active_version, {})

    if not isinstance(active_metadata, dict):
        active_metadata = {}

    active_metrics = active_metadata.get("metrics", {})

    if not isinstance(active_metrics, dict):
        active_metrics = {}

    comparison_rows = (
        evaluation.get("results")
        or evaluation.get("models")
        or evaluation.get("comparisons")
        or []
    )

    if isinstance(comparison_rows, dict):

        comparison_rows = [
            {"version": key, **value}
            for key, value in comparison_rows.items()
            if isinstance(value, dict)
        ]

    if not isinstance(comparison_rows, list):
        comparison_rows = []

    evaluation_by_version = {}

    for row in comparison_rows:

        if not isinstance(row, dict):
            continue

        version = (
            row.get("version")
            or row.get("model_version")
            or row.get("name")
        )

        if version:
            evaluation_by_version[str(version)] = row

    active_evaluation = evaluation_by_version.get(
        str(active_version), {}
    )

    if not active_metrics and isinstance(active_evaluation, dict):

        active_metrics = active_evaluation.get(
            "metrics", active_evaluation
        )

    active = {
        "version": active_version,
        "status": "active",
        "accuracy": _format_metric(
            _metric_value(active_metrics, "accuracy")
        ),
        "precision": _format_metric(
            _metric_value(
                active_metrics, "toxic_precision", "precision"
            )
        ),
        "recall": _format_metric(
            _metric_value(
                active_metrics, "toxic_recall", "recall"
            )
        ),
        "f1": _format_metric(
            _metric_value(
                active_metrics, "toxic_f1", "f1", "f1_score"
            )
        )
    }

    candidates = []

    for version, metadata in versions.items():

        if version == active_version:
            continue

        if not isinstance(metadata, dict):
            continue

        status = str(
            metadata.get("status", "candidate")
        ).lower()

        if status not in {"candidate", "rejected", "inactive"}:
            continue

        metrics = metadata.get("metrics", {})

        if not isinstance(metrics, dict):
            metrics = {}

        evaluation_row = evaluation_by_version.get(
            str(version), {}
        )

        if not metrics and isinstance(evaluation_row, dict):

            metrics = evaluation_row.get(
                "metrics", evaluation_row
            )

        candidates.append({
            "version": version,
            "status": status,
            "accuracy": _format_metric(
                _metric_value(metrics, "accuracy")
            ),
            "precision": _format_metric(
                _metric_value(
                    metrics, "toxic_precision", "precision"
                )
            ),
            "recall": _format_metric(
                _metric_value(
                    metrics, "toxic_recall", "recall"
                )
            ),
            "f1": _format_metric(
                _metric_value(
                    metrics, "toxic_f1", "f1", "f1_score"
                )
            )
        })

    candidates.reverse()

    return {
        "active": active,
        "candidates": candidates,
        "has_previous_version": bool(
            registry.get("previous_active_version")
        )
    }


@app.context_processor
def inject_model_dashboard():

    return {
        "model_dashboard": get_model_dashboard()
    }


def run_model_management_command(command, version=None):

    command_args = [
        sys.executable,
        "-m",
        "model.manage_models",
        command
    ]

    if version:
        command_args.append(version)

    return subprocess.run(
        command_args,
        capture_output=True,
        text=True
    )


# ============================================================
# FILE HELPERS
# ============================================================

def allowed_file(filename):

    return (
        "." in filename
        and filename.rsplit(
            ".",
            1
        )[1].lower()
        in ALLOWED_EXTENSIONS
    )


@app.route("/uploads/<filename>")
def uploaded_file(filename):

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename
    )


# ============================================================
# CATEGORY SUGGESTION
# ============================================================

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

    for pattern in threat_patterns:

        if re.search(pattern, text):
            return "threat"

    for pattern in spam_patterns:

        if re.search(pattern, text):
            return "spam"

    for pattern in harassment_patterns:

        if re.search(pattern, text):
            return "harassment"

    for pattern in abuse_patterns:

        if re.search(pattern, text):
            return "abuse"

    return ""


# ============================================================
# OCR
# ============================================================

def extract_text_from_image(filepath):

    try:

        image = Image.open(filepath)

        extracted_text = pytesseract.image_to_string(
            image
        )

        return extracted_text.strip()

    except Exception as error:

        print(
            "OCR error:",
            error
        )

        return None


# ============================================================
# OCR / COMMENT EXTRACTION HELPERS
# ============================================================

def is_time_line(text):

    return bool(
        re.fullmatch(
            r"\d+\s*[smhdwy]",
            text.strip().lower()
        )
    )


def is_metadata_line(line):

    text = line.strip().lower()

    if not text:
        return True

    metadata_phrases = [
        "see translation",
        "view replies",
        "view reply",
        "edited",
        "reply",
        "replies",
        "follow",
        "following",
        "likes",
        "like",
        "comments",
        "share",
        "send",
        "message",
        "more",
        "translate"
    ]

    for phrase in metadata_phrases:

        if phrase in text:

            return True

    if is_time_line(text):

        return True

    # Lines made almost entirely from punctuation,
    # separators, or numbers.
    if re.fullmatch(
        r"[\d\s.,|*_—–\-@]+",
        text
    ):

        return True

    return False


def looks_like_hashtag_block(line):

    text = line.strip()

    if not text:
        return True

    hashtag_count = text.count("#")

    if hashtag_count >= 2:
        return True

    return False


def clean_extracted_comment(comment):

    # Collapse OCR whitespace.
    comment = re.sub(
        r"\s+",
        " ",
        comment
    ).strip()

    # Remove common OCR separator characters
    # from the beginning and end.
    comment = re.sub(
        r"^[|*_—–\-]+",
        "",
        comment
    ).strip()

    comment = re.sub(
        r"[|*_—–\-]+$",
        "",
        comment
    ).strip()

    # Remove stray @ characters at the edges.
    comment = re.sub(
        r"^@\s*",
        "",
        comment
    ).strip()

    comment = re.sub(
        r"\s*@\s*$",
        "",
        comment
    ).strip()

    return comment


def clean_username(text):

    """
    Cleans common OCR variations of Instagram usernames.

    Examples:

        @username@
        @ username @
        username
    """

    text = text.strip()

    text = re.sub(
        r"^@\s*",
        "",
        text
    )

    text = re.sub(
        r"\s*@\s*$",
        "",
        text
    )

    return text.strip()


def looks_like_username(text):

    """
    Determines whether a line looks like an Instagram username.

    We deliberately require either:

    - an @ symbol, OR
    - a username containing . or _, OR
    - a short username-like token with no spaces.

    This prevents ordinary comments such as
    "you suck" from being interpreted as usernames.
    """

    raw = text.strip()

    if not raw:
        return False

    has_at = "@" in raw

    cleaned = clean_username(raw)

    # Remove accidental spaces around @.
    cleaned = cleaned.replace(
        " ",
        ""
    )

    username_pattern = re.fullmatch(
        r"[A-Za-z0-9._]{2,30}",
        cleaned
    )

    if not username_pattern:
        return False

    if has_at:
        return True

    if "." in cleaned or "_" in cleaned:
        return True

    return False


def split_username_and_comment(line):

    """
    Attempts to split a single OCR line into:

        username + comment

    Supports forms such as:

        username hello there
        @username hello there
        @ username @ hello there
        username @ hello there
    """

    text = line.strip()

    if not text:
        return None, None

    # --------------------------------------------------------
    # Pattern 1:
    #
    # @ username @ comment
    #
    # This is useful for OCR output where Instagram's
    # visual separators are interpreted as @ characters.
    # --------------------------------------------------------

    match = re.match(
        r"^@\s*([A-Za-z0-9._]{2,30})\s*@\s+(.+)$",
        text
    )

    if match:

        username = match.group(1)

        comment = match.group(2)

        return username, comment


    # --------------------------------------------------------
    # Pattern 2:
    #
    # @username comment
    # --------------------------------------------------------

    match = re.match(
        r"^@\s*([A-Za-z0-9._]{2,30})\s+(.+)$",
        text
    )

    if match:

        username = match.group(1)

        comment = match.group(2)

        return username, comment


    # --------------------------------------------------------
    # Pattern 3:
    #
    # username @ comment
    # --------------------------------------------------------

    match = re.match(
        r"^([A-Za-z0-9._]{2,30})\s*@\s+(.+)$",
        text
    )

    if match:

        username = match.group(1)

        comment = match.group(2)

        return username, comment


    # --------------------------------------------------------
    # Pattern 4:
    #
    # username comment
    #
    # Only accept this when the first token looks
    # strongly like a username.
    # --------------------------------------------------------

    match = re.match(
        r"^([A-Za-z0-9._]{2,30})\s+(.+)$",
        text
    )

    if match:

        username = match.group(1)

        comment = match.group(2)

        if (
            "." in username
            or "_" in username
            or "@" in text
        ):

            return username, comment


    return None, None


def extract_comments_from_text(raw_text):

    """
    First-pass Instagram comment extractor.

    Designed for OCR output rather than perfectly structured
    text.

    It handles:

    1. username + comment on the same line
    2. @username + comment
    3. username on one line and comment on the next
    4. OCR @ separators
    5. multiline comments
    6. Instagram metadata
    7. hashtag blocks
    8. duplicate comments

    Example OCR:

        @ glimpseoflifee @
        @ ae Love these videos Y @
        12h
        View replies (1)

    becomes:

        Love these videos Y
    """

    if not raw_text:
        return []


    # --------------------------------------------------------
    # Normalize line endings.
    # --------------------------------------------------------

    raw_text = raw_text.replace(
        "\r\n",
        "\n"
    )

    raw_text = raw_text.replace(
        "\r",
        "\n"
    )


    lines = [
        line.strip()
        for line in raw_text.splitlines()
        if line.strip()
    ]


    comments = []

    current_comment = None

    pending_username = None


    # --------------------------------------------------------
    # Process every OCR line.
    # --------------------------------------------------------

    for line in lines:


        # ====================================================
        # METADATA
        # ====================================================

        if is_metadata_line(line):

            continue


        # ====================================================
        # HASHTAGS
        # ====================================================

        if looks_like_hashtag_block(line):

            continue


        # ====================================================
        # SAME-LINE USERNAME + COMMENT
        # ====================================================

        username, comment_text = (
            split_username_and_comment(line)
        )

        if username and comment_text:

            # Save previous multiline comment.
            if current_comment:

                comments.append(
                    clean_extracted_comment(
                        current_comment
                    )
                )

            current_comment = clean_extracted_comment(
                comment_text
            )

            pending_username = None

            continue


        # ====================================================
        # USERNAME-ONLY LINE
        # ====================================================

        if looks_like_username(line):

            cleaned_username = clean_username(
                line
            )

            # Save any previous comment first.
            if current_comment:

                comments.append(
                    clean_extracted_comment(
                        current_comment
                    )

                )

                current_comment = None

            pending_username = cleaned_username

            continue


        # ====================================================
        # COMMENT AFTER USERNAME
        # ====================================================

        if pending_username:

            current_comment = clean_extracted_comment(
                line
            )

            pending_username = None

            continue


        # ====================================================
        # MULTILINE COMMENT
        # ====================================================

        if current_comment:

            current_comment += (
                " " + clean_extracted_comment(line)
            )

            continue


        # ====================================================
        # FALLBACK
        # ====================================================

        # If OCR gives us a standalone sentence and we
        # haven't found a username, preserve it rather than
        # throwing the text away.
        #
        # This is intentionally conservative about obvious
        # UI/metadata lines, which were already filtered above.

        cleaned_line = clean_extracted_comment(
            line
        )

        if len(cleaned_line) >= 3:

            current_comment = cleaned_line


    # --------------------------------------------------------
    # Save final comment.
    # --------------------------------------------------------

    if current_comment:

        comments.append(
            clean_extracted_comment(
                current_comment
            )
        )


    # --------------------------------------------------------
    # Final cleanup + deduplication.
    # --------------------------------------------------------

    cleaned_comments = []

    seen = set()

    for comment in comments:

        comment = clean_extracted_comment(
            comment
        )

        if len(comment) < 2:
            continue

        comparison = comment.lower()

        if comparison in seen:
            continue

        seen.add(comparison)

        cleaned_comments.append(
            comment
        )


    return cleaned_comments


# ============================================================
# DATASET SAVING
# ============================================================

def save_examples(rows):

    DATA_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    new_data = pd.DataFrame(rows)

    if DATA_FILE.exists():

        existing_data = pd.read_csv(
            DATA_FILE
        )

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

        new_data = new_data.drop_duplicates(
            subset=["_comparison"]
        )

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


# ============================================================
# TRAINING LAB
# ============================================================

@app.route(
    "/",
    methods=["GET", "POST"]
)
def trainer():

    predictions = []


    # ========================================================
    # GET
    # ========================================================

    if request.method == "GET":

        return render_template(
            "trainer.html",
            predictions=[],
            dataset_count=get_dataset_count(),
            uploaded_image=None,
            extracted_text=None,
            extracted_comments=[],
            source=""
        )


    action = request.form.get(
        "action"
    )


    # ========================================================
    # IMAGE UPLOAD + OCR
    # ========================================================

    if action == "upload_image":

        image = request.files.get(
            "image"
        )

        if image is None or image.filename == "":

            flash(
                "Please select an image first."
            )

            return redirect(
                url_for("trainer")
            )


        if not allowed_file(
            image.filename
        ):

            flash(
                "Invalid image type. "
                "Please upload JPG, JPEG, or PNG."
            )

            return redirect(
                url_for("trainer")
            )


        UPLOAD_FOLDER.mkdir(
            parents=True,
            exist_ok=True
        )


        extension = image.filename.rsplit(
            ".",
            1
        )[1].lower()


        filename = (
            f"{uuid.uuid4().hex}.{extension}"
        )


        filepath = (
            UPLOAD_FOLDER / filename
        )


        image.save(filepath)


        extracted_text = extract_text_from_image(
            filepath
        )


        source = (
            f"screenshot:{filename}"
        )


        if extracted_text is None:

            flash(
                "❌ OCR failed. "
                "The image was uploaded successfully, "
                "but its text could not be extracted."
            )

        elif not extracted_text:

            flash(
                "⚠ Image uploaded, but no text "
                "could be detected."
            )

        else:

            flash(
                "✓ Image uploaded and text extracted successfully."
            )


        return render_template(
            "trainer.html",
            predictions=[],
            dataset_count=get_dataset_count(),
            uploaded_image=filename,
            extracted_text=extracted_text,
            extracted_comments=[],
            source=source
        )


    # ========================================================
    # EXTRACT COMMENTS
    # ========================================================

    if action == "extract_comments":

        corrected_text = request.form.get(
            "ocr_text",
            ""
        )


        uploaded_image = request.form.get(
            "uploaded_image",
            ""
        )


        source = request.form.get(
            "source",
            "screenshot"
        )


        if not corrected_text.strip():

            flash(
                "Please provide OCR text first."
            )

            return redirect(
                url_for("trainer")
            )


        extracted_comments = (
            extract_comments_from_text(
                corrected_text
            )
        )


        if not extracted_comments:

            flash(
                "⚠ No comments could be detected. "
                "Please correct the OCR text or "
                "enter comments manually."
            )

        else:

            flash(
                f"✓ Detected "
                f"{len(extracted_comments)} "
                f"possible comment(s). "
                f"Review them before analysis."
            )


        return render_template(
            "trainer.html",
            predictions=[],
            dataset_count=get_dataset_count(),
            uploaded_image=uploaded_image,
            extracted_text=corrected_text,
            extracted_comments=extracted_comments,
            source=source
        )


    # ========================================================
    # ANALYZE EXTRACTED COMMENTS
    # ========================================================

    if action == "analyze_extracted":

        extracted_comments = request.form.getlist(
            "extracted_comment"
        )


        source = request.form.get(
            "source",
            "screenshot"
        )


        uploaded_image = request.form.get(
            "uploaded_image",
            ""
        )


        comments = [
            comment.strip()
            for comment in extracted_comments
            if comment.strip()
        ]


        if not comments:

            flash(
                "Please provide at least one comment."
            )

            return redirect(
                url_for("trainer")
            )


        for comment in comments:

            result = predict_comment(
                comment
            )


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
            dataset_count=get_dataset_count(),
            uploaded_image=uploaded_image,
            extracted_text=None,
            extracted_comments=[],
            source=source
        )


    # ========================================================
    # ANALYZE MANUAL COMMENTS
    # ========================================================

    if action == "analyze":

        raw_comments = request.form.get(
            "comments",
            ""
        )


        source = request.form.get(
            "source",
            "manual"
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

            result = predict_comment(
                comment
            )


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
            dataset_count=get_dataset_count(),
            uploaded_image=None,
            extracted_text=None,
            extracted_comments=[],
            source=source
        )


    # ========================================================
    # SAVE LABELLED COMMENTS
    # ========================================================

    elif action == "save":

        comments = request.form.getlist(
            "comment"
        )


        categories = request.form.getlist(
            "category"
        )


        sources = request.form.getlist(
            "source"
        )


        labels = []


        for i in range(
            len(comments)
        ):

            labels.append(
                request.form.get(
                    f"toxic_label_{i}"
                )
            )


        rows = []


        for i, (
            comment,
            label,
            category
        ) in enumerate(
            zip(
                comments,
                labels,
                categories
            )
        ):

            if label not in [
                "0",
                "1"
            ]:

                continue


            source = (
                sources[i]
                if i < len(sources)
                else "manual"
            )


            rows.append({

                "comment": comment,

                "toxic_label": int(label),

                "category": category,

                "source": source,

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


    # ========================================================
    # PROMOTE CANDIDATE MODEL
    # ========================================================

    elif action == "promote":

        version = request.form.get(
            "version", ""
        ).strip()

        if not version:

            flash("Please select a candidate model version.")

            return redirect(url_for("trainer"))

        result = run_model_management_command(
            "promote", version
        )

        output = (
            result.stdout.strip()
            or result.stderr.strip()
            or "No command output was returned."
        )

        if result.returncode == 0:

            flash(
                "✓ Model promotion completed.\n\n"
                + output
                + "\n\nRestart both Flask applications "
                "to load the newly active model."
            )

        else:

            flash(
                "❌ Model promotion was not completed.\n\n"
                + output
            )

        return redirect(url_for("trainer"))


    # ========================================================
    # ROLLBACK ACTIVE MODEL
    # ========================================================

    elif action == "rollback":

        result = run_model_management_command("rollback")

        output = (
            result.stdout.strip()
            or result.stderr.strip()
            or "No command output was returned."
        )

        if result.returncode == 0:

            flash(
                "✓ Model rollback completed.\n\n"
                + output
                + "\n\nRestart both Flask applications "
                "to load the restored model."
            )

        else:

            flash(
                "❌ Model rollback was not completed.\n\n"
                + output
            )

        return redirect(url_for("trainer"))


    # ========================================================
    # RETRAIN
    # ========================================================

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


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":

    app.run(
        debug=True,
        port=5001
    )