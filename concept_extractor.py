import gzip
import csv
import json
import sys
import os
from typing import Dict, List, Set, Optional

# -------------------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------------------
# Path to the ConceptNet 5.7 assertions file
CONCEPTNET_FILE = '/Users/sherzodhakimov/Downloads/conceptnet-assertions-5.7.0.csv.gz'

# The source language for the concepts (e.g., 'en' for English)
SOURCE_LANG = 'en'

# The target languages to extract translations for (e.g., ['fr', 'es', 'ja'])
TARGET_LANGS = ['fr', 'es', 'de', 'ja', 'zh']

# Filter for Part of Speech? 'n' = Noun, 'v' = Verb, etc.
# Set to None to disable filtering.
POS_FILTER = 'n'

# Minimum weight to consider an assertion valid.
# 1.0 is the default confidence. Higher is better.
MIN_WEIGHT = 1.0

# Output file name
OUTPUT_FILE = 'conceptnet_nouns_extracted.json'

# -------------------------------------------------------------------
# SYSTEM SETUP
# -------------------------------------------------------------------
# Increase CSV field size limit to handle large metadata blobs in column 4
try:
    csv.field_size_limit(sys.maxsize)
except OverflowError:
    # Handle systems where sys.maxsize is too large for C long
    csv.field_size_limit(2147483647)


class ConceptNetExtractor:
    """
    Parses ConceptNet 5.7 assertions to extract translations for specific POS.
    """

    def __init__(self, filepath):
        self.filepath = filepath
        self.relations = {'/r/Synonym'}  # The relation used for translation

    def parse_uri(self, uri: str):
        """
        Deconstructs a ConceptNet URI into components.
        Format: /c/{lang}/{text}/{pos}/{sense}...
        """
        if not uri.startswith('/c/'):
            return None

        parts = uri.split('/')
        # parts = '' (empty string before first slash)
        # parts = 'c'
        # parts = language code
        # parts = concept text

        if len(parts) < 4:
            return None

        data = {
            'lang': parts[2],
            'text': parts[3],
            'pos': None,
            'sense': None
        }

        # Check for POS
        if len(parts) > 4:
            data['pos'] = parts[4]

        # Check for sense/disambiguation (e.g., /wn/animal)
        if len(parts) > 5:
            data['sense'] = '/'.join(parts[5:])

        return data

    def extract(self) -> dict:
        """
        Performs the streaming extraction.
        Returns a dictionary: { "concept": { "lang": ["translation",...] } }
        """
        results = dict()
        target_lang_set = set(TARGET_LANGS)

        print(f"Reading {self.filepath}...")
        print(f"Extracting {POS_FILTER if POS_FILTER else 'all'} concepts from '{SOURCE_LANG}'...")

        if not os.path.exists(self.filepath):
            print(f"Error: File {self.filepath} not found.")
            return {}

        line_count = 0

        try:
            with gzip.open(self.filepath, 'rt', encoding='utf-8', errors='replace') as f:
                reader = csv.reader(f, delimiter='\t', quoting=csv.QUOTE_NONE)

                for row in reader:
                    line_count += 1
                    if line_count % 1_000_000 == 0:
                        print(f"Processed {line_count:,} assertions...", end='\r')

                    # Standard ConceptNet row has 5 columns
                    if len(row) < 5:
                        continue

                    uri, relation, start_node, end_node, json_metadata = row

                    # 1. Filter by Relation (Cheapest check)
                    if relation not in self.relations:
                        continue

                    # 2. Parse URIs
                    start = self.parse_uri(start_node)
                    end = self.parse_uri(end_node)

                    if not start or not end:
                        continue

                    # 3. Bidirectional Logic
                    # We look for a match where one side is SOURCE and other is TARGET

                    # Case A: Start -> End (e.g., English -> French)
                    is_forward = (start['lang'] == SOURCE_LANG and end['lang'] in target_lang_set)

                    # Case B: End -> Start (e.g., French -> English)
                    # Because /r/Synonym is symmetric, this is also a valid translation
                    is_reverse = (end['lang'] == SOURCE_LANG and start['lang'] in target_lang_set)

                    if not (is_forward or is_reverse):
                        continue

                    # 4. Filter by POS (Part of Speech)
                    # We only care if the SOURCE term matches the requested POS.
                    # In Case A, Start is source. In Case B, End is source.
                    source_concept_data = start if is_forward else end
                    target_concept_data = end if is_forward else start

                    if POS_FILTER:
                        # If the concept has a POS tag, it MUST match.
                        # If it has NO tag, we might skip it or include it.
                        # Here, we strictly require the tag if present.
                        if source_concept_data['pos'] and source_concept_data['pos'] != POS_FILTER:
                            continue

                        # If the user strictly needs nouns, we should probably skip untagged ones
                        # unless we are sure. For this script, we require the match if the tag exists.
                        # (Adjust logic here if you want to be more permissive)
                        if source_concept_data['pos'] is None:
                            # Strict mode: skip if we can't verify it's a noun
                            continue

                            # 5. Check Metadata (Most expensive check, do last)
                    try:
                        meta = json.loads(json_metadata)
                        if meta.get('weight', 0) < MIN_WEIGHT:
                            continue
                    except json.JSONDecodeError:
                        continue

                    # 6. Store Result
                    source_text = source_concept_data['text'].replace('_', ' ')
                    target_text = target_concept_data['text'].replace('_', ' ')
                    t_lang = target_concept_data['lang']

                    if source_text not in results:
                        results[source_text] = {}
                    if t_lang not in results[source_text]:
                        results[source_text][t_lang] = set()

                    results[source_text][t_lang].add(target_text)

        except KeyboardInterrupt:
            print("\nProcessing interrupted by user.")
        except Exception as e:
            print(f"\nCritical Error: {e}")

        print(f"\nComplete. Found {len(results)} source concepts.")

        # formatting for JSON output (convert sets to lists)
        output = {
            k: {lang: list(v) for lang, v in val.items()}
            for k, val in results.items()
        }
        return output


if __name__ == "__main__":
    extractor = ConceptNetExtractor(CONCEPTNET_FILE)
    data = extractor.extract()

    print(f"Saving to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("Done.")
