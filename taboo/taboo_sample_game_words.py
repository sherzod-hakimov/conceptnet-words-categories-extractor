#!/usr/bin/env python3
"""
Sample target words and taboo words for a Taboo-style game.

Reads:
  taboo/resources/<lang_id>/word_relations_with_similarity.json

Writes:
  taboo/resources/<lang_id>/high_frequency_taboo_words.json
  taboo/resources/<lang_id>/low_frequency_taboo_words.json

Rules (language-agnostic):
  1) Prefer Synonym/IsA by highest similarity with edit_similarity <= 0.2
     and reject candidates too similar to existing taboo words (> 0.4 edit similarity)
  2) If still short, add from other relations (exclude related_to, derived_from)
     where lemma_edit_similarity <= 0.3, also rejecting too-similar candidates
  3) Keep targets even if only 2 taboo words after step 2
  4) If minimum quota not reached, revisit those 2-taboo targets and add one
     related_to word with lemma_edit_similarity <= 0.2 to reach 3
  5) Save only targets with 3 taboo words
"""

import argparse
import json
from pathlib import Path
from typing import Dict, List


def is_single_word(text: str) -> bool:
    return " " not in text.strip()


def edit_distance_similarity(a: str, b: str) -> float:
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0

    len_a = len(a)
    len_b = len(b)
    prev = list(range(len_b + 1))
    curr = [0] * (len_b + 1)

    for i in range(1, len_a + 1):
        curr[0] = i
        ca = a[i - 1]
        for j in range(1, len_b + 1):
            cb = b[j - 1]
            cost = 0 if ca == cb else 1
            curr[j] = min(
                prev[j] + 1,
                curr[j - 1] + 1,
                prev[j - 1] + cost,
            )
        prev, curr = curr, prev

    dist = prev[len_b]
    max_len = max(len_a, len_b)
    return 1.0 - (dist / max_len)


def is_too_similar_to_existing(taboo: List[dict], candidate_word: str) -> bool:
    for rel in taboo:
        existing_word = rel.get("word", "").strip()
        if not existing_word:
            continue
        if edit_distance_similarity(existing_word, candidate_word) > 0.4:
            return True
    return False


def pick_taboo_words_initial(word_relations: List[dict]) -> List[dict]:
    """Pick taboo words using Synonym priority and allowed relations.

    Returns up to 3 taboo words.
    """
    taboo = []
    seen = set()

    # 1) accepted relations priority by highest similarity with edit_similarity <= 0.2
    first_pass = [
        rel
        for rel in word_relations
        if rel.get("relation") in ["synonym", "is_a", "part_of", "antonym", "similar_to"]
        and rel.get("edit_similarity") is not None
        and float(rel.get("edit_similarity")) <= 0.2
    ]
    first_pass.sort(key=lambda r: float(r.get("similarity") or 0.0), reverse=True)
    for rel in first_pass:
        word = rel.get("word", "").strip()
        if not word or word in seen:
            continue
        if is_too_similar_to_existing(taboo, word):
            continue
        taboo.append(rel)
        seen.add(word)
        if len(taboo) >= 3:
            return taboo

    # 2) Other relations excluding related_to and derived_from, lemma_edit_similarity <= 0.3
    for rel in word_relations:
        relation = rel.get("relation")
        if relation in ["synonym", "derived_from"]:
            continue
        les = rel.get("lemma_edit_similarity")
        if les is None or float(les) > 0.3:
            continue
        word = rel.get("word", "").strip()
        if not word or word in seen:
            continue
        if is_too_similar_to_existing(taboo, word):
            continue
        taboo.append(rel)
        seen.add(word)
        if len(taboo) >= 3:
            return taboo

    return taboo


def add_related_to_if_needed(taboo: List[dict], word_relations: List[dict]) -> List[dict]:
    if len(taboo) >= 3:
        return taboo
    seen = {rel.get("word", "").strip() for rel in taboo}
    for rel in word_relations:
        if rel.get("relation") != "related_to":
            continue
        les = rel.get("lemma_edit_similarity")
        if les is None or float(les) > 0.2:
            continue
        word = rel.get("word", "").strip()
        if not word or word in seen:
            continue
        taboo.append(rel)
        return taboo
    return taboo


def to_output_entries(samples: List[dict]) -> List[dict]:
    output = []
    for sample in samples:
        target = sample.get("target_word", "").strip()
        taboo_words = sample.get("taboo_words", [])
        related = [w.get("word", "").strip() for w in taboo_words if w.get("word")]
        related_stem = [w.get("word", "").strip() for w in taboo_words if w.get("word")]
        if not target or len(related) != 3:
            continue
        output.append(
            {
                "target_word": target,
                "related_word": related,
                "target_word_stem": target,
                "related_word_stem": related_stem,
            }
        )
    return output


def sample_category(
    data: Dict[str, List[dict]],
    category_names: List[str],
    require_single_word: bool,
) -> List[dict]:
    samples = []
    two_taboo = []
    for category, entries in data.items():
        if category not in category_names:
            continue
        for entry in entries:
            target = entry.get("target_word", "").strip()
            if not target:
                continue
            if require_single_word and not is_single_word(target):
                continue

            word_relations = entry.get("word_relations", [])
            taboo_words = pick_taboo_words_initial(word_relations)

            if len(taboo_words) == 3:
                samples.append(
                    {
                        "target_word": target,
                        "taboo_words": taboo_words,
                        "source_category": category,
                    }
                )
            elif len(taboo_words) == 2:
                two_taboo.append(
                    {
                        "target_word": target,
                        "taboo_words": taboo_words,
                        "word_relations": word_relations,
                        "source_category": category,
                    }
                )

    return samples, two_taboo


def finalize_samples_with_related_to(
    samples: List[dict],
    two_taboo: List[dict],
    min_per_category: int,
) -> List[dict]:
    if len(samples) >= min_per_category:
        return samples
    for item in two_taboo:
        taboo = add_related_to_if_needed(item["taboo_words"], item["word_relations"])
        if len(taboo) == 3:
            samples.append(
                {
                    "target_word": item["target_word"],
                    "taboo_words": taboo,
                    "source_category": item["source_category"],
                }
            )
        if len(samples) >= min_per_category:
            break
    return samples


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sample target words + taboo words from word_relations_with_similarity.json"
    )
    parser.add_argument(
        "--resources-dir",
        default=str(Path(__file__).resolve().parent / "resources"),
        help="Path to taboo resources directory",
    )
    parser.add_argument("--min-per-category", type=int, default=50)
    parser.add_argument("--require-single-word", action="store_true", default=True)
    parser.add_argument("--allow-multi-word", action="store_true", default=False)
    args = parser.parse_args()

    require_single_word = args.require_single_word and not args.allow_multi_word
    resources_dir = Path(args.resources_dir)

    rel_paths = list(resources_dir.glob("*/word_relations_with_similarity.json"))
    if not rel_paths:
        print("No word_relations_with_similarity.json files found.")
        return

    for rel_path in rel_paths:
        lang_code = rel_path.parent.name
        with rel_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        high_samples, high_two = sample_category(
            data,
            category_names=["high"],
            require_single_word=require_single_word,
        )
        low_samples, low_two = sample_category(
            data,
            category_names=["low", "medium"],
            require_single_word=require_single_word,
        )

        if len(high_samples) < args.min_per_category:
            high_samples = finalize_samples_with_related_to(
                high_samples,
                high_two,
                args.min_per_category,
            )
        if len(low_samples) < args.min_per_category:
            low_samples = finalize_samples_with_related_to(
                low_samples,
                low_two,
                args.min_per_category,
            )

        high_output = to_output_entries(high_samples)
        low_output = to_output_entries(low_samples)

        high_path = rel_path.parent / "high_frequency_taboo_words.json"
        low_path = rel_path.parent / "low_frequency_taboo_words.json"

        with high_path.open("w", encoding="utf-8") as f:
            json.dump(high_output, f, ensure_ascii=False, indent=2)
        with low_path.open("w", encoding="utf-8") as f:
            json.dump(low_output, f, ensure_ascii=False, indent=2)

        print(
            f"{lang_code}: wrote {len(high_output)} high, {len(low_output)} low -> {high_path} / {low_path}"
        )


if __name__ == "__main__":
    main()
