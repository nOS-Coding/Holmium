"""GitHub integration tools using PyGithub."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from github import Github
from github.GithubException import GithubException

from tools.registry import register_tool

_SECRETS_PATH = "/etc/holmium/secrets.env"


def _get_token() -> Optional[str]:
    if not os.path.isfile(_SECRETS_PATH):
        return None
    with open(_SECRETS_PATH) as f:
        for line in f:
            line = line.strip()
            if line.startswith("github_token="):
                return line.split("=", 1)[1].strip("'\"")
    return None


def _get_client() -> Optional[Github]:
    token = _get_token()
    if not token:
        return None
    return Github(token)


@register_tool(
    "gh_list_repos",
    "List all repositories for the authenticated GitHub user.",
)
def gh_list_repos() -> List[Dict[str, Any]]:
    client = _get_client()
    if client is None:
        return [{"error": "GitHub token not configured in /etc/holmium/secrets.env"}]
    try:
        repos = []
        for repo in client.get_user().get_repos():
            repos.append({
                "name": repo.name,
                "full_name": repo.full_name,
                "description": repo.description,
                "url": repo.html_url,
                "private": repo.private,
                "language": repo.language,
                "updated_at": str(repo.updated_at),
                "stars": repo.stargazers_count,
                "forks": repo.forks_count,
            })
        return repos
    except GithubException as e:
        return [{"error": str(e.data.get("message", e))}]


@register_tool(
    "gh_create_issue",
    "Create a new issue in a repository.",
    params_schema={
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository full name (e.g. user/repo)"},
            "title": {"type": "string", "description": "Issue title"},
            "body": {"type": "string", "description": "Issue body"},
        },
        "required": ["repo", "title"],
    },
)
def gh_create_issue(repo: str, title: str, body: str = "") -> Dict[str, Any]:
    client = _get_client()
    if client is None:
        return {"error": "GitHub token not configured"}
    try:
        issue = client.get_repo(repo).create_issue(title=title, body=body)
        return {"number": issue.number, "title": issue.title, "url": issue.html_url, "state": issue.state}
    except GithubException as e:
        return {"error": str(e.data.get("message", e))}


@register_tool(
    "gh_list_issues",
    "List open issues in a repository.",
    params_schema={
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository full name (e.g. user/repo)"},
        },
        "required": ["repo"],
    },
)
def gh_list_issues(repo: str) -> List[Dict[str, Any]]:
    client = _get_client()
    if client is None:
        return [{"error": "GitHub token not configured"}]
    try:
        issues = []
        for issue in client.get_repo(repo).get_issues(state="open"):
            issues.append({
                "number": issue.number,
                "title": issue.title,
                "state": issue.state,
                "created_at": str(issue.created_at),
                "updated_at": str(issue.updated_at),
                "labels": [l.name for l in issue.labels],
                "url": issue.html_url,
            })
        return issues
    except GithubException as e:
        return [{"error": str(e.data.get("message", e))}]


@register_tool(
    "gh_close_issue",
    "Close an issue by repository and issue number.",
    params_schema={
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository full name"},
            "issue_number": {"type": "integer", "description": "Issue number to close"},
        },
        "required": ["repo", "issue_number"],
    },
)
def gh_close_issue(repo: str, issue_number: int) -> bool:
    client = _get_client()
    if client is None:
        return False
    try:
        issue = client.get_repo(repo).get_issue(number=issue_number)
        issue.edit(state="closed")
        return True
    except GithubException:
        return False


@register_tool(
    "gh_create_pr",
    "Create a pull request.",
    params_schema={
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository full name"},
            "title": {"type": "string", "description": "PR title"},
            "body": {"type": "string", "description": "PR description"},
            "head": {"type": "string", "description": "Head branch"},
            "base": {"type": "string", "description": "Base branch (default main)"},
        },
        "required": ["repo", "title", "head"],
    },
)
def gh_create_pr(repo: str, title: str, body: str = "", head: str = "", base: str = "main") -> Dict[str, Any]:
    client = _get_client()
    if client is None:
        return {"error": "GitHub token not configured"}
    try:
        pr = client.get_repo(repo).create_pull(title=title, body=body, head=head, base=base)
        return {"number": pr.number, "title": pr.title, "url": pr.html_url, "state": pr.state}
    except GithubException as e:
        return {"error": str(e.data.get("message", e))}


@register_tool(
    "gh_list_prs",
    "List open pull requests in a repository.",
    params_schema={
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository full name"},
        },
        "required": ["repo"],
    },
)
def gh_list_prs(repo: str) -> List[Dict[str, Any]]:
    client = _get_client()
    if client is None:
        return [{"error": "GitHub token not configured"}]
    try:
        prs = []
        for pr in client.get_repo(repo).get_pulls(state="open"):
            prs.append({
                "number": pr.number,
                "title": pr.title,
                "state": pr.state,
                "created_at": str(pr.created_at),
                "head": pr.head.label,
                "base": pr.base.label,
                "url": pr.html_url,
            })
        return prs
    except GithubException as e:
        return [{"error": str(e.data.get("message", e))}]


@register_tool(
    "gh_merge_pr",
    "Merge a pull request.",
    params_schema={
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository full name"},
            "pr_number": {"type": "integer", "description": "PR number to merge"},
        },
        "required": ["repo", "pr_number"],
    },
)
def gh_merge_pr(repo: str, pr_number: int) -> bool:
    client = _get_client()
    if client is None:
        return False
    try:
        pr = client.get_repo(repo).get_pull(number=pr_number)
        pr.merge()
        return True
    except GithubException:
        return False


@register_tool(
    "gh_push_file",
    "Create or update a file in a repository via the GitHub API.",
    params_schema={
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository full name"},
            "path": {"type": "string", "description": "File path in the repository"},
            "content": {"type": "string", "description": "File content"},
            "commit_message": {"type": "string", "description": "Commit message"},
            "branch": {"type": "string", "description": "Branch name (default main)"},
        },
        "required": ["repo", "path", "content", "commit_message"],
    },
)
def gh_push_file(repo: str, path: str, content: str, commit_message: str, branch: str = "main") -> bool:
    client = _get_client()
    if client is None:
        return False
    try:
        r = client.get_repo(repo)
        try:
            existing = r.get_contents(path, ref=branch)
            r.update_file(path, commit_message, content, existing.sha, branch=branch)
        except GithubException:
            r.create_file(path, commit_message, content, branch=branch)
        return True
    except GithubException:
        return False


@register_tool(
    "gh_get_file",
    "Get the contents of a file from a repository.",
    params_schema={
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository full name"},
            "path": {"type": "string", "description": "File path"},
            "branch": {"type": "string", "description": "Branch name (default main)"},
        },
        "required": ["repo", "path"],
    },
)
def gh_get_file(repo: str, path: str, branch: str = "main") -> str:
    client = _get_client()
    if client is None:
        return "GitHub token not configured"
    try:
        contents = client.get_repo(repo).get_contents(path, ref=branch)
        if isinstance(contents, list):
            return "\n".join(c.name for c in contents)
        return contents.decoded_content.decode("utf-8")
    except GithubException as e:
        return f"Error: {e.data.get('message', e)}"


@register_tool(
    "gh_monitor_repo",
    "Start monitoring a repository for new issues/PRs.",
    params_schema={
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository full name to monitor"},
        },
        "required": ["repo"],
    },
)
def gh_monitor_repo(repo: str) -> None:
    """Register a repo for periodic monitoring. Stored in scheduler / background loop."""
    monitor_path = Path("/var/holmium/github_monitors.json")
    monitors: List[str] = []
    if monitor_path.is_file():
        import json
        monitors = json.loads(monitor_path.read_text())
    if repo not in monitors:
        monitors.append(repo)
    monitor_path.parent.mkdir(parents=True, exist_ok=True)
    import json
    monitor_path.write_text(json.dumps(monitors))


# ── PR Details & Diff ────────────────────────────────────────────────────────────


@register_tool(
    "gh_pr_details",
    "Get detailed information about a pull request.",
    params_schema={
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository full name"},
            "pr_number": {"type": "integer", "description": "PR number"},
        },
        "required": ["repo", "pr_number"],
    },
)
def gh_pr_details(repo: str, pr_number: int) -> Dict[str, Any]:
    client = _get_client()
    if client is None:
        return {"error": "GitHub token not configured"}
    try:
        pr = client.get_repo(repo).get_pull(number=pr_number)
        return {
            "number": pr.number,
            "title": pr.title,
            "body": pr.body,
            "state": pr.state,
            "merged": pr.merged,
            "mergeable": pr.mergeable,
            "mergeable_state": pr.mergeable_state,
            "draft": pr.draft,
            "created_at": str(pr.created_at),
            "updated_at": str(pr.updated_at),
            "head": {"ref": pr.head.ref, "sha": pr.head.sha, "repo": pr.head.repo.full_name if pr.head.repo else None},
            "base": {"ref": pr.base.ref, "sha": pr.base.sha},
            "user": pr.user.login if pr.user else None,
            "labels": [l.name for l in pr.labels],
            "url": pr.html_url,
        }
    except GithubException as e:
        return {"error": str(e.data.get("message", e))}


@register_tool(
    "gh_pr_diff",
    "Get the diff of a pull request (list of changed files with status and patch).",
    params_schema={
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository full name"},
            "pr_number": {"type": "integer", "description": "PR number"},
        },
        "required": ["repo", "pr_number"],
    },
)
def gh_pr_diff(repo: str, pr_number: int) -> List[Dict[str, Any]]:
    client = _get_client()
    if client is None:
        return [{"error": "GitHub token not configured"}]
    try:
        pr = client.get_repo(repo).get_pull(number=pr_number)
        files = []
        for f in pr.get_files():
            files.append({
                "filename": f.filename,
                "status": f.status,
                "additions": f.additions,
                "deletions": f.deletions,
                "changes": f.changes,
                "patch": f.patch,
                "raw_url": f.raw_url,
            })
        return files
    except GithubException as e:
        return [{"error": str(e.data.get("message", e))}]


@register_tool(
    "gh_pr_comment",
    "Add a review comment to a pull request.",
    params_schema={
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository full name"},
            "pr_number": {"type": "integer", "description": "PR number"},
            "body": {"type": "string", "description": "Comment body"},
        },
        "required": ["repo", "pr_number", "body"],
    },
)
def gh_pr_comment(repo: str, pr_number: int, body: str) -> bool:
    client = _get_client()
    if client is None:
        return False
    try:
        pr = client.get_repo(repo).get_pull(number=pr_number)
        pr.create_issue_comment(body)
        return True
    except GithubException:
        return False


@register_tool(
    "gh_review_pr",
    "Submit a formal review for a pull request (approve, comment, or request changes).",
    params_schema={
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository full name"},
            "pr_number": {"type": "integer", "description": "PR number"},
            "body": {"type": "string", "description": "Review body text"},
            "event": {
                "type": "string",
                "enum": ["APPROVE", "COMMENT", "REQUEST_CHANGES"],
                "description": "Review action",
            },
        },
        "required": ["repo", "pr_number", "body", "event"],
    },
)
def gh_review_pr(repo: str, pr_number: int, body: str, event: str) -> bool:
    client = _get_client()
    if client is None:
        return False
    try:
        pr = client.get_repo(repo).get_pull(number=pr_number)
        pr.create_review(body=body, event=event)
        return True
    except GithubException:
        return False


# ── Labels ───────────────────────────────────────────────────────────────────────


@register_tool(
    "gh_add_labels",
    "Add labels to an issue or pull request.",
    params_schema={
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository full name"},
            "issue_number": {"type": "integer", "description": "Issue or PR number"},
            "labels": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Label names to add",
            },
        },
        "required": ["repo", "issue_number", "labels"],
    },
)
def gh_add_labels(repo: str, issue_number: int, labels: List[str]) -> bool:
    client = _get_client()
    if client is None:
        return False
    try:
        issue = client.get_repo(repo).get_issue(number=issue_number)
        issue.add_to_labels(*labels)
        return True
    except GithubException:
        return False


@register_tool(
    "gh_remove_label",
    "Remove a label from an issue or pull request.",
    params_schema={
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository full name"},
            "issue_number": {"type": "integer", "description": "Issue or PR number"},
            "label": {"type": "string", "description": "Label name to remove"},
        },
        "required": ["repo", "issue_number", "label"],
    },
)
def gh_remove_label(repo: str, issue_number: int, label: str) -> bool:
    client = _get_client()
    if client is None:
        return False
    try:
        issue = client.get_repo(repo).get_issue(number=issue_number)
        issue.remove_from_labels(label)
        return True
    except GithubException:
        return False


# ── Branches ─────────────────────────────────────────────────────────────────────


@register_tool(
    "gh_list_branches",
    "List branches in a repository.",
    params_schema={
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository full name"},
        },
        "required": ["repo"],
    },
)
def gh_list_branches(repo: str) -> List[Dict[str, Any]]:
    client = _get_client()
    if client is None:
        return [{"error": "GitHub token not configured"}]
    try:
        branches = []
        for b in client.get_repo(repo).get_branches():
            branches.append({
                "name": b.name,
                "commit_sha": b.commit.sha,
                "protected": b.protected,
            })
        return branches
    except GithubException as e:
        return [{"error": str(e.data.get("message", e))}]


@register_tool(
    "gh_create_branch",
    "Create a new branch in a repository from an existing ref.",
    params_schema={
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository full name"},
            "branch": {"type": "string", "description": "New branch name"},
            "source_branch": {"type": "string", "description": "Source branch to fork from (default main)"},
        },
        "required": ["repo", "branch"],
    },
)
def gh_create_branch(repo: str, branch: str, source_branch: str = "main") -> bool:
    client = _get_client()
    if client is None:
        return False
    try:
        r = client.get_repo(repo)
        ref = r.get_git_ref(f"heads/{source_branch}")
        r.create_git_ref(ref=f"refs/heads/{branch}", sha=ref.object.sha)
        return True
    except GithubException:
        return False


@register_tool(
    "gh_delete_branch",
    "Delete a branch from a repository.",
    params_schema={
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository full name"},
            "branch": {"type": "string", "description": "Branch name to delete"},
        },
        "required": ["repo", "branch"],
    },
)
def gh_delete_branch(repo: str, branch: str) -> bool:
    client = _get_client()
    if client is None:
        return False
    try:
        r = client.get_repo(repo)
        ref = r.get_git_ref(f"heads/{branch}")
        ref.delete()
        return True
    except GithubException:
        return False


# ── CI / GitHub Actions ──────────────────────────────────────────────────────────


@register_tool(
    "gh_list_workflows",
    "List GitHub Actions workflows in a repository.",
    params_schema={
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository full name"},
        },
        "required": ["repo"],
    },
)
def gh_list_workflows(repo: str) -> List[Dict[str, Any]]:
    client = _get_client()
    if client is None:
        return [{"error": "GitHub token not configured"}]
    try:
        workflows = []
        for w in client.get_repo(repo).get_workflows():
            workflows.append({
                "name": w.name,
                "path": w.path,
                "state": w.state,
                "url": w.html_url,
            })
        return workflows
    except GithubException as e:
        return [{"error": str(e.data.get("message", e))}]


@register_tool(
    "gh_trigger_workflow",
    "Trigger a GitHub Actions workflow by name.",
    params_schema={
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository full name"},
            "workflow_name": {"type": "string", "description": "Workflow filename (e.g. ci.yml)"},
            "ref": {"type": "string", "description": "Branch or ref to run on (default main)"},
        },
        "required": ["repo", "workflow_name"],
    },
)
def gh_trigger_workflow(repo: str, workflow_name: str, ref: str = "main") -> bool:
    client = _get_client()
    if client is None:
        return False
    try:
        r = client.get_repo(repo)
        for w in r.get_workflows():
            if w.name == workflow_name or w.path.endswith(workflow_name):
                w.create_dispatch(ref=ref)
                return True
        return False
    except GithubException:
        return False


@register_tool(
    "gh_list_workflow_runs",
    "List recent workflow runs for a repository.",
    params_schema={
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository full name"},
            "limit": {"type": "integer", "description": "Max runs to return (default 10)"},
            "branch": {"type": "string", "description": "Filter by branch (optional)"},
        },
        "required": ["repo"],
    },
)
def gh_list_workflow_runs(repo: str, limit: int = 10, branch: str = "") -> List[Dict[str, Any]]:
    client = _get_client()
    if client is None:
        return [{"error": "GitHub token not configured"}]
    try:
        runs = []
        kwargs = {"branch": branch} if branch else {}
        for run in client.get_repo(repo).get_workflow_runs(**kwargs)[:limit]:
            runs.append({
                "id": run.id,
                "name": run.name,
                "workflow": run.workflow_url.split("/")[-1] if run.workflow_url else "",
                "head_branch": run.head_branch,
                "head_sha": run.head_sha[:8],
                "status": run.status,
                "conclusion": run.conclusion,
                "created_at": str(run.created_at),
                "updated_at": str(run.updated_at),
                "url": run.html_url,
            })
        return runs
    except GithubException as e:
        return [{"error": str(e.data.get("message", e))}]


# ── Releases ─────────────────────────────────────────────────────────────────────


@register_tool(
    "gh_list_releases",
    "List releases in a repository.",
    params_schema={
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository full name"},
            "limit": {"type": "integer", "description": "Max releases to return (default 10)"},
        },
        "required": ["repo"],
    },
)
def gh_list_releases(repo: str, limit: int = 10) -> List[Dict[str, Any]]:
    client = _get_client()
    if client is None:
        return [{"error": "GitHub token not configured"}]
    try:
        releases = []
        for r in client.get_repo(repo).get_releases()[:limit]:
            releases.append({
                "id": r.id,
                "tag_name": r.tag_name,
                "name": r.title,
                "draft": r.draft,
                "prerelease": r.prerelease,
                "created_at": str(r.created_at),
                "published_at": str(r.published_at),
                "body": r.body,
                "url": r.html_url,
            })
        return releases
    except GithubException as e:
        return [{"error": str(e.data.get("message", e))}]


@register_tool(
    "gh_create_release",
    "Create a new release in a repository.",
    params_schema={
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository full name"},
            "tag_name": {"type": "string", "description": "Git tag for the release"},
            "name": {"type": "string", "description": "Release title"},
            "body": {"type": "string", "description": "Release description"},
            "draft": {"type": "boolean", "description": "Create as draft (default false)"},
            "prerelease": {"type": "boolean", "description": "Mark as prerelease (default false)"},
        },
        "required": ["repo", "tag_name"],
    },
)
def gh_create_release(repo: str, tag_name: str, name: str = "", body: str = "", draft: bool = False, prerelease: bool = False) -> bool:
    client = _get_client()
    if client is None:
        return False
    try:
        r = client.get_repo(repo)
        r.create_git_release(tag=tag_name, name=name or tag_name, message=body, draft=draft, prerelease=prerelease)
        return True
    except GithubException:
        return False
