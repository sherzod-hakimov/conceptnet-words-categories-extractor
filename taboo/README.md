# Taboo Game Word Lists

This directory contains word lists for the Taboo game in 28 languages (EU-24 + Russian + Urdu + Arabic + Maltese).

## Overview

Each language has a set of target words with 3 related "taboo" words that players cannot use when describing the target word. The word lists are split into two difficulty levels:
- **High frequency**: Top 50 most common nouns with relations
- **Low frequency**: Additional nouns for extended gameplay

## Directory Structure

```
taboo/
├── README.md                                    # This file
├── taboo_extract_frequent_nouns.py              # Script to extract frequent nouns
├── taboo_extract_relations_from_conceptnet.py   # Script to extract taboo words from ConceptNet
├── frequent_nouns/                              # Extracted noun frequency lists
│   ├── ar_nouns.csv
│   ├── bg_nouns.csv
│   └── ... (one CSV per language)
└── resources/                                   # Final taboo word lists
    ├── ar/
    │   ├── high_frequency_taboo_words.json
    │   └── low_frequency_taboo_words.json
    ├── bg/
    │   ├── high_frequency_taboo_words.json
    │   └── low_frequency_taboo_words.json
    └── ... (28 languages total)
```

## Supported Languages

- **EU-24**: bg, cs, da, de, el, en, es, et, fi, fr, ga, hr, hu, it, lt, lv, mt, nl, pl, pt, ro, sk, sl, sv
- **Additional**: ar (Arabic), ru (Russian), tr (Turkish), ur (Urdu)

## Data Format

Each JSON file contains an array of word entries with this structure:

```json
{
  "target_word": "winter",
  "related_word": ["cold", "snow", "season"],
  "target_word_stem": "winter",
  "related_word_stem": ["cold", "snow", "season"]
}
```

- `target_word`: The word players must describe
- `related_word`: Array of 3 taboo words that cannot be used
- `target_word_stem`: Stem/lemma form of the target word
- `related_word_stem`: Stem/lemma forms of the related words

## Curation Process

### Automated Curation (25 languages)

For most languages (bg, cs, da, de, el, en, es, et, fi, fr, ga, hu, it, lt, lv, nl, pl, pt, ro, ru, sk, sl, sv, tr, ur), the curation process is fully automated:

1. **Noun Extraction** (`taboo_extract_frequent_nouns.py`)
   - Extracts frequent nouns from OpenSubtitles word frequency data
   - Uses Stanford Stanza POS tagger to identify nouns
   - Generates `frequent_nouns/{lang}_nouns.csv` files

2. **Relation Extraction** (`taboo_extract_relations_from_conceptnet.py`)
   - Loads frequent nouns from CSV files
   - Merges with nouns from Universal Dependencies treebanks
   - Queries ConceptNet 5.7 for semantic relations
   - Selects 3 related words per target using multiple relation types:
     - `/r/RelatedTo` - General semantic relatedness
     - `/r/Synonym` - Synonyms
     - `/r/IsA` - Category membership
     - `/r/HasA` - Part-whole relations
     - `/r/PartOf` - Whole-part relations
     - `/r/UsedFor` - Purpose/function
     - `/r/CapableOf` - Capabilities
     - `/r/Antonym` - Opposites
     - `/r/DerivedFrom` - Word origins
     - `/r/SimilarTo` - Similarity
     - `/r/MadeOf` - Material composition
   - Samples highest-weight words from different relations
   - Generates final JSON files in `resources/{lang}/`

### Manual Curation (3 languages)

**Arabic (ar), Maltese (mt), and Croatian (hr)** were curated manually using **Google Gemini** due to insufficient data coverage in ConceptNet for these languages. The automated scripts did not deliver adequate results, so human curation with AI assistance was employed to ensure quality word lists.

## Quality Criteria

For all languages, the following quality criteria are applied:

1. **Single Words**: Only single-word entries (no phrases) for languages with space-based tokenization
2. **Length Constraints**: Words must meet language-specific minimum and maximum length requirements
3. **Frequency-Based**: Target words are ordered by frequency (most common first)
4. **Semantic Diversity**: Related words are sampled from different relation types to ensure variety
5. **Relation Strength**: Words with higher ConceptNet weights are prioritized

## Language-Specific Settings

Different languages have specific configuration parameters:

| Language | Lowercase | Min Length | Max Length | Single Word Check |
|----------|-----------|------------|------------|-------------------|
| Arabic (ar) | Yes | 2 | 10 | No |
| Urdu (ur) | Yes | 3 | 10 | No |
| German (de) | No | 4 | 12 | Yes |
| English (en) | Yes | 3 | 8 | Yes |
| Others | Yes | 3 | 10-12 | Yes |

*Note: Arabic and Urdu don't use single-word check because they don't rely on space-based tokenization.*

## Data Sources

1. **OpenSubtitles Frequency Data**: Real-world word usage frequencies from movie/TV subtitles
2. **Universal Dependencies v2.17**: Linguistic annotations for part-of-speech information
3. **ConceptNet 5.7**: Multilingual semantic knowledge graph for word relations
4. **Google Gemini**: AI-assisted curation for Arabic, Maltese, and Croatian

## Usage

To use these word lists in a Taboo game application:

1. Load the appropriate JSON file based on language and difficulty level
2. Randomly select entries from the array
3. Present the `target_word` to the player who must describe it
4. Show the `related_word` array to other players who must ensure these words are not used

## Regeneration

To regenerate the word lists (for supported languages):

```bash
# Step 1: Extract frequent nouns (if needed)
cd taboo
python3 taboo_extract_frequent_nouns.py

# Step 2: Generate taboo word lists from ConceptNet
python3 taboo_extract_relations_from_conceptnet.py
```

Note: Regeneration requires:
- ConceptNet 5.7 assertions file (`conceptnet-assertions-5.7.0.csv.gz`)
- Universal Dependencies v2.17 treebanks (`ud-treebanks-v2.17.tgz`)
- Stanford Stanza models (auto-downloaded on first run)

## Contributing

If you notice issues with specific word lists or have suggestions for improvements, please contribute by:
1. Reporting issues with specific language word pairs
2. Suggesting additional semantic relations to consider
3. Providing feedback on word quality and gameplay experience
