import re
import string

# Pre-compile regex patterns for maximum CPU throughput under load
URL_PATTERN = re.compile(r'http\S+|www\S+|https\S+')
HTML_PATTERN = re.compile(r'<.*?>')
SPACES_PATTERN = re.compile(r'\s+')
PUNCT_TABLE = str.maketrans('', '', string.punctuation)

def clean_text(text):
    """
    Cleans and preprocesses input comment text.
    Steps:
    1. Lowercasing
    2. Remove URLs
    3. Remove HTML tags
    4. Remove punctuation
    5. Remove extra whitespace
    """
    if not isinstance(text, str):
        return ""

    text = text.lower()
    text = URL_PATTERN.sub('', text)
    text = HTML_PATTERN.sub('', text)
    text = text.translate(PUNCT_TABLE)
    text = SPACES_PATTERN.sub(' ', text).strip()
    return text

def clean_batch(texts):
    """
    Cleans a list of text comments efficiently.
    """
    return [clean_text(t) for t in texts]