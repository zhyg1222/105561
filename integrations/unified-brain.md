# 统一大脑流程

## 入口

- 微信：`POST http://127.0.0.1:12400/v1/respond`
- Open-LLM-VTuber：`POST http://127.0.0.1:12400/v1/chat/completions`
- 自主任务：在独立 daemon 中执行，结果写入同一知识库

## 事件结构

```json
{
  "event_id": "唯一编号",
  "source": "wechat/live/text/mic",
  "user_id": "联系人编号",
  "scope": "private/public/internal",
  "text": "输入",
  "history": [],
  "timestamp": "本地时间"
}
```

## 处理顺序

1. 事件去重。
2. 更新小居居状态。
3. 按来源读取隔离的长期记忆。
4. 让 DeepSeek 输出内部反应决策和最终短回复。
5. 如果决策需要最新信息，调用 AnySearch，再生成最终回复。
6. 写回关系记忆与行为审计。
7. 将短回复交给微信或 TTS/Live2D。

## 兼容接口

Open-LLM-VTuber 使用 OpenAI 兼容的 Chat Completions 接口，所以不需要修改其前端。它只负责语音和 Live2D，人格、记忆和决策由 Brain Gateway 负责。

## 服务

- Brain Gateway：`127.0.0.1:12400`
- Open-LLM-VTuber：`127.0.0.1:12393`
- 健康检查：`GET http://127.0.0.1:12400/health`