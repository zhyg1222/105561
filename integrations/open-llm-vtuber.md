# Open-LLM-VTuber 集成

## 仓库位置

- Git 子模块：`vendor/open-llm-vtuber`
- 固定提交：`992309c0aa19845960228f880013d4685fde93b5`（v1.2.1）
- 许可证：MIT；Live2D 示例模型受单独的 Live2D 许可约束，商业使用前需重新核对。

## 已接线

- DeepSeek provider：`deepseek_llm`
- 模型：`deepseek-chat`
- 语音合成：Edge TTS，`zh-CN-XiaoxiaoNeural`
- Live2D：项目自带 `mao_pro`
- MCP：`time`、`ddg-search`
- 人格：小居居人格核心、关系规则和联网规则
- API Key：只写入被 `.gitignore` 排除的私有 `conf.yaml`，不进入 Git

## 私有配置

```text
vendor/open-llm-vtuber/conf.yaml
```

该文件已由本机生成，必须保密。

## 启动

```powershell
wscript.exe D:\yige-personal-kb\xiaojuju\scripts\start_open_llm_vtuber.vbs
```

本地地址：

```text
http://127.0.0.1:12393
```

## 当前环境说明

- Python 3.10 独立环境由 uv 创建在子模块目录。
- 当前电脑为 8GB 内存、无独立显卡，适合做 720p 本地预览，不适合 24 小时高质量直播。
- 默认 SherpaONNX SenseVoice ASR 模型首次启动约 1GB，会在本机下载。
- 正式直播前应评估专用主机或云端运行。