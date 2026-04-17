import re
import string

def clean_text(text):
    """
    Cleans and preprocesses input comment text.
    Steps:
    1. Lowercasing
    2. Remove URLs
    3. Remove HTML tags
    4. Remove special characters & punctuation
    5. Remove extra spaces
    """

    # 1. Lowercase
    text = text.lower()

    # 2. Remove URLs
    text = re.sub(r'http\S+|www\S+|https\S+', '', text)

    # 3. Remove HTML tags
    text = re.sub(r'<.*?>', '', text)

    # 4. Remove punctuation
    text = text.translate(str.maketrans('', '', string.punctuation))

    # . Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    return text