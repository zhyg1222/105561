Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = "D:\yige-personal-kb\xiaojuju"
sh.Run """D:\yige-personal-kb\.runtime\wechat-operator\.venv\Scripts\python.exe"" run_autonomy.py --once", 0, False