import gzip
import csv
import json
import sys
import os
from typing import Dict, List, Set

# -------------------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------------------
# Path to the ConceptNet 5.7 assertions file
CONCEPTNET_FILE = 'conceptnet-assertions-5.7.0.csv.gz'

# Source language for the word list
SOURCE_LANG = 'en'

# Target languages to extract translations for
TARGET_LANGS = ['fr', 'es', 'de', 'it', 'ja', 'zh', 'ru', 'ar']

# Word list to translate (example: common objects and concepts)
WORD_LIST = [
    'cat', 'dog', 'house', 'car', 'tree', 'water', 'food', 'book',
    'computer', 'phone', 'table', 'chair', 'door', 'window', 'sun',
    'moon', 'star', 'flower', 'bird', 'fish', 'mountain', 'river',
    'city', 'country', 'friend', 'family', 'love', 'time', 'money',
    'work', 'school', 'student', 'teacher', 'doctor', 'hospital',
    'restaurant', 'airport', 'train', 'bus', 'bicycle', 'street',
    'music', 'movie', 'game', 'sport', 'ball', 'team', 'player',
    'color', 'red', 'blue', 'green', 'yellow', 'black', 'white'
]

# Relations to consider for translation
# /r/Synonym - words with similar meanings across languages
# /r/TranslationOf - direct translations
TRANSLATION_RELATIONS = {'/r/Synonym', '/r/TranslationOf'}

# Minimum weight to consider an assertion valid
MIN_WEIGHT = 1.0

# Output file name
OUTPUT_FILE = 'word_translations.json'

# -------------------------------------------------------------------
# SYSTEM SETUP
# -------------------------------------------------------------------
# Increase CSV field size limit to handle large metadata blobs
try:
    csv.field_size_limit(sys.maxsize)
except OverflowError:
    csv.field_size_limit(2147483647)


class WordListTranslator:
    """
    Extracts translations for a specific word list from ConceptNet.
    """

    def __init__(self, filepath: str, word_list: List[str]):
        self.filepath = filepath
        self.word_list = set(word_list)  # Convert to set for O(1) lookup
        self.relations = TRANSLATION_RELATIONS

    def parse_uri(self, uri: str) -> dict:
        """
        Parses a ConceptNet URI into components.
        Format: /c/{lang}/{text}/{pos}/{sense}...
        """
        if not uri.startswith('/c/'):
            return None

        parts = uri.split('/')
        if len(parts) < 4:
            return None

        data = {
            'lang': parts[2],
            'text': parts[3].replace('_', ' '),
            'pos': parts[4] if len(parts) > 4 else None,
            'sense': '/'.join(parts[5:]) if len(parts) > 5 else None
        }

        return data

    def normalize_text(self, text: str) -> str:
        """
        Normalizes text for comparison (lowercase, remove underscores).
        """
        return text.lower().replace('_', ' ').strip()

    def extract(self) -> dict:
        """
        Extracts translations for words in the word list.
        Returns: { "word": { "lang": ["translation1", "translation2", ...] } }
        """
        results = {word: {} for word in self.word_list}
        target_lang_set = set(TARGET_LANGS)
        
        # Normalize word list for comparison
        normalized_words = {self.normalize_text(word): word for word in self.word_list}

        print(f"Reading {self.filepath}...")
        print(f"Looking for translations of {len(self.word_list)} words...")
        print(f"Target languages: {', '.join(TARGET_LANGS)}")

        if not os.path.exists(self.filepath):
            print(f"Error: File {self.filepath} not found.")
            return {}

        line_count = 0
        matches_found = 0

        try:
            with gzip.open(self.filepath, 'rt', encoding='utf-8', errors='replace') as f:
                reader = csv.reader(f, delimiter='\t', quoting=csv.QUOTE_NONE)

                for row in reader:
                    line_count += 1
                    if line_count % 1_000_000 == 0:
                        print(f"Processed {line_count:,} assertions, found {matches_found} translations...", end='\r')

                    # Standard ConceptNet row has 5 columns
                    if len(row) < 5:
                        continue

                    uri, relation, start_node, end_node, json_metadata = row

                    # 1. Filter by relation
                    if relation not in self.relations:
                        continue

                    # 2. Parse URIs
                    start = self.parse_uri(start_node)
                    end = self.parse_uri(end_node)

                    if not start or not end:
                        continue

                    # 3. Check if one side is SOURCE language and other is TARGET language
                    is_forward = (start['lang'] == SOURCE_LANG and end['lang'] in target_lang_set)
                    is_reverse = (end['lang'] == SOURCE_LANG and start['lang'] in target_lang_set)

                    if not (is_forward or is_reverse):
                        continue

                    # 4. Identify source and target concepts
                    source_concept = start if is_forward else end
                    target_concept = end if is_forward else start

                    # 5. Check if the source word is in our word list
                    normalized_source = self.normalize_text(source_concept['text'])
                    if normalized_source not in normalized_words:
                        continue

                    # 6. Check metadata weight
                    try:
                        meta = json.loads(json_metadata)
                        if meta.get('weight', 0) < MIN_WEIGHT:
                            continue
                    except json.JSONDecodeError:
                        continue

                    # 7. Store the translation
                    original_word = normalized_words[normalized_source]
                    target_text = target_concept['text']
                    target_lang = target_concept['lang']

                    if target_lang not in results[original_word]:
                        results[original_word][target_lang] = set()

                    results[original_word][target_lang].add(target_text)
                    matches_found += 1

        except KeyboardInterrupt:
            print("\nProcessing interrupted by user.")
        except Exception as e:
            print(f"\nCritical Error: {e}")
            import traceback
            traceback.print_exc()

        print(f"\nComplete. Processed {line_count:,} assertions.")
        print(f"Found translations for {sum(1 for word, langs in results.items() if langs)} words.")

        # Convert sets to sorted lists for JSON output
        output = {
            word: {lang: sorted(list(translations)) for lang, translations in langs.items()}
            for word, langs in results.items()
        }

        return output


def print_summary(data: dict):
    """
    Prints a summary of the extracted translations.
    """
    print("\n" + "="*60)
    print("TRANSLATION SUMMARY")
    print("="*60)
    
    words_with_translations = [word for word, langs in data.items() if langs]
    words_without_translations = [word for word, langs in data.items() if not langs]
    
    print(f"\nWords with translations: {len(words_with_translations)}")
    print(f"Words without translations: {len(words_without_translations)}")
    
    if words_without_translations:
        print(f"\nWords not found: {', '.join(sorted(words_without_translations)[:10])}")
        if len(words_without_translations) > 10:
            print(f"... and {len(words_without_translations) - 10} more")
    
    # Show some examples
    print("\nExample translations:")
    for word in sorted(words_with_translations)[:5]:
        print(f"\n  {word}:")
        for lang, translations in sorted(data[word].items()):
            print(f"    {lang}: {', '.join(translations[:3])}")
            if len(translations) > 3:
                print(f"         ... and {len(translations) - 3} more")


if __name__ == "__main__":
    translator = WordListTranslator(CONCEPTNET_FILE, WORD_LIST)
    data = translator.extract()

    print(f"\nSaving to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print_summary(data)
    print(f"\nDone! Output saved to {OUTPUT_FILE}")
