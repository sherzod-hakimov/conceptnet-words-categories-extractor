import os
import requests
import bz2
import xml.sax
import regex as re
import unicodedata
import csv
from collections import Counter
from tqdm import tqdm

# --- CONFIGURATION ---

# Length of words to extract.
# Set to None or 0 to extract ALL words (Warning: Requires lots of RAM for large languages like English)
# Set to 5 to extract only 5-letter words.
TARGET_LENGTH = 5

# Minimum frequency to save (helps remove typos/garbage)
MIN_FREQUENCY = 10

# Output directory
OUTPUT_DIR = "wiki_5_letter_words"

# Language codes (Wikipedia prefixes usually match ISO codes)
# Each entry provides a human name and a strict alphabet (lowercase).
# If alphabet is None, fall back to \p{L}+ matching.
TARGET_LANGS = {
    'bg': {'name': 'Bulgarian', 'alphabet': "абвгдежзийклмнопрстуфхцчшщъьюя", 'vowels': "аеёиоуъюя"},
    'hr': {'name': 'Croatian', 'alphabet': "abcčćdđefghijklmnoprstuvzž", 'vowels': "aeiou"},
    'cs': {'name': 'Czech', 'alphabet': "aábcčdďeéěfghchiíjklmnňoópqrřsštťuúůvwxyýzž", 'vowels': "aeiouyáéěíóúůý"},
    'da': {'name': 'Danish', 'alphabet': "abcdefghijklmnopqrstuvwxyzæøå", 'vowels': "aeiouyæøå"},
    'nl': {'name': 'Dutch', 'alphabet': "abcdefghijklmnopqrstuvwxyz", 'vowels': "aeiouy"},
    'en': {'name': 'English', 'alphabet': "abcdefghijklmnopqrstuvwxyz", 'vowels': "aeiouy"},
    'et': {'name': 'Estonian', 'alphabet': "abcdefghijklmnopqrsšzžtuvwõäöüxy", 'vowels': "aeiouõäöü"},
    'fi': {'name': 'Finnish', 'alphabet': "abcdefghijklmnopqrstuvwxyzåäö", 'vowels': "aeiouyäöå"},
    'fr': {'name': 'French', 'alphabet': "abcdefghijklmnopqrstuvwxyzàâæçéèêëîïôœùûüÿ", 'vowels': "aeiouyàâæéèêëîïôœùûüÿ"},
    'de': {'name': 'German', 'alphabet': "abcdefghijklmnopqrstuvwxyzäöüß", 'vowels': "aeiouäöü"},
    'el': {'name': 'Greek', 'alphabet': "αβγδεζηθικλμνξοπρστυφχψω", 'vowels': "αεηιουω"},
    'hu': {'name': 'Hungarian', 'alphabet': "aábcdeéfghiíjklmnoóöőpqrstuúüűvwxyz", 'vowels': "aeiouáéíóöőúüű"},
    'ga': {'name': 'Irish', 'alphabet': "abcdefghijklmnopqrstuvwxyzáéíóú", 'vowels': "aeiouáéíóú"},
    'it': {'name': 'Italian', 'alphabet': "abcdefghijklmnopqrstuvwxyzàèéìíîòóùú", 'vowels': "aeiouàèéìíîòóùú"},
    'lv': {'name': 'Latvian', 'alphabet': "aābcčdeēfgģhiījkķlļmnņoprsštuūvzž", 'vowels': "aeiouāēīū"},
    'lt': {'name': 'Lithuanian', 'alphabet': "aąbcčdeęėfghiįyjklmnoprsštuųūvzž", 'vowels': "aeiouąęėįųū"},
    'mt': {'name': 'Maltese', 'alphabet': "abċdefġgħhijklmnopqrstuuvwxżz", 'vowels': "aeiou"},
    'pl': {'name': 'Polish', 'alphabet': "aąbcćdeęfghijklłmnńoópqrsśtuvwxyzźż", 'vowels': "aeiouyąęó"},
    'pt': {'name': 'Portuguese', 'alphabet': "abcdefghijklmnopqrstuvwxyzáâãàçéêíóôõúü", 'vowels': "aeiouáâãàéêíóôõúü"},
    'ro': {'name': 'Romanian', 'alphabet': "abcdefghijklmnopqrstuvwxyzăâîșşțţ", 'vowels': "aeiouăâî"},
    'sk': {'name': 'Slovak', 'alphabet': "aáäbcčdďeéfghchiíjklľĺmnňoóôpqrŕsštťuúůvwxyýzž", 'vowels': "aeiouyáéíóôúýä"},
    'sl': {'name': 'Slovenian', 'alphabet': "abcčdefghijklmnoprsštuvzž", 'vowels': "aeiou"},
    'es': {'name': 'Spanish', 'alphabet': "abcdefghijklmnopqrstuvwxyzáéíñóúü", 'vowels': "aeiouáéíóúü"},
    'sv': {'name': 'Swedish', 'alphabet': "abcdefghijklmnopqrstuvwxyzåäö", 'vowels': "aeiouyåäö"},
    'ar': {'name': 'Arabic', 'alphabet': "ابتثجحخدذرزسشصضطظعغفقكلمنهوي"},
    'ru': {'name': 'Russian', 'alphabet': "абвгдеёжзийклмнопрстуфхцчшщъыьэюя", 'vowels': "аеёиоуыэюя"},
    'tr': {'name': 'Turkish', 'alphabet': "abcçdefgğhıijklmnoöprsştuüvyz", 'vowels': "aeıioöuü"},
    'ur': {'name': 'Urdu', 'alphabet': "ابتثجچحخدذرڑزژسشصضطظعغفقکگلمنوهیءے"}
}


# --- SAX CONTENT HANDLER ---



def _normalize_text(text, lang_code):
    text = unicodedata.normalize("NFC", text)
    text = text.lower()
    if lang_code == "tr":
        # Lowercasing Turkish dotted İ yields "i" + combining dot.
        # Remove the combining dot so length checks stay correct.
        text = text.replace("\u0307", "")
    return text


class WikiContentHandler(xml.sax.ContentHandler):
    """
    Stream-parses the XML dump.
    It looks for <text> tags, extracts content, and updates the word counter.
    """

    def __init__(self, target_length=None, lang_code=None, alphabet=None):
        self._current_tag = ""
        self._buffer = []
        self._word_counts = Counter()
        self.target_length = target_length
        self.lang_code = lang_code
        self.alphabet = alphabet

        if self.alphabet:
            letters_re = f"[{re.escape(self.alphabet)}]"
            if self.target_length:
                self._word_regex = re.compile(rf"{letters_re}{{{self.target_length}}}")
            else:
                self._word_regex = re.compile(rf"{letters_re}+")
        else:
            # Regex for valid words:
            # \p{L} matches any unicode letter (covers Arabic, Cyrillic, Latin accents).
            self._word_regex = re.compile(r'\p{L}+')

    def startElement(self, name, attrs):
        self._current_tag = name
        if name == "text":
            self._buffer = []

    def characters(self, content):
        if self._current_tag == "text":
            self._buffer.append(content)

    def endElement(self, name):
        if name == "text":
            text_content = "".join(self._buffer)
            self._process_text(text_content)
            self._buffer = []
        self._current_tag = ""

    def _process_text(self, text):
        text = _normalize_text(text, self.lang_code)

        # 1. Find all words
        words = self._word_regex.findall(text)

        # 2. Filter by length (if specific length requested)
        if self.target_length and self.alphabet is None:
            words = [w for w in words if len(w) == self.target_length]

        # 2b. Turkish-specific cleanup: require at least one vowel
        vowels = TARGET_LANGS.get(self.lang_code, {}).get('vowels')
        if vowels:
            words = [w for w in words if any(v in w for v in vowels)]

        # 3. Update counts
        self._word_counts.update(words)

    def get_counts(self):
        return self._word_counts


# --- DOWNLOAD & PROCESS FUNCTIONS ---

def get_dump_url(lang_code):
    # Standard URL for the latest articles dump
    return f"https://dumps.wikimedia.org/{lang_code}wiki/latest/{lang_code}wiki-latest-pages-articles.xml.bz2"


def download_file(url, filename):
    """Downloads a file with a progress bar."""
    if os.path.exists(filename):
        print(f"   file {filename} already exists. Skipping download.")
        return

    print(f"   Downloading {url}...")
    try:
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))

            with open(filename, 'wb') as f, tqdm(
                    desc=filename,
                    total=total_size,
                    unit='iB',
                    unit_scale=True,
                    unit_divisor=1024,
            ) as bar:
                for chunk in r.iter_content(chunk_size=1024 * 1024):  # 1MB chunks
                    size = f.write(chunk)
                    bar.update(size)
    except Exception as e:
        print(f"   ❌ Download failed: {e}")
        if os.path.exists(filename):
            os.remove(filename)  # Clean up partial file


def process_dump(lang_code, lang_name, alphabet):
    filename = f"{lang_code}wiki-latest-pages-articles.xml.bz2"
    url = get_dump_url(lang_code)

    # 1. Download
    download_file(url, filename)

    if not os.path.exists(filename):
        return

    print(f"   Processing XML content for {lang_name}...")

    # 2. Parse XML stream (BZ2 decompressed on the fly)
    handler = WikiContentHandler(
        target_length=TARGET_LENGTH,
        lang_code=lang_code,
        alphabet=alphabet,
    )
    parser = xml.sax.make_parser()
    parser.setContentHandler(handler)
    # Disable security features we don't need for speed
    parser.setFeature(xml.sax.handler.feature_namespaces, 0)

    try:
        with bz2.open(filename, 'rt', encoding='utf-8', errors='ignore') as f:
            # We wrap 'f' to not crash on malformed chunks, though XML parser usually handles it.
            parser.parse(f)

    except Exception as e:
        print(f"   ⚠️ Parsing interrupted (might be partial data): {e}")

    # 3. Save Results
    counts = handler.get_counts()

    if not counts:
        print(f"   No words found.")
        return

    # Filter out rare words
    filtered_counts = {k: v for k, v in counts.items() if v >= MIN_FREQUENCY}

    # sort words alphabetically, ascending order
    sorted_words = sorted(filtered_counts.items(), key=lambda item: item[0], reverse=False)

    output_file = os.path.join(OUTPUT_DIR, f"{lang_code}_{TARGET_LENGTH if TARGET_LENGTH else 'all'}_letter_words.csv")

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['word', 'count'])
        writer.writerows(sorted_words)

    print(f"   ✅ Saved {len(sorted_words)} words to {output_file}")

    # Optional: Delete dump to save disk space?
    os.remove(filename)


# --- MAIN ---

if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Starting Wikipedia extraction for {len(TARGET_LANGS)} languages.")
    print(f"Target Length: {TARGET_LENGTH if TARGET_LENGTH else 'ALL'}")

    for code, meta in TARGET_LANGS.items():
        name = meta['name']
        alphabet = meta['alphabet']
        print(f"\n--- [{code.upper()}] {name} ---")
        process_dump(code, name, alphabet)

    print("\nBatch Complete.")
