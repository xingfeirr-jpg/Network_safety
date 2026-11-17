#!/usr/bin/env bash
# Record one complete command. Tool output and GNU time output stay separate.
set -euo pipefail
if [[ $# -lt 4 || $3 != -- ]]; then
    printf 'Usage: bash measure_run.sh RUN_ID NEW_OUTPUT_DIR -- COMMAND [ARGS...]\n' >&2
    exit 64
fi
run_id=$1
output=$2
shift 3
if [[ $run_id =~ ^PRE-P[0-9]{2}-(FF|CP|CC)-[0-9]{3}$ ]]; then
    purpose=pretest
elif [[ $run_id =~ ^FORM-P[0-9]{2}-(FF|CP|CC)-[0-9]{3}$ ]]; then
    purpose=formal
elif [[ $run_id =~ ^CHECK-HELPER-[0-9]{3}$ ]]; then
    purpose=helper_validation
else
    printf 'Unsupported run ID: %s\n' "$run_id" >&2
    exit 64
fi
[[ -x /usr/bin/time ]] || { printf '/usr/bin/time is unavailable\n' >&2; exit 69; }
mkdir -p -- "$(dirname -- "$output")"
if ! mkdir -- "$output"; then
    printf 'Output must be a new directory; existing evidence was retained: %s\n' "$output" >&2
    exit 73
fi
output=$(cd "$output" && pwd)
mkdir -- "$output/cache"
printf '%q ' "$@" > "$output/command.txt"
printf '\n' >> "$output/command.txt"
{
    printf 'measurement_schema\tmeasurement-v1\nrun_id\t%s\npurpose\t%s\n' "$run_id" "$purpose"
    printf 'working_directory\t%s\nlocale\tC\n' "$PWD"
    printf 'application_cache_policy\trequired_fresh_tool_cache\nos_page_cache\tnatural_not_cleared\n'
    printf 'created_empty_cache_directory\t%s/cache\n' "$output"
    printf 'started_utc\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "$output/run-meta.tsv"
{
    date -u +%Y-%m-%dT%H:%M:%SZ
    uname -a
    printf 'nproc='; nproc
    printf 'online_processors='; getconf _NPROCESSORS_ONLN
    cat /proc/meminfo
    cat /proc/loadavg
    printf '\nInherited shell limits:\n'; ulimit -a
} > "$output/environment-start.txt"
# The if preserves a nonzero exit/signal from the timed command under set -e.
if LC_ALL=C /usr/bin/time -v -o "$output/time.txt" -- "$@" \
    > "$output/stdout.txt" 2> "$output/stderr.txt"; then
    command_status=0
else
    command_status=$?
fi
printf '%s\n' "$command_status" > "$output/exit-code.txt"
{
    printf 'ended_utc\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf 'timed_invocation_exit_code\t%s\n' "$command_status"
    printf 'coverage_validation\tpending_tool_output_review\n'
} >> "$output/run-meta.tsv"
printf 'Recorded %s, exit=%s, directory=%s\n' "$run_id" "$command_status" "$output"
exit "$command_status"
