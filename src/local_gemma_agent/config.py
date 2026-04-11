from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_DIR = PROJECT_ROOT / "workspace"
DEFAULT_DOCS_DIR = WORKSPACE_DIR / "docs"


def _detect_obsidian_vault(start: Path) -> Path | None:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".obsidian").is_dir():
            return candidate
    return None


@dataclass(slots=True)
class Settings:
    ollama_host: str = "http://127.0.0.1:11434"
    model_name: str = "gemma3:4b"
    temperature: float = 0.2
    max_steps: int = 6
    workspace_dir: Path = WORKSPACE_DIR
    local_docs_dir: Path = DEFAULT_DOCS_DIR
    obsidian_vault_dir: Path | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        docs_dir = Path(os.getenv("LOCAL_DOCS_DIR", str(DEFAULT_DOCS_DIR)))
        if not docs_dir.is_absolute():
            docs_dir = (PROJECT_ROOT / docs_dir).resolve()

        vault_from_env = os.getenv("OBSIDIAN_VAULT_DIR", "").strip()
        if vault_from_env:
            obsidian_vault_dir = Path(vault_from_env).resolve()
        else:
            obsidian_vault_dir = _detect_obsidian_vault(PROJECT_ROOT)

        return cls(
            ollama_host=os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/"),
            model_name=os.getenv("OLLAMA_MODEL", "gemma3:4b"),
            temperature=float(os.getenv("AGENT_TEMPERATURE", "0.2")),
            max_steps=int(os.getenv("AGENT_MAX_STEPS", "6")),
            workspace_dir=WORKSPACE_DIR,
            local_docs_dir=docs_dir,
            obsidian_vault_dir=obsidian_vault_dir,
        )
