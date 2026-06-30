"""Local git operations — clone, commit, push, pull, log, diff, branch, stash, etc."""

import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from tools.registry import register_tool


def _git(*args: str, cwd: Optional[str] = None, timeout: int = 60) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            ["git", *args],
            capture_output=True, text=True, timeout=timeout,
            cwd=cwd,
        )
    except FileNotFoundError:
        raise RuntimeError("git not found on this system")


def _check_result(r: subprocess.CompletedProcess) -> Dict[str, Any]:
    if r.returncode != 0:
        return {"success": False, "error": r.stderr.strip(), "stdout": r.stdout.strip()}
    return {"success": True, "output": r.stdout.strip()}


@register_tool(
    "git_init",
    "Initialize a new git repository in a directory.",
    params_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Directory to initialize as a git repo"},
            "bare": {"type": "boolean", "description": "Create a bare repository (default false)"},
        },
        "required": ["path"],
    },
)
def git_init(path: str, bare: bool = False) -> Dict[str, Any]:
    Path(path).mkdir(parents=True, exist_ok=True)
    args = ["init"]
    if bare:
        args.append("--bare")
    args.append(path)
    return _check_result(_git(*args))


@register_tool(
    "git_clone",
    "Clone a remote repository to the local filesystem.",
    params_schema={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Remote repository URL"},
            "dest": {"type": "string", "description": "Local destination directory"},
            "branch": {"type": "string", "description": "Branch to clone (default: repo default)"},
            "depth": {"type": "integer", "description": "Shallow clone depth"},
        },
        "required": ["url", "dest"],
    },
)
def git_clone(url: str, dest: str, branch: str = "", depth: int = 0) -> Dict[str, Any]:
    args = ["clone"]
    if branch:
        args.extend(["--branch", branch])
    if depth > 0:
        args.extend(["--depth", str(depth)])
    args.extend([url, dest])
    r = _git(*args, timeout=300)
    return _check_result(r)


@register_tool(
    "git_status",
    "Show the working tree status (changed, staged, untracked files).",
    params_schema={
        "type": "object",
        "properties": {
            "repo_path": {"type": "string", "description": "Path to the git repository"},
        },
        "required": ["repo_path"],
    },
)
def git_status(repo_path: str) -> Dict[str, Any]:
    r = _git("status", "--porcelain", cwd=repo_path)
    if r.returncode != 0:
        return _check_result(r)
    lines = [ln for ln in r.stdout.strip().splitlines() if ln.strip()]
    return {"success": True, "output": "\n".join(lines), "files": lines, "count": len(lines)}


@register_tool(
    "git_add",
    "Stage file(s) for commit.",
    params_schema={
        "type": "object",
        "properties": {
            "repo_path": {"type": "string", "description": "Path to the git repository"},
            "files": {
                "type": "array",
                "items": {"type": "string"},
                "description": "File paths to stage (use ['-A'] for all)",
            },
        },
        "required": ["repo_path", "files"],
    },
)
def git_add(repo_path: str, files: List[str]) -> Dict[str, Any]:
    return _check_result(_git("add", *files, cwd=repo_path))


@register_tool(
    "git_commit",
    "Commit staged changes.",
    params_schema={
        "type": "object",
        "properties": {
            "repo_path": {"type": "string", "description": "Path to the git repository"},
            "message": {"type": "string", "description": "Commit message"},
            "all": {"type": "boolean", "description": "Auto-stage all tracked files (-a flag)"},
        },
        "required": ["repo_path", "message"],
    },
)
def git_commit(repo_path: str, message: str, stage_all: bool = False) -> Dict[str, Any]:
    args = ["commit", "-m", message]
    if stage_all:
        args.insert(1, "-a")
    return _check_result(_git(*args, cwd=repo_path))


@register_tool(
    "git_push",
    "Push local commits to a remote.",
    params_schema={
        "type": "object",
        "properties": {
            "repo_path": {"type": "string", "description": "Path to the git repository"},
            "remote": {"type": "string", "description": "Remote name (default origin)"},
            "branch": {"type": "string", "description": "Branch to push (default current branch)"},
            "force": {"type": "boolean", "description": "Force push (use with care)"},
        },
        "required": ["repo_path"],
    },
)
def git_push(repo_path: str, remote: str = "origin", branch: str = "", force: bool = False) -> Dict[str, Any]:
    args = ["push"]
    if force:
        args.append("--force")
    args.append(remote)
    if branch:
        args.append(branch)
    return _check_result(_git(*args, cwd=repo_path, timeout=120))


@register_tool(
    "git_pull",
    "Pull latest changes from a remote.",
    params_schema={
        "type": "object",
        "properties": {
            "repo_path": {"type": "string", "description": "Path to the git repository"},
            "remote": {"type": "string", "description": "Remote name (default origin)"},
            "branch": {"type": "string", "description": "Branch to pull (default current branch)"},
            "rebase": {"type": "boolean", "description": "Use rebase instead of merge"},
        },
        "required": ["repo_path"],
    },
)
def git_pull(repo_path: str, remote: str = "origin", branch: str = "", rebase: bool = False) -> Dict[str, Any]:
    args = ["pull"]
    if rebase:
        args.append("--rebase")
    args.append(remote)
    if branch:
        args.append(branch)
    return _check_result(_git(*args, cwd=repo_path, timeout=120))


@register_tool(
    "git_log",
    "Show commit history.",
    params_schema={
        "type": "object",
        "properties": {
            "repo_path": {"type": "string", "description": "Path to the git repository"},
            "limit": {"type": "integer", "description": "Max commits (default 10)"},
            "branch": {"type": "string", "description": "Branch to show (default current)"},
            "format": {
                "type": "string",
                "enum": ["oneline", "short", "full"],
                "description": "Output format",
            },
        },
        "required": ["repo_path"],
    },
)
def git_log(repo_path: str, limit: int = 10, branch: str = "", format: str = "oneline") -> Dict[str, Any]:
    fmt = {"oneline": "%h %s", "short": "%h %an %ar%n%s", "full": "%H%n%an <%ae> %ad%n%s%n%b"}[format]
    args = ["log", f"-{limit}", f"--format={fmt}"]
    if branch:
        args.append(branch)
    return _check_result(_git(*args, cwd=repo_path))


@register_tool(
    "git_diff",
    "Show changes between commits, branches, or working tree.",
    params_schema={
        "type": "object",
        "properties": {
            "repo_path": {"type": "string", "description": "Path to the git repository"},
            "staged": {"type": "boolean", "description": "Show staged (cached) diff instead of working tree"},
            "base": {"type": "string", "description": "Base ref (commit/branch, defaults to HEAD)"},
            "target": {"type": "string", "description": "Target ref (omit for working tree diff)"},
            "path": {"type": "string", "description": "Limit diff to specific file path"},
        },
        "required": ["repo_path"],
    },
)
def git_diff(repo_path: str, staged: bool = False, base: str = "", target: str = "", path: str = "") -> Dict[str, Any]:
    args = ["diff"]
    if staged:
        args.append("--cached")
    if base:
        args.append(base)
    if target:
        args.append(target)
    if path:
        args.append("--", path)
    return _check_result(_git(*args, cwd=repo_path))


@register_tool(
    "git_branch",
    "List, create, or delete branches.",
    params_schema={
        "type": "object",
        "properties": {
            "repo_path": {"type": "string", "description": "Path to the git repository"},
            "action": {
                "type": "string",
                "enum": ["list", "create", "delete"],
                "description": "Branch action",
            },
            "name": {"type": "string", "description": "Branch name (required for create/delete)"},
        },
        "required": ["repo_path", "action"],
    },
)
def git_branch(repo_path: str, action: str = "list", name: str = "") -> Dict[str, Any]:
    if action == "list":
        r = _git("branch", cwd=repo_path)
    elif action == "create":
        if not name:
            return {"success": False, "error": "Branch name required for create"}
        r = _git("branch", name, cwd=repo_path)
    elif action == "delete":
        if not name:
            return {"success": False, "error": "Branch name required for delete"}
        r = _git("branch", "-d", name, cwd=repo_path)
    else:
        return {"success": False, "error": f"Unknown action: {action}"}
    return _check_result(r)


@register_tool(
    "git_checkout",
    "Switch to a branch or restore files.",
    params_schema={
        "type": "object",
        "properties": {
            "repo_path": {"type": "string", "description": "Path to the git repository"},
            "target": {"type": "string", "description": "Branch name, commit hash, or file path to switch to"},
            "create_branch": {"type": "boolean", "description": "Create branch if it doesn't exist (-b flag)"},
        },
        "required": ["repo_path", "target"],
    },
)
def git_checkout(repo_path: str, target: str, create_branch: bool = False) -> Dict[str, Any]:
    args = ["checkout"]
    if create_branch:
        args.append("-b")
    args.append(target)
    return _check_result(_git(*args, cwd=repo_path))


@register_tool(
    "git_stash",
    "Stash changes, list stashes, or pop a stash.",
    params_schema={
        "type": "object",
        "properties": {
            "repo_path": {"type": "string", "description": "Path to the git repository"},
            "action": {
                "type": "string",
                "enum": ["push", "pop", "list", "drop", "apply"],
                "description": "Stash action",
            },
            "message": {"type": "string", "description": "Stash message (for push)"},
        },
        "required": ["repo_path", "action"],
    },
)
def git_stash(repo_path: str, action: str = "push", message: str = "") -> Dict[str, Any]:
    args = ["stash"]
    if action == "push":
        args.append("push")
        if message:
            args.extend(["-m", message])
    elif action in ("pop", "drop", "apply", "list"):
        args.append(action)
    else:
        return {"success": False, "error": f"Unknown stash action: {action}"}
    return _check_result(_git(*args, cwd=repo_path))


@register_tool(
    "git_reset",
    "Reset current HEAD or working tree.",
    params_schema={
        "type": "object",
        "properties": {
            "repo_path": {"type": "string", "description": "Path to the git repository"},
            "mode": {
                "type": "string",
                "enum": ["soft", "mixed", "hard"],
                "description": "Reset mode (default mixed)",
            },
            "ref": {"type": "string", "description": "Target ref (default HEAD)"},
        },
        "required": ["repo_path"],
    },
)
def git_reset(repo_path: str, mode: str = "mixed", ref: str = "HEAD") -> Dict[str, Any]:
    return _check_result(_git("reset", f"--{mode}", ref, cwd=repo_path))


@register_tool(
    "git_remote",
    "Manage remote repository connections.",
    params_schema={
        "type": "object",
        "properties": {
            "repo_path": {"type": "string", "description": "Path to the git repository"},
            "action": {
                "type": "string",
                "enum": ["list", "add", "remove", "set_url"],
                "description": "Remote action",
            },
            "name": {"type": "string", "description": "Remote name"},
            "url": {"type": "string", "description": "Remote URL (for add/set_url)"},
        },
        "required": ["repo_path", "action"],
    },
)
def git_remote(repo_path: str, action: str = "list", name: str = "", url: str = "") -> Dict[str, Any]:
    args = ["remote"]
    if action == "list":
        args.append("-v")
    elif action == "add":
        if not name or not url:
            return {"success": False, "error": "name and url required for add"}
        args.extend(["add", name, url])
    elif action == "remove":
        if not name:
            return {"success": False, "error": "name required for remove"}
        args.extend(["remove", name])
    elif action == "set_url":
        if not name or not url:
            return {"success": False, "error": "name and url required for set_url"}
        args.extend(["set-url", name, url])
    else:
        return {"success": False, "error": f"Unknown remote action: {action}"}
    return _check_result(_git(*args, cwd=repo_path))


@register_tool(
    "git_fetch",
    "Fetch from a remote without merging.",
    params_schema={
        "type": "object",
        "properties": {
            "repo_path": {"type": "string", "description": "Path to the git repository"},
            "remote": {"type": "string", "description": "Remote name (default origin)"},
            "prune": {"type": "boolean", "description": "Prune deleted remote refs"},
        },
        "required": ["repo_path"],
    },
)
def git_fetch(repo_path: str, remote: str = "origin", prune: bool = False) -> Dict[str, Any]:
    args = ["fetch", remote]
    if prune:
        args.append("--prune")
    return _check_result(_git(*args, cwd=repo_path, timeout=120))


@register_tool(
    "git_merge",
    "Merge a branch into the current branch.",
    params_schema={
        "type": "object",
        "properties": {
            "repo_path": {"type": "string", "description": "Path to the git repository"},
            "branch": {"type": "string", "description": "Branch to merge"},
            "no_ff": {"type": "boolean", "description": "Create a merge commit even if fast-forward possible"},
        },
        "required": ["repo_path", "branch"],
    },
)
def git_merge(repo_path: str, branch: str, no_ff: bool = False) -> Dict[str, Any]:
    args = ["merge", branch]
    if no_ff:
        args.append("--no-ff")
    return _check_result(_git(*args, cwd=repo_path))


@register_tool(
    "git_tag",
    "List, create, or delete tags.",
    params_schema={
        "type": "object",
        "properties": {
            "repo_path": {"type": "string", "description": "Path to the git repository"},
            "action": {
                "type": "string",
                "enum": ["list", "create", "delete"],
                "description": "Tag action",
            },
            "name": {"type": "string", "description": "Tag name (required for create/delete)"},
            "message": {"type": "string", "description": "Annotated tag message (for create)"},
        },
        "required": ["repo_path", "action"],
    },
)
def git_tag(repo_path: str, action: str = "list", name: str = "", message: str = "") -> Dict[str, Any]:
    if action == "list":
        r = _git("tag", "-n", cwd=repo_path)
    elif action == "create":
        if not name:
            return {"success": False, "error": "Tag name required for create"}
        args = ["tag"]
        if message:
            args.extend(["-a", name, "-m", message])
        else:
            args.append(name)
        r = _git(*args, cwd=repo_path)
    elif action == "delete":
        if not name:
            return {"success": False, "error": "Tag name required for delete"}
        r = _git("tag", "-d", name, cwd=repo_path)
    else:
        return {"success": False, "error": f"Unknown tag action: {action}"}
    return _check_result(r)


@register_tool(
    "git_show",
    "Show the contents of a commit or object.",
    params_schema={
        "type": "object",
        "properties": {
            "repo_path": {"type": "string", "description": "Path to the git repository"},
            "ref": {"type": "string", "description": "Ref to show (commit hash, branch, tag)"},
        },
        "required": ["repo_path", "ref"],
    },
)
def git_show(repo_path: str, ref: str) -> Dict[str, Any]:
    return _check_result(_git("show", ref, cwd=repo_path))
