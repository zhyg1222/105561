# Social Publishing Architecture Decision

> Date: 2026-10-27  
> Goal: give the Agent a real, auditable social publishing path without recreating brittle platform selectors.

## What was investigated

- `dreammis/social-auto-upload`: MIT, about 15.8k GitHub stars, Python CLI (`sau`), supports Douyin, Xiaohongshu, WeChat Channels and other platforms. It already contains login/cookie handling, upload flows, platform selectors and success-page waits.
- `browser_action`: useful for research and approvals, but reimplementing every creator-center selector would be fragile and expensive.
- The project already has Postgres approvals, OPA policy, audit receipts and a local Agent API.

## Decision

Use a thin adapter around `social-auto-upload` rather than copying its selector code:

1. Keep the upstream checkout in `.runtime/social-auto-upload`.
2. Make `SauCliProvider` build a constrained command line, enforce media-root boundaries, and prepend the AI identity label.
3. Route all publish calls through `social.publish` in OPA; no approval means no subprocess.
4. Store stdout/stderr, command outcome and page-verification screenshots under `.runtime/social-publish/receipts`.
5. Use a small verifier with the saved login state to look for the title/body on the platform management page. A CLI exit zero alone is only `submitted`, not `published`.

## Why not a new platform SDK

Platform APIs are private, signed and unstable for personal creator accounts. The upstream project is a maintained MIT implementation of the browser path. The adapter isolates that dependency behind a stable `publish` contract, so it can be replaced later.

## Remaining constraints

- A real account must complete the QR login once per platform.
- Platform DOM changes can break upstream selectors; the receipt and screenshot make that visible.
- Automatic verification can distinguish `published`, `scheduled`, `submitted` and `unverified`; it must never silently re-send after an unknown result.
- Cookies and QR login artifacts stay outside Git.