#!/bin/sh
# Final DEV/PROD submission steps with the FROZEN configuration in tools/production.env.
# Paid steps refuse to run unless CQA_PAID_OK=yes (set only after explicit owner approval).
# Usage (from the repository root):
#   sh tools/final_submission.sh check                      # config freeze + offline readiness, no network
#   CQA_PAID_OK=yes ENV_FILE=../.env sh tools/final_submission.sh dev-batch      # 60 synthetic chats; 5 calls -> errors
#   CONTROL_URL=... sh tools/final_submission.sh prod-fetch  # exact bytes -> data/raw/PROD_control.json
#   sh tools/final_submission.sh prod-check                  # structure only, expects 10
#   PERMISSION_REF='<organizer rule ref>' sh tools/final_submission.sh prod-grants
#   CQA_PAID_OK=yes ENV_FILE=../.env sh tools/final_submission.sh prod-batch
#   CQA_PAID_OK=yes ENV_FILE=../.env sh tools/final_submission.sh resume dev|prod RUN_DIR   # one retry of non-accepted
#   TEAM_NAME='<registered name>' sh tools/final_submission.sh export dev|prod RUN_DIR      # results/<set>/results.json
#   sh tools/final_submission.sh export dev|prod RUN_DIR    # without TEAM_NAME: validation copy under the run dir
#   TEAM_NAME=... SUBMIT_REPO=owner/repo SUBMIT_REF=branch sh tools/final_submission.sh submit   # commit+push results only
#   SUBMIT_REPO=... SUBMIT_REF=... sh tools/final_submission.sh verify dev|prod
set -eu
cd "$(dirname "$0")/.."
. tools/production.env
export PYTHONPATH=src
DEV_DATA=data/raw/DEV_conversations.json
PROD_RAW=data/raw/PROD_control.json
PROD_GRANTS=restricted/prod-approvals.json

die() { echo "STOP: $*" >&2; exit 1; }
paid() { [ "${CQA_PAID_OK:-}" = "yes" ] || die "paid step: set CQA_PAID_OK=yes only after explicit owner approval"; : "${ENV_FILE:?set ENV_FILE to the ignored .env holding OPENAI_API_KEY}"; }
freeze() {
  [ "$(shasum -a 256 "$CQA_CHECKLIST" | cut -d' ' -f1)" = "$CQA_CHECKLIST_SHA256" ] || die "checklist changed; configuration is frozen"
  python3 -B -c "
from cqa.prompt import build_request; from cqa.io import load_checklist; from cqa.loader import load_conversation, SHARED; from pathlib import Path
_,s=build_request(load_conversation(SHARED,'p1-ru-001'),load_checklist(Path('$CQA_CHECKLIST')),prompt_version='$CQA_PROMPT_VERSION')
assert s=='$CQA_PROMPT_SHA256_P1_RU_001', 'prompt bytes changed; configuration is frozen'" || die "prompt freeze check failed"
}
prod_data() { if [ -f data/raw/PROD_control_envelope.json ]; then echo data/raw/PROD_control_envelope.json; else echo "$PROD_RAW"; fi; }
batch() { # $1 data, $2 run dir, $3.. extra flags
  data=$1; run=$2; shift 2
  python3 -B -m cqa_results.batch --data "$data" --run-dir "$run" --provider openai --model "$CQA_MODEL" \
    --env-file "$ENV_FILE" --checklist "$CQA_CHECKLIST" --prompt-version "$CQA_PROMPT_VERSION" \
    --evidence-gate "$CQA_EVIDENCE_GATE" --repair-authorization "$CQA_REPAIR_REF" --quote-policy "$CQA_QUOTE_POLICY" \
    --max-output-tokens "$CQA_MAX_OUTPUT_TOKENS" --timeout-seconds "$CQA_TIMEOUT_SECONDS" --workers "$CQA_WORKERS" "$@"
}
case "${1:-}" in
  check)
    freeze
    python3 -B -c "from cqa.io import load_checklist; from pathlib import Path; from cqa_results.export import check_checklist; check_checklist(load_checklist(Path('$CQA_CHECKLIST')))"
    [ -f "$DEV_DATA" ] && python3 -B -m cqa_results.envelope check "$DEV_DATA" --expect-count 65 >/dev/null && echo "DEV-65 present and well-formed" || echo "DEV-65 raw file missing (needed for dev-batch/export)"
    for f in data/raw/x.json restricted/x.json outputs/x .env; do git check-ignore -q --no-index "$f" || die "ignore rule missing for $f"; done
    for f in results/dev/results.json results/prod/results.json; do git check-ignore -q --no-index "$f" && die "$f would be ignored"; done
    echo "Frozen configuration verified: $CQA_CHECKLIST + $CQA_PROMPT_VERSION + gate=$CQA_EVIDENCE_GATE + $CQA_MODEL" ;;
  dev-batch)
    paid; freeze
    run=outputs/submission/dev-final-$(date +%Y%m%d-%H%M%S)
    # No grants manifest: only the 60 reviewed synthetic chats may leave the machine; the 5 calls become errors.
    batch "$DEV_DATA" "$run" --allow-external-synthetic --expect-count 65 --live-call-limit 65
    echo "Run directory: $run" ;;
  prod-fetch)
    : "${CONTROL_URL:?export CONTROL_URL (read -rs CONTROL_URL; export CONTROL_URL)}"
    python3 -B -m cqa_results.envelope fetch --url-env CONTROL_URL --out "$PROD_RAW" ${CONTROL_AUTH:+--header-env CONTROL_AUTH} ;;
  prod-check)
    python3 -B -m cqa_results.envelope check "$(prod_data)" --expect-count 10 ;;
  prod-grants)
    : "${PERMISSION_REF:?set PERMISSION_REF to the organizer rule/permission reference (no URL/token)}"
    python3 -B -m cqa_results.grants --data "$(prod_data)" --data-class organizer_control --reference "$PERMISSION_REF" \
      --external openai --expires "$(date -u -v+2d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '+2 days' +%Y-%m-%dT%H:%M:%SZ)" --output "$PROD_GRANTS" ;;
  prod-batch)
    paid; freeze
    [ -f "$PROD_GRANTS" ] || die "no $PROD_GRANTS: run prod-grants after confirming organizer permission"
    run=outputs/submission/prod-final-$(date +%Y%m%d-%H%M%S)
    batch "$(prod_data)" "$run" --authorization-manifest "$PROD_GRANTS" --allow-external-authorized \
      --expect-count 10 --live-call-limit 10
    echo "Run directory: $run" ;;
  resume)
    paid; freeze
    set_name=${2:?dev|prod}; run=${3:?RUN_DIR}
    if [ "$set_name" = dev ]; then batch "$DEV_DATA" "$run" --allow-external-synthetic --expect-count 65 --live-call-limit 65 --resume
    else batch "$(prod_data)" "$run" --authorization-manifest "$PROD_GRANTS" --allow-external-authorized --expect-count 10 --live-call-limit 10 --resume; fi ;;
  export)
    set_name=${2:?dev|prod}; run=${3:?RUN_DIR}
    data=$DEV_DATA; [ "$set_name" = prod ] && data=$(prod_data)
    if [ -n "${TEAM_NAME:-}" ]; then
      python3 -B -c "
import re,sys; from cqa_results.contract import PLACEHOLDERS
t=sys.argv[1]
bad = t.strip() in PLACEHOLDERS or t != t.strip() or re.search(r'(?i)pending|placeholder|\\btbd\\b|\\btodo\\b|dry.?run|rehearsal|wiring|not a submission|[<>]', t)
sys.exit(1 if bad else 0)" "$TEAM_NAME" || die "TEAM_NAME looks like a placeholder; nothing written"
      python3 -B -c "
import json,sys; m=json.load(open(sys.argv[1]+'/run.json')); c=m['configuration']
want={'checklist_version':'2026-11-07.v7','model_requested':sys.argv[2],'provider':'openai'}
bad=[k for k,v in want.items() if m.get(k)!=v]
if c.get('prompt_version')!=sys.argv[3]: bad.append('prompt_version')
if c.get('evidence_gate','strict')!=sys.argv[4]: bad.append('evidence_gate')
sys.exit('run is not the frozen production configuration: '+', '.join(bad) if bad else 0)" "$run" "$CQA_MODEL" "$CQA_PROMPT_VERSION" "$CQA_EVIDENCE_GATE" \
        || die "official results come only from runs made with tools/production.env"
      out=results/$set_name/results.json
      python3 -B -m cqa_results.export --set "$set_name" --data "$data" --run-dir "$run" --team-name "$TEAM_NAME" \
        --output "$out" ${OVERWRITE:+--overwrite} ${UNATTEMPTED_REASON:+--unattempted-reason "$UNATTEMPTED_REASON"}
      python3 -B -m cqa_results.validate "$out" --set "$set_name" --dataset "$data" --team-name "$TEAM_NAME" --submission
    else
      out=$run-export/results.json
      echo "TEAM_NAME not set: writing a validation copy to $out (never submitted)"
      python3 -B -m cqa_results.export --set "$set_name" --data "$data" --run-dir "$run" --team-name "UNSET TEAM NAME (not a submission)" \
        --output "$out" --overwrite ${UNATTEMPTED_REASON:+--unattempted-reason "$UNATTEMPTED_REASON"}
      python3 -B -m cqa_results.validate "$out" --set "$set_name" --dataset "$data"
    fi ;;
  submit)
    : "${TEAM_NAME:?}"; : "${SUBMIT_REPO:?owner/repo}"; : "${SUBMIT_REF:?branch in the URL given to organizers}"
    [ "$(git rev-parse --abbrev-ref HEAD)" = "$SUBMIT_REF" ] || die "check out $SUBMIT_REF itself; pushing another branch onto it is refused"
    git fetch origin "$SUBMIT_REF"
    [ "$(git rev-parse HEAD)" = "$(git rev-parse "origin/$SUBMIT_REF")" ] || die "local $SUBMIT_REF differs from origin; inspect, never force"
    files=""
    for s in dev prod; do
      [ -f "results/$s/results.json" ] || continue
      data=$DEV_DATA; [ "$s" = prod ] && data=$(prod_data)
      python3 -B -m cqa_results.validate "results/$s/results.json" --set "$s" --dataset "$data" --team-name "$TEAM_NAME" --submission >/dev/null \
        || die "results/$s/results.json fails submission validation"
      files="$files results/$s/results.json"
    done
    [ -n "$files" ] || die "no results files"
    [ -z "$(git diff --cached --name-only)" ] || die "something is already staged; unstage it first"
    # shellcheck disable=SC2086
    git add -- $files
    staged=$(git diff --cached --name-only | sort | tr '\n' ' ')
    expected=$(for f in $files; do echo "$f"; done | sort | tr '\n' ' ')
    [ "$staged" = "$expected" ] || { git reset -q; die "staged set differs from results files: $staged"; }
    git commit -q -m "Submit CQA results ($(echo $files | sed 's#results/##g; s#/results.json##g'))"
    git push origin "$SUBMIT_REF"
    echo "Pushed. Now run: sh tools/final_submission.sh verify dev|prod" ;;
  verify)
    set_name=${2:?dev|prod}; data=$DEV_DATA; [ "$set_name" = prod ] && data=$(prod_data)
    python3 -B -m cqa_results.verify_remote --repo "${SUBMIT_REPO:?}" --ref "${SUBMIT_REF:?}" --set "$set_name" --dataset "$data" ;;
  *) sed -n 2,20p "$0"; exit 2 ;;
esac
