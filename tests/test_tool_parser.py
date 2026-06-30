import pytest
import json
from tools.parser import ToolParser


@pytest.fixture
def parser():
    return ToolParser()


class TestToolParserEdgeCases:
    def test_empty_string(self, parser):
        assert parser.parse("") == []

    def test_only_whitespace(self, parser):
        assert parser.parse("   \n  \t  ") == []

    def test_partial_prefix(self, parser):
        text = "Some text TOOL_CALL: without proper json"
        assert parser.parse(text) == []

    def test_nested_quotes_in_params(self, parser):
        text = """TOOL_CALL: {"tool": "shell_run", "params": {"command": "echo \\"hello world\\""}}"""
        calls = parser.parse(text)
        assert len(calls) == 1
        assert "hello world" in calls[0]["params"]["command"]

    def test_unicode_in_json(self, parser):
        text = 'TOOL_CALL: {"tool": "file_write", "params": {"content": "üñíçödé"}}'
        calls = parser.parse(text)
        assert len(calls) == 1
        assert calls[0]["params"]["content"] == "üñíçödé"

    def test_very_long_text(self, parser):
        text = "A" * 10000 + ' TOOL_CALL: {"tool": "test", "params": {}}'
        calls = parser.parse(text)
        assert len(calls) == 1

    def test_malformed_json_close_but_wrong(self, parser):
        text = 'TOOL_CALL: {tool: "test", params: {}}'
        calls = parser.parse(text)
        assert len(calls) == 0

    def test_extra_brackets(self, parser):
        text = 'TOOL_CALL: {"tool": "a", "params": {"nested": {"deep": true}}}'
        calls = parser.parse(text)
        assert len(calls) == 1
        assert calls[0]["params"]["nested"]["deep"] is True

    def test_tool_call_at_start(self, parser):
        text = 'TOOL_CALL: {"tool": "first", "params": {}} and then some text'
        calls = parser.parse(text)
        assert len(calls) == 1

    def test_tool_call_at_end(self, parser):
        text = 'Some text at the end TOOL_CALL: {"tool": "last", "params": {}}'
        calls = parser.parse(text)
        assert len(calls) == 1

    def test_adjacent_tool_calls(self, parser):
        text = 'TOOL_CALL: {"tool": "a", "params": {}}TOOL_CALL: {"tool": "b", "params": {}}'
        calls = parser.parse(text)
        assert len(calls) == 2

    def test_tool_call_with_array_params(self, parser):
        text = 'TOOL_CALL: {"tool": "test", "params": {"items": [1, 2, 3]}}'
        calls = parser.parse(text)
        assert len(calls) == 1
        assert calls[0]["params"]["items"] == [1, 2, 3]

    def test_tool_call_with_null_params(self, parser):
        text = 'TOOL_CALL: {"tool": "test", "params": null}'
        calls = parser.parse(text)
        assert len(calls) == 1

    def test_newlines_between_tool_calls(self, parser):
        text = 'TOOL_CALL: {"tool": "a", "params": {}}\n\nTOOL_CALL: {"tool": "b", "params": {}}'
        calls = parser.parse(text)
        assert len(calls) == 2

    def test_tool_result_pattern_not_confused(self, parser):
        text = 'TOOL_RESULT: {"success": true} TOOL_CALL: {"tool": "test", "params": {}}'
        calls = parser.parse(text)
        assert len(calls) == 1

    def test_tool_call_in_code_block(self, parser):
        text = """Here is a code block:
```python
# TOOL_CALL: {"tool": "test", "params": {}}
print("hi")
```
And then TOOL_CALL: {"tool": "real", "params": {}}"""
        calls = parser.parse(text)
        assert len(calls) == 1

    def test_extreme_nesting(self, parser):
        deep = {"key": "value"}
        for _ in range(50):
            deep = {"nested": deep}
        text = f'TOOL_CALL: {{"tool": "deep", "params": {json.dumps(deep)}}}'
        calls = parser.parse(text)
        # Deep nesting may fail, but should not crash
        assert len(calls) <= 1

    def test_zero_width_chars(self, parser):
        text = 'TOOL_CALL:\u200B{"tool": "test", "params": {}}'
        calls = parser.parse(text)
        assert len(calls) == 0

    def test_exceed_max_calls(self, parser):
        parser.max_calls = 2
        text = 'TOOL_CALL: {"tool": "a", "params": {}} TOOL_CALL: {"tool": "b", "params": {}} TOOL_CALL: {"tool": "c", "params": {}}'
        calls = parser.parse(text)
        assert len(calls) == 2
