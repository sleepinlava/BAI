# MCP 2026-07-28 与 ABI MCP 适配研究

> 调研日期：2026-08-01
> 范围：MCP 官方规范、官方 Python SDK 文档及官方仓库；不使用二手资料。

## 结论

截至调研日，MCP 的正式最新版是 **2026-07-28**，不是此前的 2025-11-25；官方
Python SDK 的最新稳定主线是 **v2.0.0**，同日发布，支持 2026-07-28 以及所有更早的
协议版本。`pip install mcp` 已默认安装 2.x。[规范发布记录](https://github.com/modelcontextprotocol/modelcontextprotocol/releases/tag/2026-07-28)
和 [Python SDK v2.0.0 发布记录](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.0.0)
均对此作了明确说明。

ABI 当前把 MCP 保持为调用 `ABIAgentInterface` 的薄 stdio 适配器，这个边界设计仍然
正确。必须更新的是 Python SDK v2 API 和测试；协议握手、版本协商及逐请求元数据应交给
官方 SDK。建议先完成等价迁移，再单独评估结构化结果、资源/提示和 Streamable HTTP，
不要把第二阶段能力扩展混入机械迁移。

## 与 2025-11-25 相比的协议变化

官方的完整权威摘要见 [2026-07-28 changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog)。
对 Python MCP server/plugin 最重要的变化如下。

### 生命周期、版本与能力

- 协议核心改为无状态：删除 `initialize` / `notifications/initialized`、协议级 session
  以及 `Mcp-Session-Id`。服务器不得依赖同一连接上的前序请求。
- 每个请求在 `_meta` 中携带
  `io.modelcontextprotocol/protocolVersion` 和
  `io.modelcontextprotocol/clientCapabilities`；客户端每次请求 SHOULD 携带
  `clientInfo`，服务器每个结果 SHOULD 携带 `serverInfo`。
- 服务器 MUST 实现 `server/discover`，公布支持的版本、能力和身份；兼容新旧协议的 stdio
  客户端应先探测，现代探测失败后才回退到旧版 `initialize`。同一个 SDK v2
  `MCPServer` 可兼容旧客户端，因此 ABI 不应自行实现握手兼容层。
- `ClientCapabilities` 和 `ServerCapabilities` 新增 `extensions`；实验性功能可以通过
  扩展协商，不再继续塞入核心协议。

来源：[基础协议与无状态规则](https://modelcontextprotocol.io/specification/2026-07-28/basic/index)、
[版本与兼容性](https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning)、
[服务器发现](https://modelcontextprotocol.io/specification/2026-07-28/server/discover)、
[stdio 兼容探测](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio)。

### JSON-RPC、结果与错误

- 仍严格使用 JSON-RPC 2.0。请求 ID 必须是字符串或整数、不能为 `null`，同一发送方的
  未完成请求 ID 不得重复；notification 不得带 ID，也不得返回 response。
- 2026-07-28 不再允许服务器发起 JSON-RPC request。sampling、elicitation、roots 等
  服务器向客户端索取输入的场景改为 MRTR：服务器先返回
  `InputRequiredResult(resultType="input_required")`，客户端以新 JSON-RPC ID、原方法和
  `inputResponses` 重试。
- 所有普通成功结果新增必需的 `resultType: "complete"`；为兼容旧服务器，客户端遇到
  缺省字段时按 `complete` 处理。
- 标准 JSON-RPC 错误仍为 `-32700`、`-32600` 至 `-32603`。MCP 规范保留
  `-32020..-32099`：`HeaderMismatch=-32020`、
  `MissingRequiredClientCapability=-32021`、
  `UnsupportedProtocolVersion=-32022`。资源不存在由旧 `-32002` 改为
  `-32602 Invalid Params`。
- 工具执行的“业务失败”应返回 `CallToolResult(isError=true)`，让模型可读；真正的协议、
  权限或参数错误才使用 JSON-RPC error。ABI 迁移时应保留这一区分。

来源：[基础消息与错误规则](https://modelcontextprotocol.io/specification/2026-07-28/basic/index)、
[MRTR](https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/mrtr)、
[工具错误处理](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)。

### Tools、Resources 与 Prompts

- 服务器只应声明实际实现的能力。ABI 目前只暴露 tools，继续只声明 tools 完全合规；
  不需要为了“协议完整”空置 resources 或 prompts。
- `tools/list`、`resources/list`、`resources/templates/list`、`prompts/list` 使用不透明 cursor
  分页。客户端不能解析 cursor，空字符串也是有效 cursor；无 `nextCursor` 才表示结束。
- 上述 list 结果以及 `resources/read` 必须带 `ttlMs` 和
  `cacheScope`（`public`/`private`）。工具列表 SHOULD 使用确定顺序，既利于缓存，也利于
  LLM prompt cache。
- 工具的 `inputSchema`/`outputSchema` 现在允许完整 JSON Schema 2020-12 关键字；
  `structuredContent` 可为任意 JSON 值。实现须限制 `$ref`、组合关键字、深度和验证耗时，
  且不能任意抓取外部 `$ref`。
- 工具可带 `title`、`icons`、`annotations` 和 `outputSchema`；annotations 只是非可信提示，
  不能替代 ABI 自己的 `safe/full/management` 权限和确认门禁。
- Streamable HTTP 下可用 `x-mcp-header` 把 primitive 工具参数镜像成
  `Mcp-Param-*` 路由头；规范明确建议不要镜像敏感参数。ABI 当前 stdio 不需要它。
- tools、resources、prompts 的 catalog 变化统一通过 `subscriptions/listen` 订阅流通知。
  ABI 每个进程启动时 catalog 固定，因此无需实现动态 `listChanged`，除非以后支持运行时
  热插拔。

来源：[Tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)、
[Resources](https://modelcontextprotocol.io/specification/2026-07-28/server/resources)、
[Prompts](https://modelcontextprotocol.io/specification/2026-07-28/server/prompts)、
[Pagination](https://modelcontextprotocol.io/specification/2026-07-28/server/utilities/pagination)、
[订阅与通知](https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/subscriptions)。

### stdio 与 Streamable HTTP

- stdio 保持一行一个 UTF-8 JSON-RPC message；消息不得内含换行；stdout 只能写协议消息，
  任意诊断日志必须写 stderr。stdin EOF 是主要的优雅退出信号。
- 现代 stdio 请求的版本和能力全部在 JSON body `_meta` 中。取消仍通过
  `notifications/cancelled`；服务器应尽快停止，且不得再为已取消请求发消息。
- 2026-07-28 Streamable HTTP 只有单一 **POST** MCP endpoint，删除 GET stream、DELETE
  session、session ID、SSE event ID 和 `Last-Event-ID` 恢复。每个 request 独立返回单个
  JSON 或 request-scoped SSE；流中最后是 response。
- 每个 HTTP POST 必带 `MCP-Protocol-Version` 和 `Mcp-Method`；`tools/call`、
  `resources/read`、`prompts/get` 还必须带 `Mcp-Name`，并与 body 对应字段一致。
- HTTP 取消通过关闭该请求的 SSE response stream 表达，不发送
  `notifications/cancelled`。断流后没有重放；重试必须使用新的 request ID。
- Streamable HTTP 必须验证 `Origin`，本地服务应只绑定 `127.0.0.1`，生产服务应认证所有
  连接。旧 HTTP+SSE 已正式 deprecated。

来源：[stdio](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio)、
[Streamable HTTP](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http)。

### 进度、取消、日志与长任务

- 请求方仍可在 `_meta.progressToken` 请求进度；服务端用
  `notifications/progress` 回报，progress 必须单调增加并在请求完成后停止。通知应限流。
- request-scoped progress 与 log notification 只走所属 request 的 response stream，不能
  放到 `subscriptions/listen`。
- 所有请求都 SHOULD 有可配置的逐请求 timeout；即使 progress 持续到达，也 SHOULD 保留
  不可无限延长的最大 timeout，避免资源耗尽。
- 删除 `logging/setLevel`。2026-07-28 通过每次请求的
  `_meta.io.modelcontextprotocol/logLevel` 选择日志级别；请求未带该字段时，服务器 MUST
  NOT 发 `notifications/message`。Logging、Roots、Sampling 均已 deprecated；新服务优先
  使用 stderr/OpenTelemetry、显式工具参数/资源 URI 和直接的模型提供方 API。
- 2025-11-25 的实验 Tasks 已从核心移到官方 `io.modelcontextprotocol/tasks` 扩展并重新
  设计。Python SDK v2.0.0 尚未实现该扩展，因此 ABI 当前不要基于它改造工作流执行；继续
  使用现有 Job Service/执行 envelope，待 SDK 后续 2.x 明确支持后再评估。

来源：[Progress](https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/progress)、
[Cancellation](https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/cancellation)、
[Logging](https://modelcontextprotocol.io/specification/2026-07-28/server/utilities/logging)、
[弃用清单](https://modelcontextprotocol.io/specification/2026-07-28/deprecated-features)、
[Python SDK v2.0.0 known gaps](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.0.0)。

### 认证与安全

- MCP OAuth 授权是 HTTP transport 的可选能力；stdio SHOULD NOT 走这套流程，而应从进程
  环境取得凭据。ABI 目前只有 stdio，因此本轮 SDK 迁移无需引入 OAuth。
- 未来若增加远程 HTTP：资源服务器必须发布 RFC 9728 Protected Resource Metadata，
  客户端通过 RFC 8414 或 OIDC Discovery 找授权服务器，并在 authorization 和 token
  请求都带 RFC 8707 `resource`。
- 服务器必须验证 access token 的 audience，禁止把收到的 MCP token 透传给下游服务；
  401 表示无效/缺失 token，403 + `WWW-Authenticate` 用于 `insufficient_scope` 增量授权。
- 客户端必须校验 RFC 9207 `iss`（存在时），将注册凭据按授权服务器 issuer 隔离，issuer
  变化时重新注册，并声明适当的 OIDC `application_type`。
- OAuth Dynamic Client Registration 已 deprecated；新客户端优先使用 Client ID Metadata
  Documents。

来源：[MCP Authorization](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization)、
[MCP Security Best Practices](https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices)。

## Python SDK v2 API 对 ABI 的直接影响

官方 [v1 → v2 迁移指南](https://py.sdk.modelcontextprotocol.io/migration/)
列出了所有破坏性变化。ABI 直接命中的项目是：

| ABI 当前用法 | SDK v2 用法/行为 | 处理 |
|---|---|---|
| `from mcp.server.fastmcp import FastMCP` | `from mcp.server.mcpserver import MCPServer`（也可从 `mcp.server` 导入） | 必改 |
| `FastMCP("abi")` | `MCPServer("abi", version=<ABI version>)` | 必改；明确报告 ABI 版本 |
| `mcp>=1.28,<2` | v2 稳定线，建议初始锁为 `mcp>=2.0,<3` | 必改并重新构建 wheel |
| `@mcp.tool()` | decorator 基本用法保留 | 工具工厂可小改迁移 |
| Python protocol fields 为 camelCase | Python 属性改 snake_case；wire 序列化用 alias | 手工类型/测试需排查 |
| `McpError` | `MCPError` | 若使用则改名 |
| 隐式 SDK 包版本作为 server version | 未传版本时报告空字符串 | 显式传 ABI 包版本 |
| 同步 handler 在 event loop 执行 | 同步 handler 在 worker thread 执行 | 核对 contextvars/线程局部状态 |
| 宽松 handler 返回与异常处理 | server/client 严格校验 schema；`MCPError` 才是 JSON-RPC error | 增加 wire 级测试 |

此外，协议类型拆到与 `mcp` 精确同版本的 `mcp-types` 包；`mcp.types` 保留兼容 alias，但新
代码可直接从 `mcp_types` 导入。v2 的高层 `Client(target)` 默认自动探测现代协议并回退旧版；
ABI 是服务端，不需要自行复制这一逻辑。官方 SDK v2 支持 Python 3.10+，与 ABI 当前最低
版本一致。[SDK README](https://github.com/modelcontextprotocol/python-sdk#readme)

## ABI 的建议实施顺序

### P0：完成等价 SDK v2 迁移

1. 将 optional dependency 改为 `mcp>=2.0,<3`，同步 package/build 文档。
2. 将 `FastMCP` import、变量和测试 fake 迁移为 `MCPServer`，创建服务时传 ABI 自身版本。
3. 保持 `abi-mcp --profile ...` 和 `transport="stdio"` 行为不变；不要手写
   `server/discover`、逐请求 `_meta`、`resultType` 或旧协议回退，它们属于 SDK。
4. 用真实 SDK 增加 stdio wire 集成测试：发现/兼容协商、`tools/list`、`tools/call`、
   JSON-RPC error、取消、stdout 纯净度和 stdin EOF 退出。现有 `FakeMCP` 单元测试只能验证
   注册集合，不能证明协议合规。
5. 运行 Ruff、mypy、MCP 单元/集成测试、package build 和 clean-wheel `[mcp]` smoke test。

### P1：补齐 MCP 元数据和结构化返回

1. 将 SSOT 中已有的 `read_only` 和权限属性映射为 MCP tool annotations，并补充
   `destructiveHint`、`idempotentHint`、`openWorldHint`；安全门禁仍由 ABI core 强制。
2. 为 ABI envelope 建立输出 JSON Schema，让 MCP tool 返回
   `structuredContent`，同时保留简短 text content 兼容只读文本的 host。当前“JSON 字符串
   作为 text”仍然合法，但会失去 SDK v2 的结果校验和结构化消费优势。
3. 保证工具注册顺序确定，并针对 safe/full/management 三种启动时静态 catalog 验证
   capability/list 结果。catalog 不热变时不要声明 `listChanged=true`。

### P2：独立评估新能力

- 如果希望 Agent 可浏览插件说明、limitations、report manifest，可把稳定、只读、可寻址
  内容设计为 MCP resources；交互模板才设计为 prompts。二者不是迁移 v2 的前置条件。
- 如果远程部署确有需求，再新增 Streamable HTTP 入口，并同时完成 Origin 校验、OAuth、
  body size、超时、反向代理 SSE buffering 和无状态横向扩容设计；不要把 `safe` profile
  当作 HTTP 认证。
- Tasks extension 暂缓，直到官方 Python SDK 支持；ABI 长任务继续使用 transport-neutral
  Job Service。

## 当前 ABI 差距快照

- `src/abi/mcp/server.py` 仍导入 `mcp.server.fastmcp.FastMCP`。
- `pyproject.toml` 仍锁定 `mcp>=1.28,<2`。
- `_tool_factory.py` 只通过签名让 SDK 推导 input schema，返回类型固定为 `str`；尚未输出
  `CallToolResult`/`structuredContent` 或 output schema。
- `tool_descriptors.py` 的 provider export 已有 `title` 和 `readOnlyHint`，但 MCP 注册路径未把
  这些元数据传给 `@mcp.tool()`。
- 当前仅有 stdio 入口，这与本轮最小迁移目标一致，也避免了在未实现 HTTP auth/security
  前意外暴露远程服务。

以上快照用于指导实现，不意味着要在同一提交中完成 P0、P1、P2。
