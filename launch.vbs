Option Explicit
Dim shell, fso, project, pythonw, command
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
project = fso.GetParentFolderName(WScript.ScriptFullName)
pythonw = shell.ExpandEnvironmentStrings("%USERPROFILE%") & "\venvs\CivitHelper\Scripts\pythonw.exe"
If Not fso.FileExists(pythonw) Then
  MsgBox "Python environment missing. See README.md.", 16, "Civit Helper"
  WScript.Quit 1
End If
shell.CurrentDirectory = project
command = Chr(34) & pythonw & Chr(34) & " " & Chr(34) & project & "\app.py" & Chr(34) & " gui"
shell.Run command, 0, False
