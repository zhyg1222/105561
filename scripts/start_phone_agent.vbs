Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = "D:\yige-personal-kb\xiaojuju\apps\phone_agent"
sh.Run """D:\yige-personal-kb\.runtime\wechat-operator\.venv\Scripts\python.exe"" phone_agent.py --loop", 0, False