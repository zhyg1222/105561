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
- 默认 SenseVoice 模型约 1GB，在 Windows 上下载失败；已改用 ModelScope 的 `Systran/faster-whisper-base`（约 138MB），保存在 D 盘模型目录。
- 正式直播前应评估专用主机或云端运行。
## D 盘缓存

- D:\yige-personal-kb\.runtime\uv-cache：uv 包缓存
- D:\yige-personal-kb\.runtime\huggingface：Hugging Face 缓存
- D:\yige-personal-kb\.runtime\torch：Torch 缓存
- endor/open-llm-vtuber/models/faster-whisper-base：本地 ASR 模型

## 开源状态（重要）

- DeepSeek Harness：MIT，开源。
- Open-LLM-VTuber：MIT，开源；Live2D 示例模型另有许可。
- Faster-Whisper：MIT；当前 Whisper base 模型为 MIT。
- Sherpa-ONNX：Apache 许可，开源；当前中文 VITS 模型由社区训练，仓库未给出清晰的统一商用许可证，正式商用前需单独核实。
- 当前 TTS：`sherpa-onnx-vits-zh-ll`，本地 CPU 离线运行，不再使用 Edge TTS。
- DeepSeek 模型：当前通过官方 API 调用，模型服务本身不是完全本地/开源部署。
- Live2D Cubism 运行时和示例形象：不是完全开源，商业直播前必须取得相应许可或替换为自建可用形象。
- 本项目主仓库目前没有添加 LICENSE 文件，因此还不能宣称自身代码已正式开源。

## 自然对话

- 已使用独立的直播短对话提示词 `prompts/live_persona.md`。
- 不再把完整制度文件塞入每次对话提示。
- 真实 WebSocket 测试：输入“介绍一下自己”，返回两句短回复并成功生成两段音频。