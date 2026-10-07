#!/usr/bin/env bash
# ci_watch.sh : run beside the CI test suite. Every two minutes, remove the
# build cache of sources whose directory is gone, and every ten log disk and
# memory use.
#
# A program compiled from a test's temporary directory is cached under
# `__dewycache__/__external__/<hash>/<tail>`, where on the runner `<tail>` is
# the source's absolute path (the checkout and /tmp share only `/`). A test
# that builds a native driver leaves about 300 MB there. Once pytest removes
# a passing test's directory (`tmp_path_retention_policy=failed`), nothing
# reads that cache again.
set -u
external=__dewycache__/__external__
round=0
while sleep 120; do
    if [[ -d $external ]]; then
        for entry in "$external"/*/; do
            file=$(find "$entry" -type f -print -quit 2>/dev/null)
            [[ -n $file ]] || continue
            source_dir=$(dirname "/${file#"$entry"}")
            [[ -d $source_dir ]] || rm -rf "$entry"
        done
    fi
    if (( round % 5 == 0 )); then
        echo "resources: disk $(df -h --output=used,avail / | tail -1 | xargs) (used, available);" \
            "memory $(free -m | awk '/Mem:/ {print $3 " MB used, " $7 " MB available"}');" \
            "cache $(du -sh __dewycache__ 2>/dev/null | cut -f1)"
    fi
    round=$((round + 1))
done
