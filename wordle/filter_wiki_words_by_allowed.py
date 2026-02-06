import argparse
import csv
import os

# Minimum frequency to keep per language.
# Set per-language thresholds explicitly to make tuning easy.
MIN_FREQUENCY_BY_LANG = {
    "ar": 5,
    "bg": 50,
    "cs": 50,
    "da": 50,
    "de": 50,
    "el": 5,
    "en": 50,
    "es": 50,
    "et": 50,
    "fi": 50,
    "fr": 50,
    "ga": 50,
    "hr": 50,
    "hu": 50,
    "it": 50,
    "lt": 50,
    "lv": 50,
    "mt": 50,
    "nl": 50,
    "pl": 50,
    "pt": 50,
    "ro": 50,
    "ru": 50,
    "sk": 50,
    "sl": 50,
    "sv": 50,
    "tr": 50,
    "ur": 10,
}

DEFAULT_MIN_FREQUENCY = 50

WIKI_CSV_DIR = "wiki_5_letter_words"
RESOURCES_DIR = "resources"


def load_allowed_words(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def iter_wiki_words(csv_path):
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            word = row.get("word")
            count = row.get("count")
            if not word or count is None:
                continue
            try:
                yield word, int(count)
            except ValueError:
                continue


def filter_language(lang_code, min_frequency, dry_run=False):
    csv_path = os.path.join(WIKI_CSV_DIR, f"{lang_code}_5_letter_words.csv")
    allowed_path = os.path.join(RESOURCES_DIR, lang_code, "allowed_words.txt")

    if not os.path.exists(csv_path):
        print(f"[{lang_code}] Missing CSV: {csv_path}")
        return

    allowed_words = load_allowed_words(allowed_path)
    if allowed_words is None:
        print(f"[{lang_code}] Missing allowed list: {allowed_path}")
        return

    filtered = [
        word
        for word, count in iter_wiki_words(csv_path)
        if count >= min_frequency and word in allowed_words
    ]

    if dry_run:
        print(f"[{lang_code}] {len(filtered)} words would be saved (min freq {min_frequency})")
        return

    os.makedirs(os.path.dirname(allowed_path), exist_ok=True)
    with open(allowed_path, "w", encoding="utf-8") as f:
        for word in filtered:
            f.write(f"{word}\n")

    print(f"[{lang_code}] Saved {len(filtered)} words to {allowed_path} (min freq {min_frequency})")


def main():
    parser = argparse.ArgumentParser(
        description="Filter wiki 5-letter CSVs by frequency and allowed_words.txt."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print counts without writing files.",
    )
    parser.add_argument(
        "--lang",
        action="append",
        help="Process only specific language codes (repeatable).",
    )
    args = parser.parse_args()

    target_langs = args.lang or sorted(MIN_FREQUENCY_BY_LANG.keys())
    for lang_code in target_langs:
        min_freq = MIN_FREQUENCY_BY_LANG.get(lang_code, DEFAULT_MIN_FREQUENCY)
        filter_language(lang_code, min_freq, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
