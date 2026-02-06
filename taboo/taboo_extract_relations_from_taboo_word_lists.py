#!/usr/bin/env python3
"""
Extract ConceptNet relations for taboo target words per language.

Reads taboo word lists from:
  taboo/resources/<lang_id>/taboo_word_lists.json

Writes relations to:
  taboo/resources/<lang_id>/word_relations.json

Output keeps the same keys (e.g., high/medium/low) and stores, for each target word,
its related words with relation label and weight.
"""

import csv
import gzip
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

# -------------------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------------------
VALID_RELATIONS = [
    "/r/Synonym", "/r/RelatedTo", "/r/IsA", "/r/HasA", "/r/PartOf",
    "/r/UsedFor", "/r/CapableOf", "/r/Antonym", "/r/DerivedFrom",
    "/r/SimilarTo", "/r/MadeOf",
]

# Language-specific settings with single_word_check flag
LANGUAGES = {
    "ar": {"lowercase": True, "single_word_check": False},
    "bg": {"lowercase": True, "single_word_check": True},
    "cs": {"lowercase": True, "single_word_check": True},
    "da": {"lowercase": True, "single_word_check": True},
    "de": {"lowercase": False, "single_word_check": True},
    "el": {"lowercase": True, "single_word_check": True},
    "en": {"lowercase": True, "single_word_check": True},
    "es": {"lowercase": True, "single_word_check": True},
    "et": {"lowercase": True, "single_word_check": True},
    "fi": {"lowercase": True, "single_word_check": True},
    "fr": {"lowercase": True, "single_word_check": True},
    "ga": {"lowercase": True, "single_word_check": True},
    "hr": {"lowercase": True, "single_word_check": True},
    "hu": {"lowercase": True, "single_word_check": True},
    "it": {"lowercase": True, "single_word_check": True},
    "lt": {"lowercase": True, "single_word_check": True},
    "lv": {"lowercase": True, "single_word_check": True},
    "mt": {"lowercase": True, "single_word_check": True},
    "nl": {"lowercase": True, "single_word_check": True},
    "pl": {"lowercase": True, "single_word_check": True},
    "pt": {"lowercase": True, "single_word_check": True},
    "ro": {"lowercase": True, "single_word_check": True},
    "ru": {"lowercase": True, "single_word_check": True},
    "sk": {"lowercase": True, "single_word_check": True},
    "sl": {"lowercase": True, "single_word_check": True},
    "sv": {"lowercase": True, "single_word_check": True},
    "tr": {"lowercase": True, "single_word_check": True},
    "ur": {"lowercase": True, "single_word_check": False},
}


# -------------------------------------------------------------------
# HELPERS
# -------------------------------------------------------------------


def parse_uri(uri: str) -> dict:
    """Parse ConceptNet URI into components."""
    if not uri.startswith("/c/"):
        return None
    parts = uri.split("/")
    if len(parts) < 4:
        return None
    return {
        "lang": parts[2],
        "text": parts[3],
        "pos": parts[4] if len(parts) > 4 else None,
    }


def is_single_word(text: str) -> bool:
    return " " not in text.strip()


def normalize_relation(relation: str) -> str:
    name = relation.split("/")[-1]
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
    return s2.lower()


def normalize_word(word: str, lang_code: str) -> str:
    word = word.strip()
    if not word:
        return ""
    if LANGUAGES.get(lang_code, {}).get("lowercase", True):
        word = word.lower()
    return word


def get_match_keys(word: str, lang_code: str) -> List[str]:
    word = word.strip()
    if not word:
        return []
    if lang_code == "de":
        base = word.lower()
        cap = base[:1].upper() + base[1:] if base else base
        if cap != base:
            return [base, cap]
        return [base]
    return [normalize_word(word, lang_code)]


def get_word_entries(word_entries: Dict[str, List[dict]], lang_code: str, text: str) -> List[dict]:
    entries: List[dict] = []
    seen: set = set()
    for key in get_match_keys(text, lang_code):
        for entry in word_entries.get(key, []):
            entry_id = id(entry)
            if entry_id in seen:
                continue
            seen.add(entry_id)
            entries.append(entry)
    return entries


# -------------------------------------------------------------------
# IO
# -------------------------------------------------------------------


def load_taboo_word_lists(resources_dir: Path) -> Tuple[
    Dict[str, Dict[str, List[dict]]], Dict[str, Dict[str, List[dict]]]
]:
    """
    Load taboo word lists for each language and build structures for accumulation.

    Returns:
      lang_to_categories: {lang: {category: [entry, ...]}}
      lang_to_word_entries: {lang: {word: [entry, ...]}}
    """
    lang_to_categories: Dict[str, Dict[str, List[dict]]] = {}
    lang_to_word_entries: Dict[str, Dict[str, List[dict]]] = {}

    for word_list_path in resources_dir.glob("*/taboo_word_lists.json"):
        lang_code = word_list_path.parent.name
        print(lang_code)
        with word_list_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        categories: Dict[str, List[dict]] = {}
        word_entries: Dict[str, List[dict]] = defaultdict(list)

        for category, words in data.items():
            if not isinstance(words, list):
                continue

            category_entries = []
            for raw_word in words:
                if not isinstance(raw_word, str):
                    continue
                word = normalize_word(raw_word, lang_code)
                if len(word) < 1:
                    continue

                entry = {
                    "target_word": word,
                    "word_relations": [],
                }
                category_entries.append(entry)
                word_entries[word].append(entry)

            categories[category] = category_entries

        lang_to_categories[lang_code] = categories
        lang_to_word_entries[lang_code] = word_entries

    return lang_to_categories, lang_to_word_entries


def save_word_relations(resources_dir: Path, lang_to_categories: Dict[str, Dict[str, List[dict]]]):
    for lang_code, categories in lang_to_categories.items():
        out_path = resources_dir / lang_code / "word_relations.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(categories, f, ensure_ascii=False, indent=2)


# -------------------------------------------------------------------
# MAIN EXTRACTION
# -------------------------------------------------------------------


def extract_relations_from_conceptnet(
    conceptnet_path: Path,
    lang_to_word_entries: Dict[str, Dict[str, List[dict]]],
):
    """
    Scan ConceptNet once and populate each entry's word_relations list.
    """
    # Per-entry dedupe: (relation_label, related_word) -> weight
    entry_relation_maps: Dict[int, Dict[Tuple[str, str], float]] = {}

    for lang, word_entries in lang_to_word_entries.items():
        print('Processing', lang, len(word_entries.values()))
        for entries in word_entries.values():
            for entry in entries:
                entry_relation_maps[id(entry)] = {}

    line_count = 0

    with gzip.open(conceptnet_path, "rt", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE)

        for row in reader:
            line_count += 1
            if len(row) < 5:
                continue

            _, relation, start_node, end_node, json_metadata = row

            if relation not in VALID_RELATIONS:
                continue

            start = parse_uri(start_node)
            end = parse_uri(end_node)
            if not start or not end:
                continue

            if start["lang"] != end["lang"]:
                continue

            lang_code = start["lang"]
            if lang_code not in lang_to_word_entries:
                continue

            try:
                meta = json.loads(json_metadata)
                weight = float(meta.get("weight", 0))
            except Exception:
                continue

            start_text = normalize_word(start["text"].replace("_", " "), lang_code)
            end_text = normalize_word(end["text"].replace("_", " "), lang_code)

            lang_config = LANGUAGES.get(lang_code, {})
            check_single_word = lang_config.get("single_word_check", True)

            relation_label = normalize_relation(relation)

            # Forward direction: start is target, end is related
            start_entries = get_word_entries(lang_to_word_entries[lang_code], lang_code, start_text)
            if start_entries:
                if not (check_single_word and not is_single_word(end_text)):
                    for entry in start_entries:
                        relation_map = entry_relation_maps[id(entry)]
                        key = (relation_label, end_text)
                        if key not in relation_map or weight > relation_map[key]:
                            relation_map[key] = weight

            # Bidirectional for Synonym/RelatedTo
            if relation in ["/r/Synonym", "/r/RelatedTo"]:
                end_entries = get_word_entries(lang_to_word_entries[lang_code], lang_code, end_text)
                if end_entries:
                    if not (check_single_word and not is_single_word(start_text)):
                        for entry in end_entries:
                            relation_map = entry_relation_maps[id(entry)]
                            key = (relation_label, start_text)
                            if key not in relation_map or weight > relation_map[key]:
                                relation_map[key] = weight

    # Move deduped maps into word_relations list
    for lang_entries in lang_to_word_entries.values():
        for entries in lang_entries.values():
            for entry in entries:
                relation_map = entry_relation_maps.get(id(entry), {})
                relation_list = [
                    {"word": word, "relation": rel, "weight": weight}
                    for (rel, word), weight in relation_map.items()
                ]
                relation_list.sort(key=lambda x: x["weight"], reverse=True)
                entry["word_relations"] = relation_list


def main():
    script_dir = Path(__file__).resolve().parent
    resources_dir = script_dir / "resources"
    conceptnet_path = script_dir.parent / "conceptnet-assertions-5.7.0.csv.gz"

    if not conceptnet_path.exists():
        raise FileNotFoundError(f"ConceptNet file not found: {conceptnet_path}")

    print('Loading word lists')
    lang_to_categories, lang_to_word_entries = load_taboo_word_lists(resources_dir)

    if not lang_to_word_entries:
        print("No taboo word lists found under resources/<lang_id>/taboo_word_lists.json")
        return

    print('Extracting the relations from ConceptNet')
    extract_relations_from_conceptnet(conceptnet_path, lang_to_word_entries)

    print('Saving the relations from ConceptNet')
    save_word_relations(resources_dir, lang_to_categories)

    print("Done. Saved word relations per language under taboo/resources/<lang_id>/word_relations.json")


if __name__ == "__main__":
    main()
