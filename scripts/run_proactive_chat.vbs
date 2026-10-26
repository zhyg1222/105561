Set sh = CreateObject("WScript.Shell")
Set env = sh.Environment("PROCESS")
env("TMP") = "D:\yige-personal-kb\.runtime\tmp"
env("TEMP") = "D:\yige-personal-kb\.runtime\tmp"
sh.CurrentDirectory = "D:\yige-personal-kb\xiaojuju"
sh.Run """D:\yige-personal-kb\.runtime\wechat-operator\.venv\Scripts\python.exe"" run_proactive_chat.py", 0, True