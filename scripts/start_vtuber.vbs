Set sh = CreateObject("WScript.Shell")
Set env = sh.Environment("PROCESS")
env("TMP") = "D:\yige-personal-kb\.runtime\tmp"
env("TEMP") = "D:\yige-personal-kb\.runtime\tmp"
env("HF_HOME") = "D:\yige-personal-kb\xiaojuju\vendor\open-llm-vtuber\models"
env("MODELSCOPE_CACHE") = "D:\yige-personal-kb\xiaojuju\vendor\open-llm-vtuber\models"
sh.CurrentDirectory = "D:\yige-personal-kb\xiaojuju\vendor\open-llm-vtuber"
sh.Run """D:\yige-personal-kb\xiaojuju\vendor\open-llm-vtuber\.venv\Scripts\python.exe"" run_server.py", 0, False