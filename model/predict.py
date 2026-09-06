import pickle
import re
from pathlib import Path
from preprocessing.clean_data import clean_text, clean_batch

# Resolve model files relative to this script directory for portability
BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "model.pkl"
VECTORIZER_PATH = BASE_DIR / "vectorizer.pkl"

with open(MODEL_PATH, "rb") as f:
    model = pickle.load(f)

with open(VECTORIZER_PATH, "rb") as f:
    vectorizer = pickle.load(f)

# Leetspeak & Evasion Character Mapping
LEET_MAP = str.maketrans({
    '@': 'a', '$': 's', '0': 'o', '1': 'i', '3': 'e', '!': 'i', '5': 's', '7': 't', '*': ''
})

import json

RULES_FILE = BASE_DIR.parent / "rules" / "harassment_patterns.json"

if RULES_FILE.exists():
    with open(RULES_FILE, "r", encoding="utf-8") as f:
        rules_data = json.load(f)
    SLUR_PLACEHOLDERS = set(rules_data.get("slur_placeholders", []))
    HINGLISH_HINDI_TOXIC_TERMS = set(rules_data.get("hinglish_hindi_toxic_terms", []))
    raw_patterns = rules_data.get("creator_protection_patterns", [])
    COMPILED_PATTERNS = [(re.compile(p, re.IGNORECASE), cat) for p, cat in raw_patterns]
else:
    SLUR_PLACEHOLDERS = {
        "r-word", "r word", "rword", "f-word", "f word", "fword",
        "n-word", "n word", "nword", "c-word", "c word", "b-word", "b word"
    }
    HINGLISH_HINDI_TOXIC_TERMS = {"randi", "chinaar", "bhadwi", "chutiya", "bhenchod", "madarchod", "bsdk", "bhosdike", "gandu", "harami", "kys"}
    COMPILED_PATTERNS = [(re.compile(r'\bkys\b', re.IGNORECASE), "Severe Threat / Self-Harm")]

def normalize_text_for_evasions(text):
    """
    Normalizes text to defeat common obfuscations & leetspeak.
    """
    if not isinstance(text, str):
        return "", ""
    
    normalized = text.lower().translate(LEET_MAP)
    normalized_no_dots = re.sub(r'(?<=\b\w)[._ ](?=\w\b)', '', normalized)
    return normalized, normalized_no_dots

def detect_threats_and_slurs(text):
    """
    Scans text for creator safety risks:
    1. Slur euphemisms (R-word, F-word, etc.)
    2. Creator harassment, solicitation, slut-shaming, objectification phrase patterns
    3. Hinglish & Hindi profanity terms (chinaar, bhadwi, etc.)
    """
    if not isinstance(text, str):
        return False, None, 0.0

    raw_lower = text.lower().strip()
    norm_text, norm_no_dots = normalize_text_for_evasions(text)

    # A. Check Slur Placeholders / Euphemisms
    for placeholder in SLUR_PLACEHOLDERS:
        if placeholder in raw_lower or placeholder in norm_text:
            return True, "Harassment / Slur Euphemism", 0.99

    # B. Check Creator Protection Phrase Patterns (Solicitation, Objectification, Death Threats)
    for regex, cat in COMPILED_PATTERNS:
        if regex.search(raw_lower) or regex.search(norm_text) or regex.search(norm_no_dots):
            return True, cat, 0.99

    # C. Check Hinglish & Hindi Profanity Single Terms
    tokens = set(re.findall(r'\w+', norm_text)).union(set(re.findall(r'\w+', norm_no_dots)))
    matches = tokens.intersection(HINGLISH_HINDI_TOXIC_TERMS)
    if matches:
        confidence = min(0.99, 0.95 + (len(matches) - 1) * 0.02)
        return True, "Hinglish/Hindi Profanity & Slurs", round(confidence, 4)

    return False, None, 0.0

def predict_comment_detail(comment):
    """
    Predicts toxicity for a single comment string with confidence score & category.
    Creator-Protection Engine: Threat Detection + Misogyny Shield + ML Model.
    """
    # 1. Creator Safety Shield
    is_rule_toxic, category, rule_conf = detect_threats_and_slurs(comment)
    if is_rule_toxic:
        is_severe = "Severe Threat" in category or "Acid" in category or "Doxxing" in category or "Sexual Violence" in category
        return {
            "comment": comment,
            "is_toxic": True,
            "label": "Toxic",
            "category": category,
            "confidence": rule_conf,
            "threat_detected": is_severe
        }

    # 2. English Machine Learning Model (TF-IDF + Logistic Regression)
    cleaned = clean_text(comment)
    vectorized = vectorizer.transform([cleaned])
    prediction = model.predict(vectorized)[0]
    probabilities = model.predict_proba(vectorized)[0]
    
    is_toxic = bool(prediction == 1)
    confidence = float(probabilities[1] if is_toxic else probabilities[0])

    return {
        "comment": comment,
        "is_toxic": is_toxic,
        "label": "Toxic" if is_toxic else "Non-Toxic",
        "category": "General Toxicity" if is_toxic else "Safe",
        "confidence": round(confidence, 4),
        "threat_detected": False
    }

def predict_comments_batch(comments: list):
    """
    Predicts toxicity for a batch of comments concurrently to optimize ML operations.
    """
    results = []
    
    # Track which indices need ML prediction
    ml_needed_indices = []
    ml_texts_cleaned = []
    
    # 1. First Pass: Apply rule-based safety shield
    for i, comment in enumerate(comments):
        is_rule_toxic, category, rule_conf = detect_threats_and_slurs(comment)
        if is_rule_toxic:
            is_severe = "Severe Threat" in category or "Acid" in category or "Doxxing" in category or "Sexual Violence" in category
            results.append({
                "comment": comment,
                "is_toxic": True,
                "label": "Toxic",
                "category": category,
                "confidence": rule_conf,
                "threat_detected": is_severe
            })
        else:
            # Placeholder for ML processing
            results.append(None)
            ml_needed_indices.append(i)
            ml_texts_cleaned.append(clean_text(comment))
            
    # 2. ML Batch Prediction
    if ml_texts_cleaned:
        vectorized = vectorizer.transform(ml_texts_cleaned)
        predictions = model.predict(vectorized)
        probabilities = model.predict_proba(vectorized)
        
        for idx_in_ml, original_idx in enumerate(ml_needed_indices):
            pred = predictions[idx_in_ml]
            prob = probabilities[idx_in_ml]
            is_toxic = bool(pred == 1)
            confidence = float(prob[1] if is_toxic else prob[0])
            
            results[original_idx] = {
                "comment": comments[original_idx],
                "is_toxic": is_toxic,
                "label": "Toxic" if is_toxic else "Non-Toxic",
                "category": "General Toxicity" if is_toxic else "Safe",
                "confidence": round(confidence, 4),
                "threat_detected": False
            }
            
    return results
