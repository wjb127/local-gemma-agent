from __future__ import annotations

from pathlib import Path
import html
import json
import math
import re
import urllib.parse
import urllib.request


class ToolError(Exception):
    """Raised when a tool request cannot be completed."""


def _resolve_in_workspace(workspace_dir: Path, raw_path: str) -> Path:
    candidate = (workspace_dir / raw_path).resolve()
    workspace_root = workspace_dir.resolve()

    if candidate != workspace_root and workspace_root not in candidate.parents:
        raise ToolError("Path is outside the workspace directory.")

    return candidate


def list_files(workspace_dir: Path, path: str = ".") -> dict:
    target = _resolve_in_workspace(workspace_dir, path)
    if not target.exists():
        raise ToolError(f"Path does not exist: {path}")
    if not target.is_dir():
        raise ToolError(f"Path is not a directory: {path}")

    entries = []
    for item in sorted(target.iterdir(), key=lambda value: (value.is_file(), value.name.lower())):
        entries.append(
            {
                "name": item.name,
                "path": str(item.relative_to(workspace_dir)).replace("\\", "/"),
                "type": "dir" if item.is_dir() else "file",
            }
        )
    return {"path": path, "entries": entries}


def read_text_file(workspace_dir: Path, path: str) -> dict:
    target = _resolve_in_workspace(workspace_dir, path)
    if not target.exists():
        raise ToolError(f"File does not exist: {path}")
    if not target.is_file():
        raise ToolError(f"Path is not a file: {path}")

    content = target.read_text(encoding="utf-8", errors="replace")
    return {"path": path, "content": content}


def write_text_file(workspace_dir: Path, path: str, content: str, mode: str = "overwrite") -> dict:
    target = _resolve_in_workspace(workspace_dir, path)
    target.parent.mkdir(parents=True, exist_ok=True)

    if mode == "append":
        with target.open("a", encoding="utf-8") as handle:
            handle.write(content)
    else:
        target.write_text(content, encoding="utf-8")

    return {
        "path": path,
        "mode": mode,
        "bytes_written": len(content.encode("utf-8")),
    }


def search_text(workspace_dir: Path, pattern: str, path: str = ".") -> dict:
    base = _resolve_in_workspace(workspace_dir, path)
    if not base.exists():
        raise ToolError(f"Path does not exist: {path}")

    matches = []
    files = [base] if base.is_file() else [item for item in base.rglob("*") if item.is_file()]
    for file_path in files:
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        for index, line in enumerate(content.splitlines(), start=1):
            if pattern.lower() in line.lower():
                matches.append(
                    {
                        "path": str(file_path.relative_to(workspace_dir)).replace("\\", "/"),
                        "line": index,
                        "text": line.strip(),
                    }
                )
                if len(matches) >= 20:
                    return {"pattern": pattern, "matches": matches}

    return {"pattern": pattern, "matches": matches}


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[0-9A-Za-z가-힣_]{2,}", text.lower())


def _iter_text_files(base: Path, extensions: set[str] | None = None) -> list[Path]:
    if not base.exists():
        raise ToolError(f"Path does not exist: {base}")

    if base.is_file():
        candidates = [base]
    else:
        candidates = [item for item in base.rglob("*") if item.is_file()]

    if not extensions:
        return candidates
    return [item for item in candidates if item.suffix.lower() in extensions]


def _score_text(query: str, text: str) -> float:
    query_tokens = _tokenize(query)
    text_tokens = _tokenize(text)
    if not query_tokens or not text_tokens:
        return 0.0

    counts: dict[str, int] = {}
    for token in text_tokens:
        counts[token] = counts.get(token, 0) + 1

    score = 0.0
    unique_query = set(query_tokens)
    for token in unique_query:
        term_frequency = counts.get(token, 0)
        if term_frequency:
            score += 1.0 + math.log(term_frequency)

    if query.lower() in text.lower():
        score += 2.0

    return score


def web_search(workspace_dir: Path, query: str, limit: int = 5) -> dict:
    del workspace_dir

    encoded_query = urllib.parse.urlencode({"q": query})
    url = f"https://html.duckduckgo.com/html/?{encoded_query}"
    request = urllib.request.Request(
        url=url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8", errors="replace")
    except OSError as exc:
        raise ToolError(f"Web search failed: {exc}") from exc

    pattern = re.compile(
        r'<a[^>]*class="result__a"[^>]*href="(?P<link>[^"]+)"[^>]*>(?P<title>.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    snippet_pattern = re.compile(
        r'<a[^>]*class="result__snippet"[^>]*>(?P<snippet>.*?)</a>|<div[^>]*class="result__snippet"[^>]*>(?P<snippet2>.*?)</div>',
        re.IGNORECASE | re.DOTALL,
    )

    title_matches = list(pattern.finditer(body))
    snippet_matches = list(snippet_pattern.finditer(body))

    results = []
    for index, match in enumerate(title_matches[: max(1, min(limit, 10))]):
        title = re.sub(r"<.*?>", "", match.group("title"))
        link = html.unescape(match.group("link"))
        if "uddg=" in link:
            parsed = urllib.parse.urlparse(link)
            uddg = urllib.parse.parse_qs(parsed.query).get("uddg")
            if uddg:
                link = uddg[0]
        snippet = ""
        if index < len(snippet_matches):
            snippet_raw = snippet_matches[index].group("snippet") or snippet_matches[index].group("snippet2") or ""
            snippet = re.sub(r"<.*?>", "", snippet_raw)

        results.append(
            {
                "title": html.unescape(title).strip(),
                "url": link.strip(),
                "snippet": html.unescape(snippet).strip(),
            }
        )

    return {"query": query, "results": results}


def search_local_docs(workspace_dir: Path, query: str, path: str = ".", limit: int = 5) -> dict:
    base = _resolve_in_workspace(workspace_dir, path)
    allowed_extensions = {".md", ".txt", ".py", ".json", ".yaml", ".yml", ".toml"}
    scored_results = []

    for file_path in _iter_text_files(base, allowed_extensions):
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        snippets = content.splitlines()
        best_score = _score_text(query, content)
        if best_score <= 0:
            continue

        snippet = ""
        for line in snippets:
            if _score_text(query, line) > 0:
                snippet = line.strip()
                break

        scored_results.append(
            {
                "path": str(file_path.relative_to(workspace_dir)).replace("\\", "/"),
                "score": round(best_score, 3),
                "snippet": snippet[:240],
            }
        )

    scored_results.sort(key=lambda item: item["score"], reverse=True)
    return {"query": query, "results": scored_results[: max(1, min(limit, 10))]}


def _resolve_in_root(root_dir: Path, raw_path: str) -> Path:
    candidate = (root_dir / raw_path).resolve()
    root = root_dir.resolve()
    if candidate != root and root not in candidate.parents:
        raise ToolError("Path is outside the allowed root directory.")
    return candidate


def list_obsidian_notes(workspace_dir: Path, vault_dir: str, path: str = ".", limit: int = 50) -> dict:
    del workspace_dir
    root = Path(vault_dir).resolve()
    if not root.exists():
        raise ToolError(f"Obsidian vault does not exist: {root}")

    target = _resolve_in_root(root, path)
    notes = []
    for item in _iter_text_files(target, {".md"}):
        rel = str(item.relative_to(root)).replace("\\", "/")
        notes.append(rel)
        if len(notes) >= max(1, min(limit, 200)):
            break

    return {"vault": str(root), "path": path, "notes": notes}


def read_obsidian_note(workspace_dir: Path, vault_dir: str, path: str) -> dict:
    del workspace_dir
    root = Path(vault_dir).resolve()
    if not root.exists():
        raise ToolError(f"Obsidian vault does not exist: {root}")

    target = _resolve_in_root(root, path)
    if target.suffix.lower() != ".md":
        raise ToolError("Only markdown notes can be read with this tool.")
    if not target.exists():
        raise ToolError(f"Note does not exist: {path}")

    content = target.read_text(encoding="utf-8", errors="replace")
    return {"path": path, "content": content}


def search_obsidian_notes(workspace_dir: Path, vault_dir: str, query: str, path: str = ".", limit: int = 5) -> dict:
    del workspace_dir
    root = Path(vault_dir).resolve()
    if not root.exists():
        raise ToolError(f"Obsidian vault does not exist: {root}")

    base = _resolve_in_root(root, path)
    scored_results = []
    for note_path in _iter_text_files(base, {".md"}):
        try:
            content = note_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        score = _score_text(query, content)
        if score <= 0:
            continue

        snippet = ""
        for line in content.splitlines():
            if _score_text(query, line) > 0:
                snippet = line.strip()
                break

        scored_results.append(
            {
                "path": str(note_path.relative_to(root)).replace("\\", "/"),
                "score": round(score, 3),
                "snippet": snippet[:240],
            }
        )

    scored_results.sort(key=lambda item: item["score"], reverse=True)
    return {"query": query, "results": scored_results[: max(1, min(limit, 10))]}


TOOLS = {
    "list_files": {
        "description": "List files and folders inside the workspace.",
        "arguments": {"path": "Relative path inside workspace. Defaults to '.'."},
        "handler": list_files,
    },
    "read_text_file": {
        "description": "Read a UTF-8 text file from the workspace.",
        "arguments": {"path": "Relative file path inside workspace."},
        "handler": read_text_file,
    },
    "write_text_file": {
        "description": "Write or append text to a file in the workspace.",
        "arguments": {
            "path": "Relative file path inside workspace.",
            "content": "Text content to write.",
            "mode": "Either 'overwrite' or 'append'.",
        },
        "handler": write_text_file,
    },
    "search_text": {
        "description": "Search case-insensitive text in files inside the workspace.",
        "arguments": {
            "pattern": "Case-insensitive search string.",
            "path": "Relative file or directory path inside workspace. Defaults to '.'.",
        },
        "handler": search_text,
    },
    "web_search": {
        "description": "Search the web and return result titles, URLs, and snippets.",
        "arguments": {
            "query": "Search query text.",
            "limit": "Optional integer from 1 to 10. Defaults to 5.",
        },
        "handler": web_search,
    },
    "search_local_docs": {
        "description": "Search local documents in the workspace with lightweight relevance scoring.",
        "arguments": {
            "query": "Question or keyword query.",
            "path": "Relative directory or file path inside workspace. Defaults to '.'.",
            "limit": "Optional integer from 1 to 10. Defaults to 5.",
        },
        "handler": search_local_docs,
    },
    "list_obsidian_notes": {
        "description": "List markdown notes from the configured Obsidian vault.",
        "arguments": {
            "vault_dir": "Absolute path of the Obsidian vault root.",
            "path": "Relative directory inside the vault. Defaults to '.'.",
            "limit": "Optional integer from 1 to 200. Defaults to 50.",
        },
        "handler": list_obsidian_notes,
    },
    "read_obsidian_note": {
        "description": "Read a markdown note from the configured Obsidian vault.",
        "arguments": {
            "vault_dir": "Absolute path of the Obsidian vault root.",
            "path": "Relative markdown note path inside the vault.",
        },
        "handler": read_obsidian_note,
    },
    "search_obsidian_notes": {
        "description": "Search markdown notes in the configured Obsidian vault.",
        "arguments": {
            "vault_dir": "Absolute path of the Obsidian vault root.",
            "query": "Question or keyword query.",
            "path": "Relative directory inside the vault. Defaults to '.'.",
            "limit": "Optional integer from 1 to 10. Defaults to 5.",
        },
        "handler": search_obsidian_notes,
    },
}


def tool_catalog_text() -> str:
    lines = []
    for name, meta in TOOLS.items():
        lines.append(f"- {name}: {meta['description']}")
        lines.append(f"  args: {json.dumps(meta['arguments'], ensure_ascii=False)}")
    return "\n".join(lines)


def execute_tool(
    name: str,
    args: dict,
    workspace_dir: Path,
    obsidian_vault_dir: Path | None = None,
) -> dict:
    if name not in TOOLS:
        raise ToolError(f"Unknown tool: {name}")

    resolved_args = dict(args)
    if name in {"list_obsidian_notes", "read_obsidian_note", "search_obsidian_notes"}:
        if "vault_dir" not in resolved_args:
            if obsidian_vault_dir is None:
                raise ToolError("No Obsidian vault is configured.")
            resolved_args["vault_dir"] = str(obsidian_vault_dir)

    handler = TOOLS[name]["handler"]
    return handler(workspace_dir=workspace_dir, **resolved_args)
