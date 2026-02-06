



import os
import json
import time
import re
from openai import OpenAI
import math

# --- CONFIGURATION ---

API_KEY = "API-key"

# 1. API Configuration
BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
MODEL_NAME = "gemini-2.0-flash"

# 2. Settings
# Batch size: Sends 50 words at a time to ensure complete responses
BATCH_SIZE = 50

# 3. Target Languages
target_langs = {
    'ar': 'Arabic', 'bg': 'Bulgarian', 'hr': 'Croatian', 'cs': 'Czech', 'da': 'Danish',
    'nl': 'Dutch', 'et': 'Estonian', 'fi': 'Finnish',
    'fr': 'French', 'de': 'German', 'el': 'Greek', 'hu': 'Hungarian',
    'ga': 'Irish', 'it': 'Italian', 'lv': 'Latvian', 'lt': 'Lithuanian',
    'mt': 'Maltese', 'pl': 'Polish', 'pt': 'Portuguese', 'ro': 'Romanian',
    'ru': 'Russian',
    'sk': 'Slovak', 'sl': 'Slovenian', 'es': 'Spanish', 'sv': 'Swedish',
    'tr': 'Turkish', 'ur': 'Urdu'
}

target_langs = {
    'ar': 'Arabic', 'bg': 'Bulgarian', 'hr': 'Croatian', 'cs': 'Czech', 'da': 'Danish',
    'nl': 'Dutch',  'et': 'Estonian', 'fi': 'Finnish',
    'fr': 'French',  'el': 'Greek', 'hu': 'Hungarian',
    'ga': 'Irish', 'it': 'Italian', 'lv': 'Latvian', 'lt': 'Lithuanian',
    'mt': 'Maltese', 'pl': 'Polish', 'pt': 'Portuguese', 'ro': 'Romanian',
    'ru': 'Russian',
    'sk': 'Slovak', 'sl': 'Slovenian', 'es': 'Spanish', 'sv': 'Swedish',
     'ur': 'Urdu'
}

BASE_DIR = "resources"
INPUT_FILE = "safe_nouns.json"


# --- HELPER FUNCTIONS ---

def load_source_json(filepath):
    if not os.path.exists(filepath):
        print(f"❌ Critical Error: Input file '{filepath}' not found.")
        return None
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def extract_words_robust(text):
    """
    Attempts to parse JSON. If that fails (truncated output),
    uses Regex to extract all quoted strings found so far.
    """
    text = text.strip()

    # 1. Try standard JSON parsing first
    # Clean markdown wrappers
    clean_text = text
    if clean_text.startswith("```json"): clean_text = clean_text[7:]
    if clean_text.startswith("```"): clean_text = clean_text[3:]
    if clean_text.endswith("```"): clean_text = clean_text[:-3]

    try:
        data = json.loads(clean_text)
        if isinstance(data, list):
            return [str(w) for w in data]
    except json.JSONDecodeError:
        pass  # Fall through to regex salvage

    # 2. Regex Salvage
    # Looks for strings inside double quotes: "word"
    # This captures everything even if the list doesn't close with ']'
    found_words = re.findall(r'"([^"]+)"', text)

    return found_words


def is_single_token(word):
    """
    Returns True if the word is a single token (no spaces).
    Adjust logic here if 'token' means something else to you.
    """
    return len(word.strip().split()) == 1


def translate_chunk(client, chunk, category_name, lang_name):
    """Translates a small batch of words."""



    system_prompt = "You are a specialized translation engine. Output ONLY a JSON array."
    list_str = json.dumps(chunk, indent=None)

    if lang_name == 'English':
        clean_words = [w for w in chunk if is_single_token(w)]
        return clean_words

    user_prompt = f"""
    Translate these {len(chunk)} words into {lang_name}.

    Source List: {list_str}

    Requirements:
    1. Output exactly one JSON array: ["trans1", "trans2"].
    2. Skip words that are not nouns
    3. Do not include any profanity or swear words in the target language
    4. All returned words should be safe words
    4. Return ONLY single-word translations if possible.
    5. No Markdown.
    """

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            # extra_body={
            #     "safetySettings": [
            #         {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            #         {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            #         {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            #         {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
            #     ]
            # }
        )

        content = response.choices[0].message.content

        # Use the robust extractor
        words = extract_words_robust(content)

        # Filter: Single tokens only
        clean_words = [w for w in words if is_single_token(w)]

        return clean_words

    except Exception as e:
        print(f"      ❌ Error on chunk: {e}")
        return []


def process_category(client, full_list, category_name, lang_name):
    """Splits a large category list into batches and translates them."""
    if not full_list:
        return []

    print(f"      Processing '{category_name}' ({len(full_list)} words)...")

    translated_results = []

    # Batch processing
    num_batches = math.ceil(len(full_list) / BATCH_SIZE)

    for i in range(num_batches):
        start_idx = i * BATCH_SIZE
        end_idx = start_idx + BATCH_SIZE
        chunk = full_list[start_idx:end_idx]

        # Translate chunk
        chunk_results = translate_chunk(client, chunk, category_name, lang_name)
        translated_results.extend(chunk_results)

        # Small sleep to be polite to API limits
        time.sleep(0.5)

    # Remove duplicates while preserving order
    seen = set()
    unique_results = []
    for w in translated_results:
        if w not in seen:
            unique_results.append(w)
            seen.add(w)

    return unique_results


def process_language(client, source_data, lang_code, lang_name):
    print(f"[{lang_code.upper()}] Processing {lang_name}...")

    folder_path = os.path.join(BASE_DIR, lang_code)
    os.makedirs(folder_path, exist_ok=True)
    file_path = os.path.join(folder_path, "taboo_word_lists.json")

    # if os.path.exists(file_path):
    #     print(f"   File exists. Skipping.")
    #     return

    translated_data = {}

    for key in ["high", "medium", "low"]:
        source_list = source_data.get(key, [])
        translated_list = process_category(client, source_list, key, lang_name)
        translated_data[key] = translated_list

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(translated_data, f, indent=4, ensure_ascii=False)
    print(
        f"   ✅ Saved {len(translated_data['high']) + len(translated_data['medium']) + len(translated_data['low'])} words to {file_path}")


# --- MAIN ---

if __name__ == "__main__":
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    source_data = load_source_json(INPUT_FILE)

    if source_data:
        print(f"Starting batched translation (Batch Size: {BATCH_SIZE})...\n")
        for code, name in target_langs.items():
            process_language(client, source_data, code, name)
        print("\nDone.")

