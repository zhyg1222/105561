Set sh = CreateObject("WScript.Shell")
Set env = sh.Environment("PROCESS")
env("UV_CACHE_DIR") = "D:\yige-personal-kb\.runtime\uv-cache"
env("HF_HOME") = "D:\yige-personal-kb\.runtime\huggingface"
env("HUGGINGFACE_HUB_CACHE") = "D:\yige-personal-kb\.runtime\huggingface\hub"
env("TRANSFORMERS_CACHE") = "D:\yige-personal-kb\.runtime\huggingface\transformers"
env("TORCH_HOME") = "D:\yige-personal-kb\.runtime\torch"
env("HF_ENDPOINT") = "https://hf-mirror.com"
sh.CurrentDirectory = "D:\yige-personal-kb\xiaojuju\vendor\open-llm-vtuber"
sh.Run """D:\yige-personal-kb\xiaojuju\vendor\open-llm-vtuber\.venv\Scripts\python.exe"" run_server.py --verbose --hf_mirror", 0, False