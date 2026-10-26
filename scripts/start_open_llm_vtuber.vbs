Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = "D:\yige-personal-kb\xiaojuju\vendor\open-llm-vtuber"
sh.Run """D:\yige-personal-kb\xiaojuju\vendor\open-llm-vtuber\.venv\Scripts\python.exe"" run_server.py --verbose", 0, False