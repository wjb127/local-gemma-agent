from __future__ import annotations

from dataclasses import dataclass
import queue
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from .agent import OllamaClient, build_system_prompt, run_agent_turn
from .config import Settings


@dataclass(slots=True)
class UiColors:
    bg: str = "#f4efe6"
    panel: str = "#fbf7f2"
    text: str = "#1f1f1f"
    accent: str = "#2f6f5e"
    accent_soft: str = "#d8ebe4"
    border: str = "#d7cfc4"
    user_bubble: str = "#e6f1ed"
    agent_bubble: str = "#f7f1e8"
    status: str = "#6a6259"


class AgentGui:
    def __init__(self, root: tk.Tk, settings: Settings) -> None:
        self.root = root
        self.settings = settings
        self.colors = UiColors()
        self.client = OllamaClient(
            host=settings.ollama_host,
            model=settings.model_name,
            temperature=settings.temperature,
        )
        self.messages = [{"role": "system", "content": build_system_prompt(settings)}]
        self.pending = False
        self.result_queue: queue.Queue[tuple[str, str]] = queue.Queue()

        self._configure_root()
        self._build_layout()
        self._poll_queue()
        self._append_agent_message(
            "로컬 Gemma 에이전트 GUI가 준비됐습니다.\n"
            "웹 검색, 로컬 문서 검색, Obsidian vault 검색을 바로 요청할 수 있어요."
        )

    def _configure_root(self) -> None:
        self.root.title("Local Gemma Agent")
        self.root.geometry("1120x780")
        self.root.minsize(920, 640)
        self.root.configure(bg=self.colors.bg)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("App.TFrame", background=self.colors.bg)
        style.configure("Panel.TFrame", background=self.colors.panel, relief="flat")
        style.configure(
            "Title.TLabel",
            background=self.colors.bg,
            foreground=self.colors.text,
            font=("Malgun Gothic", 22, "bold"),
        )
        style.configure(
            "Meta.TLabel",
            background=self.colors.bg,
            foreground=self.colors.status,
            font=("Malgun Gothic", 10),
        )
        style.configure(
            "Section.TLabel",
            background=self.colors.panel,
            foreground=self.colors.text,
            font=("Malgun Gothic", 11, "bold"),
        )
        style.configure(
            "Status.TLabel",
            background=self.colors.panel,
            foreground=self.colors.status,
            font=("Malgun Gothic", 10),
        )
        style.configure(
            "Accent.TButton",
            font=("Malgun Gothic", 10, "bold"),
            foreground="white",
            background=self.colors.accent,
            borderwidth=0,
            padding=(14, 10),
        )
        style.map(
            "Accent.TButton",
            background=[("active", "#275d4f"), ("disabled", "#98b6ac")],
        )
        style.configure(
            "Soft.TButton",
            font=("Malgun Gothic", 10),
            foreground=self.colors.text,
            background=self.colors.accent_soft,
            borderwidth=0,
            padding=(12, 10),
        )
        style.map(
            "Soft.TButton",
            background=[("active", "#c7e1d8"), ("disabled", "#e8e0d6")],
        )

    def _build_layout(self) -> None:
        outer = ttk.Frame(self.root, style="App.TFrame", padding=18)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=3)
        outer.columnconfigure(1, weight=1)
        outer.rowconfigure(1, weight=1)

        header = ttk.Frame(outer, style="App.TFrame")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 14))
        header.columnconfigure(0, weight=1)

        ttk.Label(header, text="Local Gemma Agent", style="Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            header,
            text="모든 추론은 로컬 Ollama에서 수행되고, GUI도 이 PC 안에서만 동작합니다.",
            style="Meta.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(6, 0))

        chat_panel = ttk.Frame(outer, style="Panel.TFrame", padding=14)
        chat_panel.grid(row=1, column=0, sticky="nsew", padx=(0, 12))
        chat_panel.columnconfigure(0, weight=1)
        chat_panel.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(chat_panel, style="Panel.TFrame")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        toolbar.columnconfigure(0, weight=1)
        ttk.Label(toolbar, text="Chat", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Button(toolbar, text="새 대화", style="Soft.TButton", command=self._reset_chat).grid(
            row=0, column=1, sticky="e", padx=(8, 0)
        )

        self.chat_box = scrolledtext.ScrolledText(
            chat_panel,
            wrap="word",
            font=("Malgun Gothic", 11),
            bg=self.colors.panel,
            fg=self.colors.text,
            insertbackground=self.colors.text,
            relief="flat",
            borderwidth=0,
            padx=6,
            pady=8,
        )
        self.chat_box.grid(row=1, column=0, sticky="nsew")
        self.chat_box.tag_configure(
            "user",
            background=self.colors.user_bubble,
            lmargin1=14,
            lmargin2=14,
            rmargin=14,
            spacing1=8,
            spacing3=8,
            font=("Malgun Gothic", 11, "bold"),
        )
        self.chat_box.tag_configure(
            "agent",
            background=self.colors.agent_bubble,
            lmargin1=14,
            lmargin2=14,
            rmargin=14,
            spacing1=8,
            spacing3=8,
            font=("Malgun Gothic", 11),
        )
        self.chat_box.tag_configure(
            "label",
            foreground=self.colors.accent,
            font=("Malgun Gothic", 9, "bold"),
        )
        self.chat_box.configure(state="disabled")

        composer = ttk.Frame(chat_panel, style="Panel.TFrame")
        composer.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        composer.columnconfigure(0, weight=1)

        self.input_box = tk.Text(
            composer,
            height=4,
            wrap="word",
            font=("Malgun Gothic", 11),
            bg="white",
            fg=self.colors.text,
            insertbackground=self.colors.text,
            relief="solid",
            borderwidth=1,
            padx=10,
            pady=10,
        )
        self.input_box.grid(row=0, column=0, sticky="ew")
        self.input_box.bind("<Control-Return>", self._send_from_event)

        actions = ttk.Frame(composer, style="Panel.TFrame")
        actions.grid(row=0, column=1, sticky="ns", padx=(10, 0))
        ttk.Button(actions, text="보내기", style="Accent.TButton", command=self._send_message).pack(
            fill="x"
        )
        ttk.Label(
            actions,
            text="Ctrl+Enter로 전송",
            style="Status.TLabel",
        ).pack(anchor="center", pady=(8, 0))

        side = ttk.Frame(outer, style="Panel.TFrame", padding=14)
        side.grid(row=1, column=1, sticky="nsew")
        side.columnconfigure(0, weight=1)

        ttk.Label(side, text="Session", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        meta_lines = [
            f"Model: {self.settings.model_name}",
            f"Ollama: {self.settings.ollama_host}",
            f"Workspace: {self.settings.workspace_dir}",
            f"Docs: {self.settings.local_docs_dir}",
            f"Vault: {self.settings.obsidian_vault_dir or 'Not configured'}",
        ]
        ttk.Label(
            side,
            text="\n".join(meta_lines),
            style="Status.TLabel",
            justify="left",
        ).grid(row=1, column=0, sticky="ew", pady=(8, 14))

        ttk.Label(side, text="Prompt Ideas", style="Section.TLabel").grid(row=2, column=0, sticky="w")
        prompt_ideas = tk.Listbox(
            side,
            height=8,
            font=("Malgun Gothic", 10),
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.colors.border,
            selectbackground=self.colors.accent_soft,
            selectforeground=self.colors.text,
            bg="white",
        )
        prompt_ideas.grid(row=3, column=0, sticky="ew")
        ideas = [
            "workspace/docs에서 중요한 문서를 찾아 요약해줘",
            "웹 검색으로 Gemma 3 로컬 실행 자료 3개 찾아줘",
            "Obsidian vault에서 Karpathy 관련 노트 찾아줘",
            "workspace 안 파일 구조를 정리해줘",
            "로컬 문서와 vault 내용을 비교해서 공통 주제를 정리해줘",
        ]
        for item in ideas:
            prompt_ideas.insert("end", item)
        prompt_ideas.bind("<<ListboxSelect>>", lambda event: self._fill_prompt(prompt_ideas))

        ttk.Label(side, text="Status", style="Section.TLabel").grid(row=4, column=0, sticky="w", pady=(16, 0))
        self.status_var = tk.StringVar(value="준비됨")
        ttk.Label(side, textvariable=self.status_var, style="Status.TLabel", wraplength=260).grid(
            row=5, column=0, sticky="ew", pady=(8, 0)
        )

    def _fill_prompt(self, listbox: tk.Listbox) -> None:
        selection = listbox.curselection()
        if not selection:
            return
        self.input_box.delete("1.0", "end")
        self.input_box.insert("1.0", listbox.get(selection[0]))
        self.input_box.focus_set()

    def _append_message(self, speaker: str, message: str, tag: str) -> None:
        self.chat_box.configure(state="normal")
        self.chat_box.insert("end", f"{speaker}\n", ("label",))
        self.chat_box.insert("end", f"{message.strip()}\n\n", (tag,))
        self.chat_box.configure(state="disabled")
        self.chat_box.see("end")

    def _append_user_message(self, message: str) -> None:
        self._append_message("You", message, "user")

    def _append_agent_message(self, message: str) -> None:
        self._append_message("Agent", message, "agent")

    def _set_pending(self, pending: bool, status: str) -> None:
        self.pending = pending
        self.status_var.set(status)

    def _reset_chat(self) -> None:
        if self.pending:
            messagebox.showinfo("진행 중", "응답이 끝난 뒤 새 대화를 시작할 수 있어요.")
            return
        self.messages = [{"role": "system", "content": build_system_prompt(self.settings)}]
        self.chat_box.configure(state="normal")
        self.chat_box.delete("1.0", "end")
        self.chat_box.configure(state="disabled")
        self._append_agent_message("새 대화를 시작했습니다. 무엇을 도와드릴까요?")
        self.status_var.set("새 세션 준비됨")

    def _send_from_event(self, event: tk.Event) -> str:
        self._send_message()
        return "break"

    def _send_message(self) -> None:
        if self.pending:
            return

        prompt = self.input_box.get("1.0", "end").strip()
        if not prompt:
            return

        self.input_box.delete("1.0", "end")
        self._append_user_message(prompt)
        self.messages.append({"role": "user", "content": prompt})
        self._set_pending(True, "로컬 모델이 응답을 생성하고 있습니다...")

        thread = threading.Thread(target=self._run_turn, daemon=True)
        thread.start()

    def _run_turn(self) -> None:
        try:
            reply = run_agent_turn(self.client, self.messages, self.settings)
        except Exception as exc:
            self.result_queue.put(("error", str(exc)))
            return
        self.result_queue.put(("ok", reply))

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self.result_queue.get_nowait()
                if kind == "ok":
                    self._append_agent_message(payload)
                    self._set_pending(False, "응답 완료")
                else:
                    self._append_agent_message(f"오류: {payload}")
                    self._set_pending(False, "오류 발생")
        except queue.Empty:
            pass
        finally:
            self.root.after(120, self._poll_queue)


def launch_gui() -> None:
    settings = Settings.from_env()
    settings.workspace_dir.mkdir(parents=True, exist_ok=True)
    settings.local_docs_dir.mkdir(parents=True, exist_ok=True)

    root = tk.Tk()
    AgentGui(root, settings)
    root.mainloop()
