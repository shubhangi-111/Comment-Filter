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

# 1. Slur Euphemisms & Explicit Placeholder Evasions
SLUR_PLACEHOLDERS = {
    "r-word", "r word", "rword", "f-word", "f word", "fword",
    "n-word", "n word", "nword", "c-word", "c word", "b-word", "b word"
}

# 2. Comprehensive Hinglish & Hindi Profanity Lexicon (Single Terms)
HINGLISH_HINDI_TOXIC_TERMS = {
    # Hinglish (Roman Script)
    "randi", "randii", "rundi", "r4ndi", "r@ndi", "randiya", "randia",
    "chinaar", "chinar", "chinhar", "bhadwi", "bhadwii", "bhadwe", "bhadwa",
    "gasti", "gashti", "rakhail", "kuttiya", "kamini", "chutiya", "chutiye",
    "chutiyap", "chutiyapa", "chootia", "bhenchod", "bhenchods", "bhanchod",
    "madarchod", "madarchode", "maderchod", "bsdk", "bhosdike", "bhosdika",
    "bhosadike", "gand", "gaand", "gandu", "gaandu", "harami", "haramkhor",
    "lauda", "lode", "lodu", "lawde", "loda", "saale", "saala", "choot", "chut",
    "tatte", "tatta", "jhant", "jhat", "bhosdi", "bhosada", "hijra", "chakka",
    
    # Devanagari Hindi Script
    "रंडी", "भोसड़ीके", "भोसडीके", "बहनचोद", "मादरचोद", "गांडू", "गांड", "हरामी",
    "चूतिया", "चूतिये", "लौड़ा", "लौड़े", "लोड़े", "साले", "साला", "कमीने", "कमीना",
    "भड़वा", "भड़वी", "भड़वी", "छिनाल", "छिनार", "गश्ती", "रखैल", "कुतिया", "झंट"
}

# 3. Categorized Creator Protection Threat & Harassment Phrase Patterns
CREATOR_PROTECTION_PATTERNS = [
    # A. Sexual Harassment & Solicitation
    (r'\bkitne?\s+(me|mein|mein?)\s+(degi|milegi|deli|hoga|bata)\b', "Sexual Harassment & Solicitation"),
    (r'\brate\s+(kya|kitna|bata|hoga)\b', "Sexual Harassment & Solicitation"),
    (r'\b(ek\s+baar|1\s+baar)\s+(dila\s*de|de\s*de|degi|mila\s*de)\b', "Sexual Harassment"),
    (r'\b(number|contact|phone)\s+(de|do|dedo|bhejo)\b', "Unsolicited Contact Harassment"),

    # B. Slut-Shaming & Creepy Intimidation
    (r'\bkiske?\s+(sath|saath)\s+(soti|rahti|gayi|soi)\b', "Slut-Shaming & Harassment"),
    (r'\braat\s+ko\s+kiske?\b', "Slut-Shaming & Harassment"),
    (r'\broz\s+naye\b', "Slut-Shaming & Harassment"),

    # C. Unsolicited Sexual Objectification
    (r'\b(itne|kitne|bohot|bohot\s+hi)\s+bade\b', "Sexual Objectification"),
    (r'\b(size|figure|boob?s|chuchi|chuchiyan)\s+(kya|kitna|kitni|dikha)\b', "Sexual Objectification"),

    # D. Nudity, Leaks & Unsolicited Content Requests
    (r'\b(nude|nudes|nangi|nanga|uncut|leak|mms)\s*(bhejo|de|do|link|photo|video)?\b', "Unsolicited Nudity & Leak Request"),

    # E. Severe Death Threats & Self-Harm Encouragement
    (r'\bkys\b', "Severe Threat / Self-Harm"),
    (r'\bkill\s+your\s*self\b', "Severe Threat / Self-Harm"),
    (r'\bgo\s+die\b', "Severe Threat / Self-Harm"),
    (r'\bmar\s*jaa?\b', "Severe Threat / Self-Harm"),
    (r'\bzeher\s+kha\b', "Severe Threat / Self-Harm"),
    (r'\bmar\s+dunga\b', "Severe Threat / Death Threat"),
    (r'\bmaar\s+dunga\b', "Severe Threat / Death Threat"),
    (r'\bmar\s+dungi\b', "Severe Threat / Death Threat"),
    (r'\bjaan\s+se\s+mar\b', "Severe Threat / Death Threat"),
    (r'\bjaan\s+se\s+maar\b', "Severe Threat / Death Threat"),
    (r'\bmaar\s+daal\b', "Severe Threat / Death Threat"),
    (r'\bacid\s+phek\b', "Severe Threat / Acid Attack"),
    (r'\bgoli\s+maar\b', "Severe Threat / Firearm Threat"),
    (r'\bchaku\s+maar\b', "Severe Threat / Weapon Threat"),
    (r'\btereko\s+dekh\b', "Intimidation & Stalking"),
    (r'\bdekh\s+lunga\b', "Intimidation & Stalking"),
    (r'\btera\s+address\b', "Doxxing & Stalking Threat"),
    (r'\bghar\s+aake\b', "Doxxing & Stalking Threat"),
    (r'\brape\s+(dunga|karunga|kardo)\b', "Severe Threat / Sexual Violence"),

    # Devanagari Hindi Violence
    (r'मार\s*दूंगा', "Severe Threat / Death Threat"),
    (r'जान\s*से\s*मार', "Severe Threat / Death Threat"),
    (r'गोली\s*मार', "Severe Threat / Firearm Threat"),
    (r'एसिड', "Severe Threat / Acid Attack"),
    (r'मर\s*जा', "Severe Threat / Self-Harm"),
    (r'घर\s*आके', "Doxxing & Stalking Threat")
]

COMPILED_PATTERNS = [(re.compile(p, re.IGNORECASE), cat) for p, cat in CREATOR_PROTECTION_PATTERNS]

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

def predict_comment(comment):
    res = predict_comment_detail(comment)
    return res["label"]

def predict_batch(comments):
    if not comments or not isinstance(comments, list):
        return []
    return [predict_comment_detail(c) for c in comments]