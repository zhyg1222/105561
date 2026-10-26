# Agent Platform Operations Runbook

> 闁倻鏁ょ拋鈥冲灊閿涙瓪docs/superpowers/plans/2026-10-26-01-agent-platform-foundation.md`
> 瑜版挸澧犻梼鑸殿唽閿涙艾濂栫€涙劘绻嶇悰宀嬬礉缁備焦顒涢惇鐔风杽閸欐垿鈧?

## 1. 閸撳秶鐤嗛弶鈥叉

- Windows 瀹告彃鎯庨悽?`Microsoft-Windows-Subsystem-Linux`閵?
- Windows 瀹告彃鎯庨悽?`VirtualMachinePlatform`閵?
- 娑撳﹨鍫崝鐔诲厴閸氼垳鏁ら崥搴＄箑妞ゅ鍣搁崥顖欑濞喡扳偓?
- 闁插秴鎯庨崥搴＄暔鐟?Docker Desktop閿涘苯鑻熺亸?Docker data-root 閸?`XJJ_STACK_DATA` 閹稿洤鎮?D 閻╂ǜ鈧?
- 閺堫剟銆嶉惄顔诲▏閻?Python 3.12 閸?`uv`閵?

濡偓閺屻儻绱?

```powershell
wsl --status
docker version
uv --version
```

## 2. 閸氼垰濮╅崺铏诡攨鐠佺偓鏌?

```powershell
Copy-Item deploy/compose/.env.example deploy/compose/.env
docker compose -f deploy/compose/compose.yaml --env-file deploy/compose/.env up -d
docker compose -f deploy/compose/compose.yaml --env-file deploy/compose/.env ps
```

鐟曚焦鐪?Postgres閵嗕箓alkey閵嗕腐eo4j閵嗕副PA 閸忋劑鍎存稉?`healthy`閵?

## 3. 闁板秶鐤?Agent

```powershell
Copy-Item deploy/agent.env.example deploy/agent.env
```

婵夘偄鍟撻敍?

- `XJJ_DATABASE_URL`
- `XJJ_VALKEY_URL`
- `XJJ_OPA_URL`
- `XJJ_DEEPSEEK_API_KEY`
- `XJJ_IDENTITY_DIR`
- 閸欘垶鈧绱癭XJJ_OTEL_EXPORTER_OTLP_ENDPOINT`

`deploy/agent.env` 娑撳秴绶辨潻娑樺弳 Git閵?

閸旂姾娴囬悳顖氼暔閿?

```powershell
Get-Content deploy/agent.env | ForEach-Object {
  if ($_ -and -not $_.StartsWith('#')) {
    $name, $value = $_ -split '=', 2
    Set-Item -Path "Env:$name" -Value $value
  }
}
```

## 4. 閹笛嗩攽鏉╀胶些

```powershell
uv run python scripts/migrate_platform.py
```

鏉╀胶些閸欘亜鍨卞鐑樺灗鐞涖儵缍堥獮鍐插酱鐞涱煉绱濇稉宥呭灩闂勩倗骞囬張澶嬫殶閹诡喓鈧?

## 5. 閸氼垰濮?Agent 娑?Worker

缂佸牏顏?A閿?

```powershell
uv run python scripts/run_agent_api.py --host 127.0.0.1 --port 12400
```

缂佸牏顏?B閿?

```powershell
uv run celery -A xiaojuju_agent.queue_app.celery_app worker --pool=solo --loglevel=INFO
```

閸嬨儱鎮嶅Λ鈧弻銉窗

```powershell
Invoke-RestMethod http://127.0.0.1:12400/healthz
Invoke-RestMethod http://127.0.0.1:12400/readyz
```

鐟曚焦鐪伴敍姝歨ealthz=ok`閿涘畭readyz=ready`閵?

## 6. 瑜板崬鐡欓崶鐐存杹

閸ョ偞鏂侀崜宥堫唶瑜?outbox閿?

```powershell
docker compose -f deploy/compose/compose.yaml --env-file deploy/compose/.env exec -T postgres psql -U xiaojuju -d xiaojuju -c "select count(*) from app_outbox;"
```

閹笛嗩攽閿?

```powershell
uv run python scripts/replay_shadow.py `
  --input tests/fixtures/shadow_sample.jsonl `
  --output D:/yige-personal-kb/.runtime/agent-shadow/result.jsonl
```

閸愬秵顐奸弻銉嚄 outbox閿涘本鏆熼柌蹇撶箑妞よ绗夐崣妯糕偓?

## 7. 閺佸懘娈扮拠顓濈疅

- Postgres 娑撳秴褰查悽顭掔窗`/v1/events` 鏉╂柨娲?503閿涙稐绗夐懗钘夊晸閸?SQLite 閹存牗濮ら崨濠冨灇閸旂喆鈧?
- OPA 娑撳秴褰查悽顭掔窗閹碘偓閺堝澹囨担婊呮暏瀹搞儱鍙?fail-closed閿涙硜eadiness 鏉╂柨娲?503閵?
- Valkey 娑撳秴褰查悽顭掔窗娴滃娆㈡潻娑樺弳婢惰精瑙?闁插秷鐦捄顖氱窞閿涘瘍orker 娑撳秳鍚夌憗鍛暚閹存劑鈧?
- Neo4j 娑撳秴褰查悽顭掔窗Plan 1 閺嗗倷绗夋笟婵婄閿涙备lan 2 閹?Graphiti 閸氬骸绻€妞ゅ妯嗛弬顓☆唶韫囧棙顥呯槐銏犺嫙鐠佹澘缍嶉梽宥囬獓閵?
- DeepSeek 鐡掑懏妞?缁屽搫娲栨径宥忕窗Celery 閺堝妾洪柌宥堢槸閿涙稖绉存潻鍥︾瑐闂勬劕鎮楁禍瀣╂閺嶅洩顔?failed閵?

## 8. 閸ョ偞绮?

Plan 1 閸欘亜浠涜ぐ鍗炵摍鏉╂劘顢戦妴鍌氭礀濠婃碍顒炴銈忕窗

1. 閸嬫粍顒涢弬?Agent API 閸?worker閵?
2. 娑撳秴鍨归梽銈嗘煀閺佺増宓佹惔鎿勭礉娣囨繄鏆€鐎孤ゎ吀閸滃苯娲栭弨鍓х波閺嬫嚎鈧?
3. 缂佈呯敾娴ｈ法鏁ら弮?`run_brain_gateway.py` 閸滃瞼骞囬張澶婂絺闁線鎽肩捄顖樷偓?
4. 閸欘亝婀侀崷銊︽＋闁炬崘鐭炬稊鐔蜂粻濮濄垹鎮楅敍灞惧閸欘垱鏆ｆ担鎾充粻濮?Compose閵?

## 9. 閺佺増宓佺€电厧鍤?

Postgres閿?

```powershell
New-Item -ItemType Directory -Force D:/yige-personal-kb/.runtime/backups | Out-Null
docker compose -f deploy/compose/compose.yaml --env-file deploy/compose/.env exec -T postgres pg_dump -Fc -f /tmp/xiaojuju-agent.dump -U xiaojuju -d xiaojuju
docker compose -f deploy/compose/compose.yaml --env-file deploy/compose/.env cp postgres:/tmp/xiaojuju-agent.dump D:/yige-personal-kb/.runtime/backups/xiaojuju-agent.dump
```

Plan 1 娑撳秵甯?Neo4j 鐠佹澘绻傞弫鐗堝祦閿涘苯娲滃銈嗘拱闂冭埖顔屽▽鈩冩箒 Neo4j 娑撴艾濮熺€电厧鍤妴?

## 10. 缁備焦顒涙禍瀣€?

- 娑撳秳濞囬悽?`latest` 闂€婊冨剼閹存牔绶风挧鏍モ偓?
- 娑撳秵濡?`deploy/compose/.env`閵嗕梗deploy/agent.env`閵嗕浇浜版径鈺傤劀閺傚洦褰佹禍銈呭煂 Git閵?
- 娑撳秴婀ぐ鍗炵摍濡€崇础閸氭垹婀＄€圭偛浜曟穱掳鈧胶娲块幘顓溾偓浣圭セ鐟欏牆娅掗幋鏍ㄥ閺堝搫褰傞柅浣碘偓?
- 娑撳秹鈧俺绻冩穱顔芥暭 Prompt 缂佹洝绻?OPA閵?
- 娑撳秴婀張顏勭暚閹存劗婀＄€圭偞鏁归崣鎴︾崣閺€鑸垫鐎癸絿袨閹靛婧€闁炬崘鐭鹃崣顖滄暏閵?
