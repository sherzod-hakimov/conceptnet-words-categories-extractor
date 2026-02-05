#!/usr/bin/env bash
set -euo pipefail

DEFAULT_LANGS=(
  bg hr cs da nl en et fi fr de el hu ga it lv lt mt pl pt ro sk sl es sv ru tr
)

if [[ $# -ge 1 ]]; then
  LANGS=("$@")
else
  LANGS=("${DEFAULT_LANGS[@]}")
fi

run_one() {
  local lang_code="$1"
  local dic_path="${lang_code}.dic"
  local aff_path="${lang_code}.aff"
  local output_path="resources/${lang_code}/allowed_words.txt"

  if [[ ! -f "$dic_path" || ! -f "$aff_path" ]]; then
    echo "Skipping ${lang_code}: missing ${dic_path} or ${aff_path}" >&2
    return 0
  fi

  mkdir -p "$(dirname "$output_path")"

  LC_ALL=C unmunch "$dic_path" "$aff_path" \
    | grep -E '^[[:alpha:]]{5}$' \
    | tr '[:upper:]' '[:lower:]' \
    | sort -u \
    > "$output_path"

  echo "Saved ${lang_code} to ${output_path}"
}

for lang in "${LANGS[@]}"; do
  run_one "$lang"
done
