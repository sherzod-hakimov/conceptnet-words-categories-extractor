import json
import os
import stanza
from better_profanity import profanity

# --- CONFIGURATION ---
INPUT_FILE = "word_lists.json"
OUTPUT_FILE = "safe_nouns_only.json"
MIN_LENGTH = 4


def filter_words():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Error: Input file '{INPUT_FILE}' not found.")
        return

    # 1. Initialize Safety Filter
    profanity.load_censor_words()

    # Add custom blocklist for words that might bypass standard filters
    # (These appear in your specific dataset)
    custom_bad_words = {
        "sex", "porn", "porno", "xxx", "fuck", "rape", "dick", "cock",
        "pussy", "anal", "blowjob", "cum", "milf", "orgy", "nude",
        "nudity", "breast", "penis", "vagina", "slut", "whore",
        "bitch", "masturbate", "masturbation", "sexuality", "sexual",
        "erotic", "erotica", "incest", "beastiality", "voyeur",
        "shemale", "tranny", "bondage", "hentai", "nazi", "hitler"
    }
    profanity.add_censor_words(custom_bad_words)

    # 2. Initialize Stanza NLP
    print("   Initializing Stanza (downloading English model if needed)...")
    stanza.download('en', processors='tokenize,pos', verbose=False, model_dir='../stanza_resources')
    # We only need tokenize and pos processors
    nlp = stanza.Pipeline(lang='en', processors='tokenize,pos', verbose=False, use_gpu=True)

    # 3. Load Data
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    cleaned_data = {
        "high": [],
        "medium": [],
        "low": []
    }

    total_input = 0
    total_kept = 0

    # 4. Process Categories
    for category in ["high", "medium", "low"]:
        source_list = data.get(category, [])
        total_input += len(source_list)
        print(f"   Processing '{category}' ({len(source_list)} words)...")

        valid_words = []

        # Batching isn't strictly necessary for <5000 words,
        # but processing one-by-one ensures accurate POS tagging for single words.
        for word in source_list:
            word_str = str(word).strip().lower()

            # --- FILTER 1: Length ---
            if len(word_str) < MIN_LENGTH:
                continue

            # --- FILTER 2: Safety/Profanity ---
            if profanity.contains_profanity(word_str):
                continue

            # --- FILTER 3: Stanza Noun Check ---
            doc = nlp(word_str)

            # Check if the word exists and what its tag is
            if doc.sentences and doc.sentences[0].words:
                token = doc.sentences[0].words[0]

                # UPOS tags: NOUN (common noun), PROPN (proper noun)
                if token.upos in ['NOUN']:
                    valid_words.append(word)

        cleaned_data[category] = valid_words
        total_kept += len(valid_words)

    # 5. Save Results
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(cleaned_data, f, indent=4)

    print(f"\n✅ Done!")
    print(f"   Input Words: {total_input}")
    print(f"   Safe Nouns Saved: {total_kept}")
    print(f"   File saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    filter_words()