Set sh = CreateObject("WScript.Shell")
Set env = sh.Environment("PROCESS")
env("PYTHONPATH") = "D:\yige-personal-kb\xiaojuju\src"
env("XJJ_SHADOW_MODE") = "false"
env("TMP") = "D:\yige-personal-kb\.runtime\agent-tests\tmp"
env("TEMP") = "D:\yige-personal-kb\.runtime\agent-tests\tmp"
sh.CurrentDirectory = "D:\yige-personal-kb\xiaojuju"
sh.Run """D:\yige-personal-kb\xiaojuju\.venv\Scripts\python.exe"" scripts\run_agent_api.py --host 127.0.0.1 --port 12402", 0, False