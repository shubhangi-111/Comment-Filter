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