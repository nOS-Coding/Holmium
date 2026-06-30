#!/bin/bash
set -e

cd "$(dirname "$0")/.."

echo "============================================"
echo "  Holmium Test Suite"
echo "============================================"

PASS=0
FAIL=0
FAILED_TESTS=""

run_test() {
    local name=$1
    local path=$2
    echo ""
    echo "--- $name ---"
    if python -m pytest "$path" -v --tb=short 2>&1; then
        echo "✓ $name PASSED"
        PASS=$((PASS + 1))
    else
        echo "✗ $name FAILED"
        FAIL=$((FAIL + 1))
        FAILED_TESTS="$FAILED_TESTS $name"
    fi
    echo ""
}

run_test "Tools" "tests/test_tools.py"
run_test "Memory" "tests/test_memory.py"
run_test "API" "tests/test_api.py"
run_test "Streaming" "tests/test_streaming.py"
run_test "Tool Parser" "tests/test_tool_parser.py"
run_test "Config" "tests/test_config.py"

echo "============================================"
echo "  Results: $PASS passed, $FAIL failed"
echo "============================================"

if [ "$FAIL" -gt 0 ]; then
    echo ""
    echo "Failed tests:$FAILED_TESTS"
    exit 1
fi

exit 0
