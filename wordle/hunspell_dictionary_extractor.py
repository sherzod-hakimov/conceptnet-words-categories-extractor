import argparse
import os
import requests
import subprocess
import sys

# 1. Configuration
# Map ISO codes to the specific folder names in the wooorm repo
# You can verify names here: https://github.com/wooorm/dictionaries/tree/main/dictionaries
LANG_MAP = {
    'bg': 'bg', 'hr': 'hr', 'cs': 'cs', 'da': 'da', 'nl': 'nl',
    'en': 'en', 'et': 'et', 'fi': 'fi', 'fr': 'fr', 'de': 'de',
    'el': 'el', 'hu': 'hu', 'ga': 'ga', 'it': 'it', 'lv': 'lv',
    'lt': 'lt', 'mt': 'mt', 'pl': 'pl', 'pt': 'pt', 'ro': 'ro',
    'sk': 'sk', 'sl': 'sl', 'es': 'es', 'sv': 'sv',
    'ru': 'ru', 'tr': 'tr'
}

LANG_MAP = {
    'ur': 'ur'
}

OUTPUT_DIR = "resources"
TARGET_LENGTH = 5


def download_file(url, save_path):
    with requests.get(url, stream=True) as response:
        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
            return True
        else:
            print(f"   ❌ Failed to download: {url}")
            return False


def resolve_dictionary_paths(lang_code, base_url, prefer_local):
    local_dic = f"{lang_code}.dic"
    local_aff = f"{lang_code}.aff"
    downloaded = []

    if prefer_local and os.path.exists(local_dic) and os.path.exists(local_aff):
        return local_dic, local_aff, downloaded

    dic_name = "index.dic"
    aff_name = "index.aff"

    if not download_file(f"{base_url}/{dic_name}", local_dic):
        return None, None, downloaded
    if not download_file(f"{base_url}/{aff_name}", local_aff):
        return None, None, downloaded

    downloaded.extend([local_dic, local_aff])
    return local_dic, local_aff, downloaded


def download_only(lang_code, folder_name, prefer_local):
    print(f"\n--- Downloading {lang_code.upper()} ---")
    base_url = f"https://raw.githubusercontent.com/wooorm/dictionaries/main/dictionaries/{folder_name}"

    dic_path, aff_path, _downloaded_files = resolve_dictionary_paths(
        lang_code, base_url, prefer_local
    )
    if not dic_path or not aff_path:
        return

    print(f"   ✅ Saved {dic_path} and {aff_path}")


def process_language(lang_code, folder_name, force, prefer_local):
    print(f"\n--- Processing {lang_code.upper()} ---")

    # Base URL for the raw files
    base_url = f"https://raw.githubusercontent.com/wooorm/dictionaries/main/dictionaries/{folder_name}"

    output_file = os.path.join(OUTPUT_DIR, lang_code, "allowed_words.txt")
    if not force and os.path.exists(output_file) and os.path.getsize(output_file) > 0:
        print(f"   ⏭️  Output already exists, skipping: {output_file}")
        return

    # 1. Resolve dictionary sources (prefer local if present)
    print("   Resolving dictionary files...")
    dic_path, aff_path, downloaded_files = resolve_dictionary_paths(
        lang_code, base_url, prefer_local
    )
    if not dic_path or not aff_path:
        return

    # 2. Unmunch (Expand the dictionary)
    # Command: unmunch list.dic list.aff > output.txt
    print("   Running 'unmunch' to expand words (this may take time)...")
    try:
        # We capture stdout directly
        process = subprocess.Popen(
            ['unmunch', dic_path, aff_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='ignore'
        )

        valid_words = set()

        # Stream the output line by line to save memory
        for line in process.stdout:
            word = line.strip()
            # Clean up: strict 5 letters, usually lowercase
            # Some dicts include "/" flags in output, unmunch handles most, but be safe.
            if len(word) == TARGET_LENGTH and word.isalpha():
                valid_words.add(word.lower())

        process.wait()

        # 3. Save
        # create the folder path if doesn't exist
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            # Sort for neatness
            for w in sorted(valid_words):
                f.write(f"{w}\n")

        print(f"   ✅ Saved {len(valid_words)} words to {output_file}")

    except FileNotFoundError:
        print("   ❌ Error: 'unmunch' command not found.")
        print("      Please install Hunspell tools (apt install hunspell-tools / brew install hunspell)")
        return
    except Exception as e:
        print(f"   ❌ Error processing: {e}")

    # Cleanup downloaded raw files (keep local dictionaries)
    for path in downloaded_files:
        try:
            os.remove(path)
        except OSError:
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract fixed-length word lists from Hunspell dictionaries."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild outputs even if they already exist.",
    )
    parser.add_argument(
        "--prefer-local",
        action="store_true",
        help="Use local <lang>.dic/<lang>.aff if present to skip downloads.",
    )
    parser.add_argument(
        "--download-only",
        action="store_true",
        help="Only download dictionaries (.dic/.aff) for all languages.",
    )
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if args.download_only:
        for code, folder in LANG_MAP.items():
            download_only(code, folder, prefer_local=args.prefer_local)
        sys.exit(0)

    # Verify unmunch exists before starting
    try:
        subprocess.run(['unmunch', '-h'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        print("CRITICAL ERROR: 'unmunch' is not installed or not in PATH.")
        print("Install it via: 'brew install hunspell' or 'sudo apt install hunspell-tools'")
        sys.exit(1)

    for code, folder in LANG_MAP.items():
        process_language(code, folder, force=args.force, prefer_local=args.prefer_local)
