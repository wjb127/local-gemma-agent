Option Explicit

Dim shell
Dim projectRoot
Dim pythonwPath
Dim command

Set shell = CreateObject("WScript.Shell")

projectRoot = "C:\Users\Qhv14\OneDrive\바탕 화면\Codex\20 Projects\local-gemma-agent"
pythonwPath = projectRoot & "\.venv\Scripts\pythonw.exe"

shell.CurrentDirectory = projectRoot
command = Chr(34) & pythonwPath & Chr(34) & " -c " & Chr(34) & "from local_gemma_agent.gui import launch_gui; launch_gui()" & Chr(34)
shell.Run command, 0, False
