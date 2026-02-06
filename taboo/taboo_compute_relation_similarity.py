#!/usr/bin/env python3
"""
Compute cosine similarity between target words and related words.

Reads:
  taboo/resources/<lang_id>/word_relations.json

Writes:
  taboo/resources/<lang_id>/word_relations_with_similarity.json

Output keeps the same structure and adds "similarity", "edit_similarity",
and "lemma_edit_similarity" to each word relation.
"""

import json
from pathlib import Path
from typing import Dict, List

import torch
import stanza
from sentence_transformers import SentenceTransformer, util


# -------------------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------------------
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
BATCH_SIZE = 256
STANZA_DIR = "stanza_resources"


def load_word_relations(resources_dir: Path) -> Dict[str, Dict[str, List[dict]]]:
    lang_to_data: Dict[str, Dict[str, List[dict]]] = {}
    for rel_path in resources_dir.glob("*/word_relations.json"):
        lang_code = rel_path.parent.name
        with rel_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        lang_to_data[lang_code] = data
    return lang_to_data


def save_word_relations(
    resources_dir: Path, lang_to_data: Dict[str, Dict[str, List[dict]]]
):
    for lang_code, data in lang_to_data.items():
        out_path = resources_dir / lang_code / "word_relations_with_similarity.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def embed_words(model: SentenceTransformer, words: List[str]) -> Dict[str, torch.Tensor]:
    embeddings = {}
    for i in range(0, len(words), BATCH_SIZE):
        batch = words[i : i + BATCH_SIZE]
        batch_emb = model.encode(
            batch, batch_size=BATCH_SIZE, show_progress_bar=False, convert_to_tensor=True
        )
        for w, emb in zip(batch, batch_emb):
            embeddings[w] = emb
    return embeddings


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
                prev[j] + 1,      # deletion
                curr[j - 1] + 1,  # insertion
                prev[j - 1] + cost,  # substitution
            )
        prev, curr = curr, prev

    dist = prev[len_b]
    max_len = max(len_a, len_b)
    return 1.0 - (dist / max_len)


def create_stanza_pipeline(lang_code: str, model_dir: Path):
    processors = "tokenize,mwt,pos,lemma"
    try:
        return stanza.Pipeline(
            lang=lang_code,
            processors=processors,
            verbose=False,
            use_gpu=False,
            model_dir=str(model_dir),
        )
    except Exception:
        return stanza.Pipeline(
            lang=lang_code,
            processors="tokenize,pos,lemma",
            verbose=False,
            use_gpu=False,
            model_dir=str(model_dir),
        )


def lemmatize_words(
    words: List[str],
    lang_code: str,
    model_dir: Path,
    pipeline_cache: Dict[str, stanza.Pipeline],
) -> Dict[str, str]:
    if lang_code not in pipeline_cache:
        pipeline_cache[lang_code] = create_stanza_pipeline(lang_code, model_dir)

    nlp = pipeline_cache[lang_code]
    lemmas: Dict[str, str] = {}

    for word in words:
        if not word:
            lemmas[word] = ""
            continue
        try:
            doc = nlp(word)
        except Exception:
            lemmas[word] = word
            continue

        if not doc.sentences:
            lemmas[word] = word
            continue

        lemma_tokens = []
        for sentence in doc.sentences:
            for w in sentence.words:
                if w.lemma:
                    lemma_tokens.append(w.lemma)
                elif w.text:
                    lemma_tokens.append(w.text)

        lemmas[word] = " ".join(lemma_tokens) if lemma_tokens else word

    return lemmas


def add_similarity_scores(
    model: SentenceTransformer, lang_to_data: Dict[str, Dict[str, List[dict]]]
):
    script_dir = Path(__file__).resolve().parent
    model_dir = script_dir.parent / STANZA_DIR
    pipeline_cache: Dict[str, stanza.Pipeline] = {}

    for lang_code, data in lang_to_data.items():
        print(lang_code)
        # Collect unique words (targets + related)
        unique_words = set()
        for category, entries in data.items():
            print(category, len(entries))
            for entry in entries:
                target_word = entry.get("target_word", "").strip()
                if target_word:
                    unique_words.add(target_word)
                for rel in entry.get("word_relations", []):
                    related_word = rel.get("word", "").strip()
                    if related_word:
                        unique_words.add(related_word)

        if not unique_words:
            continue

        word_list = sorted(unique_words)
        word_embeddings = embed_words(model, word_list)
        word_lemmas = lemmatize_words(word_list, lang_code, model_dir, pipeline_cache)

        # Compute similarities
        for category, entries in data.items():
            for entry in entries:
                target_word = entry.get("target_word", "").strip()
                target_vec = word_embeddings.get(target_word)
                target_lemma = word_lemmas.get(target_word, target_word)
                if target_vec is None:
                    continue

                for rel in entry.get("word_relations", []):
                    related_word = rel.get("word", "").strip()
                    related_vec = word_embeddings.get(related_word)
                    related_lemma = word_lemmas.get(related_word, related_word)
                    if related_vec is None:
                        continue
                    similarity = util.cos_sim(target_vec, related_vec).item()
                    rel["similarity"] = float(similarity)
                    rel["edit_similarity"] = float(
                        edit_distance_similarity(target_word, related_word)
                    )
                    rel["lemma_edit_similarity"] = float(
                        edit_distance_similarity(target_lemma, related_lemma)
                    )


def main():
    script_dir = Path(__file__).resolve().parent
    resources_dir = script_dir / "resources"

    if not resources_dir.exists():
        raise FileNotFoundError(f"Resources folder not found: {resources_dir}")

    lang_to_data = load_word_relations(resources_dir)
    if not lang_to_data:
        print("No word_relations.json files found under resources/<lang_id>/")
        return

    model = SentenceTransformer(MODEL_NAME)
    add_similarity_scores(model, lang_to_data)
    save_word_relations(resources_dir, lang_to_data)

    print("Done. Saved word_relations_with_similarity.json per language.")


if __name__ == "__main__":
    main()
