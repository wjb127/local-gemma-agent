# Local Gemma Agent

이 프로젝트는 인터넷 API 없이, 이 컴퓨터 안에서만 돌아가는 로컬 AI 에이전트 예제입니다.
모델은 `Ollama`로 실행하고, 기본 모델은 `Gemma 3 4B` (`gemma3:4b`)로 설정되어 있습니다.

## 보안 방향

- 대화 요청은 기본적으로 로컬 Ollama 서버(`http://127.0.0.1:11434`)로만 전송됩니다.
- OpenAI, Google API 키가 필요하지 않습니다.
- 에이전트가 파일을 쓸 수 있는 범위는 프로젝트 안의 `workspace/` 폴더로 제한했습니다.

## 빠른 시작

### 1. Ollama 설치

PowerShell에서 실행:

```powershell
winget install --id Ollama.Ollama -e
```

설치가 끝나면 Ollama 앱 또는 백그라운드 서비스가 실행 중이어야 합니다.

### 2. Gemma 모델 받기

```powershell
ollama pull gemma3:4b
```

메모리가 넉넉하면 더 큰 모델(`gemma3:12b`)로 바꿔도 됩니다.

### 3. 프로젝트 부트스트랩

```powershell
Set-Location "C:\Users\Qhv14\OneDrive\바탕 화면\Codex\20 Projects\local-gemma-agent"
.\bootstrap.ps1
```

### 4. 실행

대화형 실행:

```powershell
.\run-agent.ps1
```

GUI 실행:

```powershell
.\run-gui.ps1
```

단일 프롬프트 실행:

```powershell
.\run-agent.ps1 -Prompt "workspace 폴더 구조를 설명해줘"
```

## 현재 포함된 툴

- `list_files`: `workspace/` 내부 폴더/파일 목록 조회
- `read_text_file`: 텍스트 파일 읽기
- `write_text_file`: `workspace/` 내부에 텍스트 파일 저장 또는 이어쓰기
- `search_text`: 텍스트 검색
- `web_search`: 웹 검색 결과 제목/링크/요약 수집
- `search_local_docs`: `workspace/docs` 같은 로컬 문서 폴더를 가볍게 RAG 방식으로 검색
- `list_obsidian_notes`: 연결된 Obsidian vault의 노트 목록 조회
- `read_obsidian_note`: Obsidian 노트 읽기
- `search_obsidian_notes`: Obsidian 노트 검색

## 디렉터리 구조

```text
local-gemma-agent/
|- bootstrap.ps1
|- run-agent.ps1
|- run-gui.ps1
|- workspace/
|  `- docs/
`- src/local_gemma_agent/
```

## 환경 변수

`.env.example`을 참고해서 시스템 환경 변수로 설정하거나 PowerShell에서 세션별로 지정할 수 있습니다.

```powershell
$env:OLLAMA_MODEL = "gemma3:12b"
```

추가 설정:

```powershell
$env:LOCAL_DOCS_DIR = "workspace/docs"
$env:OBSIDIAN_VAULT_DIR = "C:\Users\Qhv14\OneDrive\바탕 화면\Codex"
```

`OBSIDIAN_VAULT_DIR`를 비워두면, 프로젝트 상위 폴더 중 `.obsidian`이 있는 위치를 자동으로 찾아 연결합니다.

## 예시 요청

```text
workspace/docs에서 RAG처럼 관련 문서를 찾아 요약해줘
```

```text
웹 검색으로 Gemma 3 로컬 실행 관련 자료 3개만 찾아줘
```

```text
내 Obsidian vault에서 'Karpathy' 관련 노트를 찾아 핵심만 정리해줘
```

## GUI 구성

- 왼쪽: 대화 로그와 입력창
- 오른쪽: 현재 모델, 로컬 문서 폴더, Obsidian vault 상태
- 프롬프트 아이디어 클릭으로 예시 질문 바로 입력
- `새 대화` 버튼으로 시스템 프롬프트는 유지한 채 세션만 초기화

## 주의

- `gemma3:4b`는 비교적 가볍지만, 여전히 GPU/메모리 상황에 따라 속도가 달라질 수 있습니다.
- 툴 호출은 프롬프트 기반으로 구현되어 있어, 필요하면 나중에 Ollama의 네이티브 툴 호출 API 방식으로 확장할 수 있습니다.
- 웹 검색은 간단한 HTML 검색 결과를 파싱하는 방식이라, 일부 사이트는 요약 품질이 들쑥날쑥할 수 있습니다.
