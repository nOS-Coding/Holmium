import pytest
import json
import tempfile
import os
from unittest.mock import patch, MagicMock, AsyncMock

from tools.registry import ToolRegistry
from tools.executor import ToolExecutor
from tools.parser import ToolParser
from tools.file_ops import FileOpsTool
from tools.shell import ShellTool
from tools.app_control import AppControlTool
from tools.remote import RemoteTool
from tools.monitor import MonitorTool


@pytest.fixture
def registry():
    r = ToolRegistry()
    r.register(FileOpsTool())
    r.register(ShellTool())
    r.register(AppControlTool())
    r.register(RemoteTool())
    r.register(MonitorTool())
    return r


@pytest.fixture
def executor(registry):
    return ToolExecutor(registry)


@pytest.fixture
def parser():
    return ToolParser()


class TestFileOpsTool:
    def test_file_read_write(self):
        tool = FileOpsTool()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test.txt")
            result = tool.execute("file_write", {"path": path, "content": "hello world"})
            assert result["success"] is True

            result = tool.execute("file_read", {"path": path})
            assert result["content"] == "hello world"

    def test_file_delete(self):
        tool = FileOpsTool()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "delete_me.txt")
            with open(path, "w") as f:
                f.write("test")
            result = tool.execute("file_delete", {"path": path})
            assert result["success"] is True
            assert not os.path.exists(path)

    def test_file_exists(self):
        tool = FileOpsTool()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "exists.txt")
            assert tool.execute("file_exists", {"path": path})["exists"] is False
            with open(path, "w") as f:
                f.write("test")
            assert tool.execute("file_exists", {"path": path})["exists"] is True

    def test_file_list(self):
        tool = FileOpsTool()
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(3):
                with open(os.path.join(tmp, f"file{i}.txt"), "w") as f:
                    f.write(f"content{i}")
            result = tool.execute("file_list", {"path": tmp})
            assert result["success"] is True
            assert len(result["entries"]) == 3

    def test_file_move(self):
        tool = FileOpsTool()
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "src.txt")
            dst = os.path.join(tmp, "dst.txt")
            with open(src, "w") as f:
                f.write("move me")
            result = tool.execute("file_move", {"src": src, "dst": dst})
            assert result["success"] is True
            assert os.path.exists(dst)
            assert not os.path.exists(src)


class TestShellTool:
    def test_shell_run(self):
        tool = ShellTool()
        result = tool.execute("shell_run", {"command": "echo hello", "timeout": 10})
        assert result["exit_code"] == 0
        assert "hello" in result["stdout"]

    def test_shell_run_failure(self):
        tool = ShellTool()
        result = tool.execute("shell_run", {"command": "exit 42", "timeout": 10})
        assert result["exit_code"] == 42

    def test_shell_run_timeout(self):
        tool = ShellTool()
        result = tool.execute("shell_run", {"command": "sleep 10", "timeout": 1})
        assert result["exit_code"] == -1
        assert "timeout" in result["stderr"].lower()

    def test_shell_run_background(self):
        tool = ShellTool()
        result = tool.execute("shell_run_background", {"command": "sleep 5"})
        assert result["success"] is True
        assert "pid" in result


class TestAppControlTool:
    @patch("tools.app_control.psutil")
    def test_process_list(self, mock_psutil):
        mock_process = MagicMock()
        mock_process.info = {
            "pid": 1234,
            "name": "python3",
            "cpu_percent": 2.5,
            "memory_percent": 1.0,
        }
        mock_psutil.process_iter.return_value = [mock_process]
        tool = AppControlTool()
        result = tool.execute("process_list", {})
        assert result["success"] is True
        assert len(result["processes"]) == 1

    @patch("tools.app_control.psutil")
    def test_process_kill_by_pid(self, mock_psutil):
        mock_proc = MagicMock()
        mock_psutil.Process.return_value = mock_proc
        tool = AppControlTool()
        result = tool.execute("process_kill", {"pid_or_name": "9999"})
        assert result["success"] is True

    def test_process_start(self):
        tool = AppControlTool()
        result = tool.execute("process_start", {"command": "sleep 10"})
        assert result["success"] is True

    def test_process_status(self):
        tool = AppControlTool()
        result = tool.execute("process_status", {"pid": os.getpid()})
        assert result["running"] is True


class TestRemoteTool:
    def test_remote_device_not_found(self):
        tool = RemoteTool()
        with patch.object(tool, "devices", {"mac": {"ip": "10.0.0.2", "token": "abc"}}):
            result = tool.execute("remote_shell", {"device": "nonexistent", "command": "echo hi"})
            assert result["success"] is False

    def test_remote_shell(self):
        tool = RemoteTool()
        with patch.object(tool, "devices", {"mac": {"ip": "10.0.0.2", "token": "abc"}}):
            with patch("tools.remote.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    stdout="hi\n", stderr="", returncode=0
                )
                result = tool.execute("remote_shell", {"device": "mac", "command": "echo hi"})
                assert result["exit_code"] == 0


class TestMonitorTool:
    def test_monitor_start_stop(self):
        tool = MonitorTool()
        result = tool.execute("monitor_start", {
            "name": "test_monitor",
            "condition": "True",
            "interval": 60
        })
        assert result["success"] is True
        assert "test_monitor" in tool.active_monitors

        result = tool.execute("monitor_list", {})
        assert "test_monitor" in str(result.get("monitors", []))

        tool.execute("monitor_stop", {"name": "test_monitor"})
        assert "test_monitor" not in tool.active_monitors

    def test_monitor_unknown_stop(self):
        tool = MonitorTool()
        result = tool.execute("monitor_stop", {"name": "does_not_exist"})
        assert result["success"] is False


class TestToolParser:
    def test_parse_single_tool_call(self):
        parser = ToolParser()
        text = 'Sure, let me check that. TOOL_CALL: {"tool": "file_read", "params": {"path": "/tmp/test.txt"}} Some more text.'
        calls = parser.parse(text)
        assert len(calls) == 1
        assert calls[0]["tool"] == "file_read"
        assert calls[0]["params"]["path"] == "/tmp/test.txt"

    def test_parse_multiple_tool_calls(self):
        parser = ToolParser()
        text = """First call TOOL_CALL: {"tool": "file_read", "params": {"path": "/a.txt"}}
Second call TOOL_CALL: {"tool": "shell_run", "params": {"command": "ls", "timeout": 30}}"""
        calls = parser.parse(text)
        assert len(calls) == 2

    def test_parse_malformed_json(self):
        parser = ToolParser()
        text = 'TOOL_CALL: {"tool": "file_read" params: {"path": "/test.txt"}}'
        calls = parser.parse(text)
        assert len(calls) == 0

    def test_parse_no_tool_call(self):
        parser = ToolParser()
        calls = parser.parse("Just a normal response with no tool calls.")
        assert len(calls) == 0

    def test_parse_nested_json(self):
        parser = ToolParser()
        text = 'TOOL_CALL: {"tool": "shell_run", "params": {"command": "echo \\"hello world\\"", "timeout": 30}}'
        calls = parser.parse(text)
        assert len(calls) == 1

    def test_parse_max_depth(self):
        parser = ToolParser(max_calls=3)
        text = "TOOL_CALL: {} TOOL_CALL: {} TOOL_CALL: {} TOOL_CALL: {}"
        for c in ["a", "b", "c", "d"]:
            text = text.replace("{}", '{"tool": "' + c + '", "params": {}}', 1)
        calls = parser.parse(text)
        assert len(calls) == 3


class TestToolExecutor:
    def test_execute_registered_tool(self, executor):
        result = executor.execute("shell_run", {"command": "echo test", "timeout": 10})
        assert "stdout" in result
        assert result["exit_code"] == 0

    def test_execute_unregistered_tool(self, executor):
        result = executor.execute("nonexistent", {})
        assert "error" in result

    def test_execute_missing_params(self, executor):
        result = executor.execute("file_read", {})
        assert "error" in result
