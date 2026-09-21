#!/usr/bin/env bash
# Archives the ROM/.sym/.custom_pointer.txt from the current build into
# backups/<commit>[-dirty]/, so a broken build can be bisected without a full
# rebuild of every candidate commit. Run after every `make sync-win`; each
# call overwrites the files for the current HEAD, and checking out a
# different commit starts a fresh folder.
set -euo pipefail

usage() {
    echo "usage: $0 <rom> <sym> [custom_pointer_txt]" >&2
    exit 1
}

[ $# -ge 2 ] || usage

rom="$1"
sym="$2"
custom_pointer="${3:-}"

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

commit_hash="$(git rev-parse --short=12 HEAD 2>/dev/null || echo nogit)"
dirty=""
if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
    dirty="-dirty"
fi

dest="backups/${commit_hash}${dirty}"
mkdir -p "$dest"

cp "$rom" "$dest/"
cp "$sym" "$dest/"
if [ -n "$custom_pointer" ] && [ -f "$custom_pointer" ]; then
    cp "$custom_pointer" "$dest/"
fi

{
    printf 'commit:  %s\n' "$(git rev-parse HEAD)"
    printf 'subject: %s\n' "$(git log -1 --format=%s HEAD)"
    printf 'author:  %s\n' "$(git log -1 --format='%an <%ae>' HEAD)"
    printf 'date:    %s\n' "$(git log -1 --format=%ai HEAD)"
    printf 'branch:  %s\n' "$(git rev-parse --abbrev-ref HEAD)"
    printf 'built:   %s\n' "$(date -Iseconds)"
    if [ -n "$dirty" ]; then
        printf '\nWARNING: built with uncommitted local changes:\n'
        git status --porcelain
    fi
    printf '\nrecent history:\n'
    git log -5 --format='  %h %s' HEAD
} > "$dest/info.txt"

printf '[backup] %s, %s%s -> %s/\n' "$(basename "$rom")" "$(basename "$sym")" \
    "$([ -n "$custom_pointer" ] && [ -f "$custom_pointer" ] && printf ', %s' "$(basename "$custom_pointer")")" \
    "$dest"
