Set sh = CreateObject("WScript.Shell")
Set env = sh.Environment("PROCESS")
env("UV_CACHE_DIR") = "D:\yige-personal-kb\.runtime\uv-cache"
env("HF_HOME") = "D:\yige-personal-kb\.runtime\huggingface"
env("TMP") = "D:\yige-personal-kb\.runtime\tmp"
env("TEMP") = "D:\yige-personal-kb\.runtime\tmp"
sh.CurrentDirectory = "D:\yige-personal-kb\xiaojuju"
sh.Run """D:\yige-personal-kb\.runtime\wechat-operator\.venv\Scripts\python.exe"" run_brain_gateway.py --host 127.0.0.1 --port 12400", 0, True