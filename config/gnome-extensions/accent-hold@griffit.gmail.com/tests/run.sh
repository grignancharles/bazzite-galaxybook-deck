#!/usr/bin/env bash
# Run every gjs unit test: extension/tests/run.sh
set -u
cd "$(dirname "$0")"
status=0
for t in *.test.js; do
    echo "== $t"
    gjs -m "$t" || status=1
done
exit $status
