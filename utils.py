import re
import pandas as pd
import unicodedata
from deep_translator import GoogleTranslator
from langdetect import detect_langs
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from sklearn.metrics.pairwise import cosine_distances
from nltk.corpus import words as nltk_words
"""import pycountry"""

# Initialize English words set (lazy load)
_english_words_set = None

def get_english_words():
    global _english_words_set
    if _english_words_set is None:
        try:
            _english_words_set = set(nltk_words.words())
        except LookupError:
            import nltk
            nltk.download('words', quiet=True)
            _english_words_set = set(nltk_words.words())
    return _english_words_set


def normalize_name(name: str):
    """Normalize names by converting unicode to ASCII and removing non-letter characters"""
    if pd.isna(name) or str(name).strip() == "":
        return ""
    
    name_str = str(name).strip()
    
    # Normalize unicode → ASCII
    nfkd = unicodedata.normalize("NFKD", name_str)
    only_ascii = nfkd.encode("ASCII", "ignore").decode("ASCII")
    
    # Lowercase + remove non-letters
    only_ascii = re.sub(r"[^a-zA-Z]", "", only_ascii).lower()
    
    return only_ascii


def extract_last_name_for_email(last_name):
    """Extract last name for email: remove punctuation, if 2+ words take last word"""
    if pd.isna(last_name) or str(last_name).strip() == "":
        return ""
    
    name_str = str(last_name).strip()
    
    # Remove punctuation
    name_str = re.sub(r'[^\w\s]', '', name_str)
    
    # Split on whitespace and get words
    words = name_str.split()
    
    if not words:
        return ""
    
    # If 2+ words, take the last one; otherwise take the whole thing
    if len(words) >= 2:
        return words[-1].lower()
    else:
        return words[0].lower()


def generate_email(first_name, last_name, email_format):
    """Generate email using the provided format and name components
    
    Args:
        first_name: First name (e.g., "John")
        last_name: Last name (e.g., "Doe")
        email_format: Email format string (e.g., "firstname.lastname@company.com")
    
    Returns:
        Generated email or empty string if names are missing
    """
    if pd.isna(first_name) or str(first_name).strip() == "":
        return ""
    if pd.isna(last_name) or str(last_name).strip() == "":
        return ""
    if pd.isna(email_format) or str(email_format).strip() == "":
        return ""
    first = str(first_name).strip().lower()
    last = extract_last_name_for_email(last_name)
    
    if not first or not last:
        return ""
    
    # Replace placeholders in format
    # Format typically looks like: firstname.lastname@company.com
    email = email_format.replace("firstname", first).replace("lastname", last)
    return email

# Initialize free Google Translate client
translator = GoogleTranslator(source='auto', target='en')

geolocator = Nominatim(user_agent="preprocess")

_translation_cache = {}
_lang_cache = {}

def normalize_text(x):
    if pd.isna(x):
        return ""
    return re.sub(r"[^\w\s]", "", str(x)).lower().strip()


def detect_lang(text):
    """Detect language and cache results"""
    if not text or str(text).strip() == "":
        return "en"
    
    text_str = str(text).strip()
    
    if text_str in _lang_cache:
        return _lang_cache[text_str]
    
    try:
        detected = detect_langs(text_str)
        lang = detected[0].lang if detected else "en"
    except:
        lang = "en"
    
    _lang_cache[text_str] = lang
    return lang


def translate_text(text, skip_lang_filter=False):
    """Translate text to English.
    
    Args:
        text: Text to translate
        skip_lang_filter: If True, translate any non-English text. 
                         If False (default), only translate specific languages in TRANSLATE_LANGS
    """
    if pd.isna(text) or str(text).strip() == "":
        return "", False
    
    text_str = str(text).strip()
    
    if text_str in _translation_cache:
        return _translation_cache[text_str]
    
    # Detect language
    lang = detect_lang(text_str)
    
    # Skip translation if already English
    if lang == "en":
        _translation_cache[text_str] = (text_str, False)
        return text_str, False
    
    # If skip_lang_filter is False, only translate specific languages
    if not skip_lang_filter:
        TRANSLATE_LANGS = {'zh-cn', 'zh-tw', 'ja', 'ko', 'ru', 'uk', 'fa', 'ar', 'zh'}
        # 'pt', 'es', 'fr', 'it', 'de', 'id', 'zh'
        if lang not in TRANSLATE_LANGS:
            _translation_cache[text_str] = (text_str, False)
            return text_str, False
    
    # Translate any non-English text
    try:
        translated = translator.translate(text_str)
        _translation_cache[text_str] = (translated, False)
        return translated, False
    except Exception as e:
        _translation_cache[text_str] = (text_str, True)
        return text_str, True


def split_location(loc):
    parts = [p.strip() for p in loc.split(",")]
    if len(parts) > 3:
        return parts[-3:]
    if len(parts) == 3:
        return parts
    if len(parts) == 2:
        return ["", parts[0], parts[1]]
    if len(parts) == 1:
        try:
            country = pycountry.countries.lookup(parts[0])
            return ["", "", country.name]
        except:
            pass
        # try:
        #     geo = geolocator.geocode(parts[0], language="en")
        #     if geo:
        #         addr = geo.raw.get("display_name", "")
        #         seg = addr.split(",")
        #         return ["", "", seg[-1].strip()]
        # except:
        #     pass
    return ["", "", ""]

# def cluster_job_titles(titles, distance_threshold=0.25):
#     clean = titles.fillna("").str.lower().str.replace(r"[^\w\s]", "", regex=True)
    
#     tfidf = TfidfVectorizer(stop_words="english", max_features=5000, min_df=2)
#     X = tfidf.fit_transform(clean)
    
#     # Reduce dimensions
#     svd = TruncatedSVD(n_components=min(100, X.shape[1]), random_state=42)
#     X_reduced = svd.fit_transform(X)
    
#     clustering = AgglomerativeClustering(
#         n_clusters=None,
#         distance_threshold=distance_threshold,
#         metric="euclidean",
#         linkage="ward"
#     )
    
#     labels = clustering.fit_predict(X_reduced)
    
#     # Select most representative title per cluster (closest to centroid)
#     cluster_names = {}
#     for label in np.unique(labels):
#         cluster_mask = labels == label
#         cluster_vectors = X_reduced[cluster_mask]
#         cluster_titles = titles[cluster_mask]
        
#         # Find title closest to cluster centroid
#         centroid = cluster_vectors.mean(axis=0)
#         distances = np.linalg.norm(cluster_vectors - centroid, axis=1)
#         representative_idx = distances.argmin()
        
#         # Use the original (cleaned) representative title
#         representative = cluster_titles.iloc[representative_idx]
#         cluster_names[label] = representative
    
#     groups = [cluster_names[l] for l in labels]
    
#     return groups


def punctuation_only(x):
    return bool(re.fullmatch(r"\W+", str(x))) if pd.notna(x) else False

def is_valid_job_title(title):
    """Check if a job title is valid (not jibberish, numbers, etc.)
    
    Also checks if at least 50% of words in the title are valid English words.
    """
    if pd.isna(title) or str(title).strip() == "":
        return False
    
    title_str = str(title).strip()
    
    # Basic length checks
    if len(title_str) < 3:
        return False
    if re.match(r'^[\d\W]+$', title_str):  # Only numbers/punctuation
        return False
    if len(title_str) > 150:  # Abnormally long
        return False
    
    # Extract and validate words
    # Remove punctuation and numbers, keep only letters and spaces
    cleaned = re.sub(r'[^\w\s]', '', title_str)
    words_list = [w for w in cleaned.lower().split() if len(w) > 1]
    
    if not words_list or len(words_list) == 0:
        return False
    
    # Check if at least 50% of words are valid English words
    english_words = get_english_words()
    valid_word_count = sum(1 for word in words_list if word in english_words)
    valid_percentage = valid_word_count / len(words_list)
    
    if valid_percentage < 0.5:
        return False
    
    # Must have at least 3 letters total
    if len(re.findall(r'[a-zA-Z]', title_str)) < 3:
        return False
    
    return True

def clean_job_titles(titles):
    """Return empty string for invalid job titles, keep valid ones"""
    return titles.apply(lambda x: x if is_valid_job_title(x) else "")

import re
import pandas as pd
from rapidfuzz import process, fuzz

def cluster_job_titles(titles, fuzzy_threshold=70):
    """
    Three-stage clustering:
    1. Filter junk entries
    2. Normalize case and punctuation
    3. Fuzzy match remaining variants
    """
    
    # Stage 1: Filter junk entries (use the main validation function)
    def is_valid_title(title):
        return is_valid_job_title(title)
    
    # Stage 2: Normalize case and punctuation
    def normalize_title(title):
        """Normalize while preserving seniority and specialization"""
        if not is_valid_title(title):
            return "Invalid Title"
        
        title_str = str(title).strip()
        
        # Normalize common patterns
        normalized = title_str
        
        # Fix common case issues for specific terms
        normalized = re.sub(r'\.net\b', '.NET', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'\bc#\b', 'C#', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'\bux\b', 'UX', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'\bui\b', 'UI', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'\bqa\b', 'QA', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'\bit\b', 'IT', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'\bai\b', 'AI', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'\bbi\b', 'BI', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'\bcrm\b', 'CRM', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'\berp\b', 'ERP', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'\bceo\b', 'CEO', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'\bcto\b', 'CTO', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'\bcfo\b', 'CFO', normalized, flags=re.IGNORECASE)
        
        # Title case for most words, but preserve acronyms
        words = normalized.split()
        result = []
        for word in words:
            if word.isupper() and len(word) <= 4:  # Keep acronyms
                result.append(word)
            elif word in ['&', 'and', 'of', 'in', 'for', 'at', 'to']:
                result.append(word.lower())
            else:
                result.append(word.capitalize())
        
        return ' '.join(result)
    
    # Apply normalization
    normalized_titles = titles.apply(normalize_title)
    
    # Stage 3: Fuzzy match for remaining variants
    unique_normalized = normalized_titles.value_counts()
    valid_titles = [t for t in unique_normalized.index if t != "Invalid Title"]
    
    if len(valid_titles) == 0:
        return normalized_titles.tolist()
    
    # Fuzzy matching with high threshold to preserve distinctions
    mapping = {}
    remaining = set(valid_titles)
    
    while remaining:
        # Pick most frequent as representative
        representative = unique_normalized[unique_normalized.index.isin(remaining)].index[0]
        mapping[representative] = representative
        remaining.remove(representative)
        
        # Find very similar titles only
        matches = process.extract(
            representative,
            list(remaining),
            scorer=fuzz.ratio,  # Use simple ratio for exact matching
            score_cutoff=fuzzy_threshold,
            limit=None
        )
        
        for match_title, score, _ in matches:
            mapping[match_title] = representative
            remaining.discard(match_title)
    
    # Apply final mapping
    result = []
    for title in normalized_titles:
        if title == "Invalid Title":
            result.append("")
        else:
            result.append(mapping.get(title, title))
    
    return result
