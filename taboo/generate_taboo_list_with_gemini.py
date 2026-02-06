import os
import json
from openai import OpenAI
from typing import List, Dict, Any

# ---------------- CONFIGURATION ---------------- #

# Replace with your actual Google GenAI API Key
API_KEY = "API-key"

# The base URL for Gemini's OpenAI-compatible endpoint
BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

# Target Model
MODEL_NAME = "gemini-2.0-flash"

# Number of samples to generate per category per run
NUM_SAMPLES = 20

# Dictionary of languages: key = folder name/id, value = Language Name
LANGUAGES = {
    "sl": "Slovenian",
    "sk": "Slovak",
'ga': 'Irish',
'mt': 'Maltese',
'da': 'Danish',
'lv': 'Latvian',
'ar': 'Arabic',
'hr': 'Croatian',
'bg': 'Bulgarian',
'et': 'Estonian',
'lt': 'Lithuanian',
    # Add more languages here, e.g., "es": "Spanish", "fr": "French"
}

# ----------------------------------------------- #

client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL
)


def ensure_directory(path: str):
    if not os.path.exists(path):
        os.makedirs(path)


def load_existing_data(filepath: str) -> List[Dict]:
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: Could not decode {filepath}. Starting fresh.")
            return []
    return []


def save_data(filepath: str, data: List[Dict]):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def generate_taboo_words(lang_name: str, frequency: str, count: int) -> List[Dict]:
    """
    Generates a list of taboo words using Gemini via OpenAI API compatibility.
    """

    # System prompt defines the persona and output format strictly
    system_instruction = f"""
    You are an expert linguist and game designer. 
    Generate a JSON list of {count} "{frequency}" words for the game Taboo in {lang_name}.

    For each entry, you must provide:
    1. "target_word": The word to be guessed.
    2. "related_word": A list of 3 taboo words that cannot be said.
    3. "target_word_stem": The stem/root of the target word.
    4. "related_word_stem": A list of stems/roots for the taboo words.

    The output must be a valid JSON array strictly following this structure:
    [
      {{
        "target_word": "example",
        "related_word": ["taboo1", "taboo2", "taboo3"],
        "target_word_stem": "exampl",
        "related_word_stem": ["tab1", "tab2", "tab3"]
      }}
    ]

    Do not wrap the JSON in markdown blocks (```json). Return raw JSON only.
    Ensure words are culturally appropriate and accurately fit the "{frequency}" frequency profile in {lang_name}.
    """

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that outputs raw JSON."},
                {"role": "user", "content": system_instruction}
            ],
            temperature=0.7,
        )

        content = response.choices[0].message.content.strip()

        # Clean up markdown if model adds it despite instructions
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]

        return json.loads(content)

    except Exception as e:
        print(f"Error generating data for {lang_name} ({frequency}): {e}")
        return []


def merge_data(existing: List[Dict], new_items: List[Dict]) -> List[Dict]:
    """
    Merges new items into existing list, avoiding duplicates based on 'target_word'.
    """
    existing_targets = {item['target_word'] for item in existing}

    merged = existing.copy()
    for item in new_items:
        if item['target_word'] not in existing_targets:
            merged.append(item)
            existing_targets.add(item['target_word'])

    return merged


def main():
    base_dir = "resources"
    ensure_directory(base_dir)

    categories = ["high_frequency", "low_frequency"]

    for lang_id, lang_name in LANGUAGES.items():
        print(f"--- Processing Language: {lang_name} ({lang_id}) ---")

        lang_dir = os.path.join(base_dir, lang_id)
        ensure_directory(lang_dir)

        for category in categories:
            filename = f"{category}_taboo_words.json"
            filepath = os.path.join(lang_dir, filename)

            # 1. Load existing
            existing_data = load_existing_data(filepath)
            print(f"  [{category}] Loaded {len(existing_data)} existing items.")

            # 2. Generate new
            print(f"  [{category}] Generating {NUM_SAMPLES} new samples...")
            new_data = generate_taboo_words(lang_name, category.replace("_", " "), NUM_SAMPLES)

            if new_data:
                # 3. Merge
                merged_data = merge_data(existing_data, new_data)
                added_count = len(merged_data) - len(existing_data)

                # 4. Save
                save_data(filepath, merged_data)
                print(f"  [{category}] Saved. Added {added_count} new unique words. Total: {len(merged_data)}")
            else:
                print(f"  [{category}] No data generated.")


if __name__ == "__main__":
    main()