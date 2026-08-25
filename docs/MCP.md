# MCP server：hs-err-jbs-analyzer

本目录下的 `tools/hs_err_mcp_server.py` 把任务 1.2 的崩溃日志分析流程封装成
**Model Context Protocol（MCP）server**，任何 MCP 客户端（WorkBuddy、Claude Code、
其他支持 MCP 的 AI 工具）都可以直接调用，对应任务 1.2 子项"创建 MCP server"。

## 提供的工具

| 工具 | 说明 | 返回 |
|---|---|---|
| `parse_hs_err(file_path)` | 解析一份 hs_err 崩溃日志 | 结构化字段（崩溃类型/直接原因/崩溃线程/故障地址/断言消息/版本/JBS 检索提示） |
| `search_jbs(query, version, max_results)` | 检索 bugs.openjdk.org 上的已知 issue，支持 `affectedVersion` 版本约束 | `{"query", "version", "count", "results"}` |
| `analyze_hs_err(file_path, max_results)` | 完整流程：解析 + 联机关联 JBS + 生成带建议的报告 | Markdown 报告 |

设计要点：

- 复用 `tools/parse_hs_err.py` 的 `parse_log()`，保证与 CLI 解析结果一致。
- `search_jbs` 建议带上 `version` 参数（来自日志的 `java_version`）做版本约束——
  纯关键词检索可能命中上百条同类型 issue，加版本约束后通常能收敛到具体 bug
  （实测 `bad AD file` 由 461 条收敛到唯一命中）。
- `analyze_hs_err` 网络失败时自动降级为仅本地解析，不中断。

## 与 skills/ 的分工

本仓库同时提供同名 Agent Skill（`skills/hs-err-jbs-analyzer/`）。二者关系：

- `tools/` 是**工具本体**：MCP server 与解析器、单测都在此，受 CI 覆盖，本文件配置的
  运行入口就是 `tools/hs_err_mcp_server.py`。
- `skills/` 是**给 AI 用的便携封装**：SKILL.md 教 AI 按"解析→原因→JBS 关联→建议"
  工作流执行，自带 `parse_hs_err.py` / `analyze_hs_err.py` 副本与样例日志，拷到
  `~/.workbuddy/skills/` 即装即用，不依赖仓库其他路径。
- 两处 `parse_hs_err.py` 保持同步：**改动以 `tools/` 版本为准（CI 验证），改完覆盖
  skill 的 `scripts/` 副本**。

## 安装依赖

```bash
pip install "mcp>=1.0"
```

本项目使用 mcp 2.x（`mcp.server.mcpserver.MCPServer` 接口）。

## 运行

```bash
python tools/hs_err_mcp_server.py
```

默认使用 stdio 传输（MCP server 标准方式），由客户端拉起，无需手动运行。

## 客户端配置

**WorkBuddy**（`~/.workbuddy/mcp.json`，在连接器管理页面启用并 Trust）：

```json
{
  "mcpServers": {
    "hs-err-jbs-analyzer": {
      "command": "<python 解释器路径，建议用装了 mcp 包的虚拟环境>",
      "args": ["<本仓库>/tools/hs_err_mcp_server.py"]
    }
  }
}
```

**Claude Code**（`claude mcp add`）：

```bash
claude mcp add hs-err-jbs-analyzer -- python tools/hs_err_mcp_server.py
```

## 自测

```bash
python tools/test_mcp_server_e2e.py
```

端到端测试会用 stdio 协议真实拉起 server，验证三个工具：
解析 `jdk-8314225.log` 得到正确直接原因、`search_jbs` 版本约束检索命中
JDK-8314225、`analyze_hs_err` 对 `jdk-8312741.log` 生成含 JDK-8312741 候选与
修复版本建议的报告。
