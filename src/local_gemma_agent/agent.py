from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import argparse
import json
import sys
import textwrap
import urllib.error
import urllib.request

from .config import Settings
from .tools import TOOLS, ToolError, execute_tool, tool_catalog_text


SYSTEM_PROMPT_TEMPLATE = """\
You are a local-first AI agent running on the user's own computer.
You must keep all work local and never suggest external APIs unless the user asks.

Your writable area is limited to this workspace:
{workspace_dir}

Preferred local docs directory for retrieval:
{local_docs_dir}

Configured Obsidian vault:
{obsidian_vault_dir}

Available tools:
{tool_catalog}

Rules:
1. When you need a tool, respond with JSON only.
2. Tool JSON format:
{{"type":"tool_call","tool":"list_files","args":{{"path":"."}}}}
3. When you are done, respond with JSON only:
{{"type":"final","message":"your helpful answer"}}
4. Do not wrap JSON in markdown fences.
5. Use only one tool call at a time.
6. Prefer inspecting files before claiming something about them.
"""


@dataclass(slots=True)
class AgentAction:
    kind: str
    message: str | None = None
    tool: str | None = None
    args: dict | None = None


class OllamaClient:
    def __init__(self, host: str, model: str, temperature: float) -> None:
        self.host = host.rstrip("/")
        self.model = model
        self.temperature = temperature

    def chat(self, messages: list[dict]) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": self.temperature,
            },
        }
        request = urllib.request.Request(
            url=f"{self.host}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Could not reach Ollama at {self.host}. Make sure Ollama is installed and running."
            ) from exc

        message = body.get("message", {})
        content = message.get("content", "")
        if not content:
            raise RuntimeError("Ollama returned an empty response.")
        return content


def build_system_prompt(settings: Settings) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(
        workspace_dir=str(settings.workspace_dir),
        local_docs_dir=str(settings.local_docs_dir),
        obsidian_vault_dir=str(settings.obsidian_vault_dir) if settings.obsidian_vault_dir else "Not configured",
        tool_catalog=tool_catalog_text(),
    )


def parse_action(raw_text: str) -> AgentAction:
    raw_text = raw_text.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.lower().startswith("json"):
            raw_text = raw_text[4:].strip()

    normalized = (
        raw_text.replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2018", "'")
        .replace("\u2019", "'")
    )

    try:
        payload = json.loads(normalized)
    except json.JSONDecodeError:
        start = normalized.find("{")
        end = normalized.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                payload = json.loads(normalized[start : end + 1])
            except json.JSONDecodeError:
                return AgentAction(kind="final", message=raw_text)
        else:
            return AgentAction(kind="final", message=raw_text)

    kind = payload.get("type")
    if kind in TOOLS:
        return AgentAction(
            kind="tool_call",
            tool=kind,
            args=payload.get("args") or {},
        )
    if kind == "tool_call":
        return AgentAction(
            kind="tool_call",
            tool=payload.get("tool"),
            args=payload.get("args") or {},
        )
    if kind == "final":
        return AgentAction(kind="final", message=payload.get("message", ""))

    return AgentAction(kind="final", message=raw_text)


def format_tool_result(tool_name: str, result: dict) -> str:
    return textwrap.dedent(
        f"""\
        Tool execution result:
        tool={tool_name}
        result={json.dumps(result, ensure_ascii=False)}

        Continue by either calling another tool or returning a final answer as JSON.
        """
    ).strip()


def run_agent_turn(client: OllamaClient, messages: list[dict], settings: Settings) -> str:
    for _ in range(settings.max_steps):
        raw_reply = client.chat(messages)
        action = parse_action(raw_reply)

        if action.kind == "final":
            final_message = action.message or raw_reply
            messages.append({"role": "assistant", "content": final_message})
            return final_message

        messages.append({"role": "assistant", "content": raw_reply})

        try:
            result = execute_tool(
                name=action.tool or "",
                args=action.args or {},
                workspace_dir=settings.workspace_dir,
                obsidian_vault_dir=settings.obsidian_vault_dir,
            )
        except ToolError as exc:
            result = {"error": str(exc)}
        except TypeError as exc:
            result = {"error": f"Invalid arguments for tool {action.tool}: {exc}"}

        messages.append({"role": "user", "content": format_tool_result(action.tool or "", result)})

    raise RuntimeError("The agent reached the maximum tool steps without finishing.")


def interactive_chat(settings: Settings) -> None:
    client = OllamaClient(
        host=settings.ollama_host,
        model=settings.model_name,
        temperature=settings.temperature,
    )
    messages = [{"role": "system", "content": build_system_prompt(settings)}]

    print(f"Local Gemma Agent running with model: {settings.model_name}")
    print(f"Workspace: {settings.workspace_dir}")
    print("Type 'exit' to quit.\n")

    while True:
        user_input = input("You> ").strip()
        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            print("Bye.")
            return

        messages.append({"role": "user", "content": user_input})
        reply = run_agent_turn(client, messages, settings)
        print(f"\nAgent> {reply}\n")


def run_single_prompt(settings: Settings, prompt: str) -> None:
    client = OllamaClient(
        host=settings.ollama_host,
        model=settings.model_name,
        temperature=settings.temperature,
    )
    messages = [
        {"role": "system", "content": build_system_prompt(settings)},
        {"role": "user", "content": prompt},
    ]
    reply = run_agent_turn(client, messages, settings)
    print(reply)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Local Gemma Agent.")
    parser.add_argument("--prompt", help="Run a single prompt and exit.")
    args = parser.parse_args()

    settings = Settings.from_env()
    settings.workspace_dir.mkdir(parents=True, exist_ok=True)
    settings.local_docs_dir.mkdir(parents=True, exist_ok=True)

    try:
        if args.prompt:
            run_single_prompt(settings, args.prompt)
        else:
            interactive_chat(settings)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
