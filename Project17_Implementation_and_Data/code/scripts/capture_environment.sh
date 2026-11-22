#!/usr/bin/env bash
# Read-only system queries, saved to a new session directory.
set -euo pipefail
if [[ $# -ne 1 ]]; then
    printf 'Usage: bash capture_environment.sh NEW_SESSION_DIRECTORY\n' >&2
    exit 64
fi
output=$1
[[ -x /usr/bin/time ]] || { printf '/usr/bin/time is unavailable\n' >&2; exit 69; }
mkdir -p -- "$(dirname -- "$output")"
if ! mkdir -- "$output"; then
    printf 'Session directory already exists or cannot be created: %s\n' "$output" >&2
    exit 73
fi
output=$(cd "$output" && pwd)
{
    printf 'Recorded UTC: '; date -u +%Y-%m-%dT%H:%M:%SZ
    printf 'Working directory: %s\n' "$PWD"
    printf '\nOS release:\n'; cat /etc/os-release
    printf '\nKernel:\n'; uname -a
    printf '\nCPU:\n'; LC_ALL=C lscpu
    printf '\nnproc='; nproc
    printf 'online_processors='; getconf _NPROCESSORS_ONLN
    printf '\nLinux-visible memory:\n'; cat /proc/meminfo
    printf '\nInherited limits:\n'; ulimit -a
    printf '\nDisk:\n'; df -h "$HOME/comp5355"
    printf '\nCgroup membership:\n'; cat /proc/self/cgroup
    for limit in /sys/fs/cgroup/memory.max /sys/fs/cgroup/cpu.max; do
        if [[ -r $limit ]]; then printf '%s=' "$limit"; cat "$limit"; fi
    done
} > "$output/system.txt"
LC_ALL=C /usr/bin/time --version > "$output/time-version.txt" 2>&1
dpkg-query -W time > "$output/time-package.txt" 2>&1 || true
sha256sum /usr/bin/time > "$output/time-binary.sha256"
{
    printf 'Commands are version queries, not target analysis.\n'
    for command in cmake ninja clang-18 cppcheck python flawfinder; do
        printf '\n[%s]\n' "$command"
        if command -v "$command" >/dev/null 2>&1; then "$command" --version; else printf 'NOT FOUND IN CURRENT PATH\n'; fi
    done
    printf '\n[CodeChecker]\n'
    if command -v CodeChecker >/dev/null 2>&1; then CodeChecker version; else printf 'NOT FOUND IN CURRENT PATH\n'; fi
} > "$output/tool-versions.txt" 2>&1
sha256sum "${BASH_SOURCE[0]}" "$(dirname "${BASH_SOURCE[0]}")/measure_run.sh" > "$output/recording-scripts.sha256"
printf 'Environment snapshot saved: %s\n' "$output"
printf 'Linux MemTotal/MemAvailable are WSL-visible values; Windows host data is recorded separately.\n'
