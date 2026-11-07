#!/bin/sh
# Paired v6 vs v7 C01 comparison. MAKES PAID OPENAI CALLS: 34 at most (17 conversations x 2 arms),
# ~USD 0.6-0.8. Requires explicit owner approval: run only with CQA_C01_PAID_OK=yes.
# No repair, strict gate, synthetic/fictional data only; the 5 real DEV calls are never included.
#
# Conversations (fixed rule, chosen before any v7 call):
#   - 8 invented cases in docs/demo/c01_variants_fictional.json (4 Yes / 4 No by construction, RU/KZ/EN)
#   - DEV genuine No (all 3): p1-ru-014 p1-kz-008 p1-en-015
#   - DEV Yes previously judged No by v6 (last ID per language): p1-ru-024 p1-kz-013 p1-en-012
#   - DEV Yes previously judged Yes by v6 (last ID per language): p1-ru-030 p1-kz-015 p1-en-014
# Pre-registered success criteria for adopting v7 (small n: directional evidence only):
#   1. Fictional: v7 C01 correct on >= 7/8 and NO false Yes on the 4 constructed No cases.
#   2. DEV genuine No: v7 keeps all 3 as No.
#   3. DEV previously-wrong Yes: v7 fixes >= 2/3.
#   4. DEV previously-right Yes: no v7 regression (3/3 Yes).
#   5. v7 structural acceptance not lower than v6 by more than 2 conversations.
set -eu
[ "${CQA_C01_PAID_OK:-}" = "yes" ] || { echo "Refusing: set CQA_C01_PAID_OK=yes only after owner approval"; exit 2; }
: "${CQA_MODEL:?set CQA_MODEL (e.g. gpt-5.4-mini-2026-03-17)}"
: "${ENV_FILE:?set ENV_FILE to the ignored .env with OPENAI_API_KEY}"
OUT=outputs/c01-compare/$(date +%Y%m%d-%H%M%S)
DEV="p1-ru-014 p1-kz-008 p1-en-015 p1-ru-024 p1-kz-013 p1-en-012 p1-ru-030 p1-kz-015 p1-en-014"
mkdir -p restricted
GRANTS=restricted/c01-fictional-approvals.json
[ -f "$GRANTS" ] || PYTHONPATH=src python3 -B -m cqa_results.grants --data docs/demo/c01_variants_fictional.json \
  --data-class synthetic_test --reference c01-fictional-comparison --external openai \
  --expires 2030-01-01T00:00:00Z --output "$GRANTS"
for ARM in v6 v7; do
  PYTHONPATH=src python3 -B -m cqa_results.batch --data docs/demo/c01_variants_fictional.json \
    --run-dir "$OUT/$ARM-fict" --provider openai --model "$CQA_MODEL" --env-file "$ENV_FILE" \
    --checklist "src/cqa/checklists/official-$ARM.json" --prompt-version atomic-v5 \
    --authorization-manifest "$GRANTS" --allow-external-authorized --expect-count 8 --workers 4 --live-call-limit 8
  # shellcheck disable=SC2086
  PYTHONPATH=src python3 -B -m cqa_results.batch --data data/shared/DEV_synthetic_60.json \
    --run-dir "$OUT/$ARM-dev" --provider openai --model "$CQA_MODEL" --env-file "$ENV_FILE" \
    --checklist "src/cqa/checklists/official-$ARM.json" --prompt-version atomic-v5 \
    --allow-external-synthetic --only $DEV --workers 4 --live-call-limit 9
done
PYTHONPATH=src python3 -B tools/c01_compare.py --data docs/demo/c01_variants_fictional.json \
  --data data/shared/DEV_synthetic_60.json --expectations tests/fixtures/c01_fictional_expectations.json \
  --run "v6=$OUT/v6-fict,$OUT/v6-dev" --run "v7=$OUT/v7-fict,$OUT/v7-dev" --json "$OUT/c01-report.json"
echo "Report: $OUT/c01-report.json"
