Option Explicit
Dim dossier, python, interface, shell, fichiers
Set fichiers = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
dossier = fichiers.GetParentFolderName(WScript.ScriptFullName)
python = fichiers.BuildPath(dossier, ".venv\Scripts\pythonw.exe")
interface = fichiers.BuildPath(dossier, "interface_trading.pyw")
If Not fichiers.FileExists(python) Then
    MsgBox "L'environnement .venv est absent. Installe le projet comme indique dans le README.", 48, "Analyse MT5"
    WScript.Quit 1
End If
shell.CurrentDirectory = dossier
shell.Run Chr(34) & python & Chr(34) & " " & Chr(34) & interface & Chr(34), 1, False
