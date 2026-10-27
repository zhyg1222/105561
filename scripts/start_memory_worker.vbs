Set sh = CreateObject("WScript.Shell")
Set env = sh.Environment("PROCESS")
env("PYTHONPATH") = "D:\yige-personal-kb\xiaojuju\src"
env("XJJ_SHADOW_MODE") = "false"
env("XJJ_DEEPSEEK_API_KEY") = sh.ExpandEnvironmentStrings("%DEEPSEEK_API_KEY%")
env("XJJ_GRAPHITI_ENABLED") = "true"
env("XJJ_NEO4J_URI") = "neo4j://127.0.0.1:7687"
env("XJJ_NEO4J_USER") = "neo4j"
env("XJJ_NEO4J_PASSWORD") = "xjj-dev-neo4j"
env("TMP") = "D:\yige-personal-kb\.runtime\agent-tests\tmp"
env("TEMP") = "D:\yige-personal-kb\.runtime\agent-tests\tmp"
sh.CurrentDirectory = "D:\yige-personal-kb\xiaojuju"
sh.Run """D:\yige-personal-kb\xiaojuju\.venv\Scripts\python.exe"" scripts\run_memory_worker.py", 0, False
