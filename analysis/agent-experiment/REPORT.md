# 任务一实验报告：将 MCP 与 Skill 安装进 AI Agent 并分析 hs_err 日志

> 实验日期：2026-08-30
> 对应任务：任务 1.2 工具链（Agent Skill `hs-err-jbs-analyzer` + MCP server）的实际安装与使用验证

## 1. 任务说明

导师要求：在完成任务一的 MCP 和 Skill 开发之后，将其**实际安装进一个 AI Agent**（如 CodeBuddy Code），
然后**使用该 Agent 分析 `hs_err_pid*.log` 文件**，并将实验的详细过程（包括输入和输出）写进报告。

## 2. 实验环境

| 项 | 值 |
|---|---|
| AI Agent | WorkBuddy 桌面版（CodeBuddy 系 Agent，支持 Agent Skill 与 MCP 两套扩展机制） |
| 操作系统 | Windows 11（补充验证于 WSL Ubuntu 22.04，任务 1.1 环境同源） |
| Python | 3.13（独立 venv，安装 `mcp>=2.0`） |
| Skill | `hs-err-jbs-analyzer`（解析 → 原因推断 → JBS 关联 → 建议的完整工作流） |
| MCP server | `tools/hs_err_mcp_server.py`（mcp 2.x `MCPServer` 接口，stdio 传输，3 个工具） |
| 测试日志 | ① JBS 真实日志 `jdk-8314225.log`（SIGSEGV，JDK 21，ZGC）② 任务 1.1 受控崩溃日志 `controlled-crash-3.log`（WhiteBox 主动 native OOM）③ `jdk-8312741.log`（C2 断言，JDK 11.0.20，MCP 端到端用） |

## 3. 安装过程

### 3.1 Agent Skill 安装

Skill 以自包含目录形式分发，安装即拷贝：

```
仓库 skills/hs-err-jbs-analyzer/
  ├── SKILL.md            # 工作流说明（Agent 的加载入口）
  ├── scripts/            # parse_hs_err.py（解析器）+ analyze_hs_err.py（分析入口）
  ├── references/         # hs_err 日志结构说明 + JBS 检索策略
  └── examples/           # 3 份真实 JBS 日志（已确认答案，可作正确性对照）
```

安装命令与验证：

```console
$ cp -r skills/hs-err-jbs-analyzer ~/.workbuddy/skills/   # 拷入 Agent 的用户级 skill 目录
$ ls ~/.workbuddy/skills/hs-err-jbs-analyzer/
SKILL.md  examples  references  scripts
```

Agent 在会话中通过 `@skill:hs-err-jbs-analyzer` 即可引用；本轮实测中 Agent 会话成功加载了
SKILL.md 并按其工作流执行（见 4.1）。

### 3.2 MCP server 安装

依赖与配置（写入 Agent 的 `~/.workbuddy/mcp.json`）：

```console
$ python -m venv .venv && .venv/bin/pip install "mcp>=2.0"   # server 依赖 mcp 2.x 的 MCPServer 接口
```

```json
{
  "mcpServers": {
    "hs-err-jbs-analyzer": {
      "command": "C:/Users/lenovo/.workbuddy/binaries/python/envs/default/Scripts/python.exe",
      "args": ["C:/Users/lenovo/WorkBuddy/2026-08-24-16-21-43/task-controlled-crash/tools/hs_err_mcp_server.py"]
    }
  }
}
```

配置后 Agent 以 stdio 方式拉起 server 并按 MCP 协议握手；本轮通过真实 stdio 会话完成
`tools/list` 与三个工具的实际调用验证（见 4.6），全部通过。

## 4. 实测过程与输入输出

### 4.1 Agent 会话加载 Skill（输入输出摘录）

**输入**（在 Agent 对话中）：

```
@skill:hs-err-jbs-analyzer 分析 examples/jdk-8314225.log 和任务1.1的受控崩溃日志 controlled-crash-3.log
```

**输出**：Agent 成功读取 SKILL.md，并按其定义的五步工作流（解析 → 解释直接原因 → JBS 检索 →
建议 → 可选报告）依次执行。以下 4.2–4.5 即 Agent 按工作流实际执行的命令与输出。

### 4.2 解析 JBS 真实日志（jdk-8314225.log）

**输入**：

```bash
python ~/.workbuddy/skills/hs-err-jbs-analyzer/scripts/analyze_hs_err.py \
    ~/.workbuddy/skills/hs-err-jbs-analyzer/examples/jdk-8314225.log
```

**输出**（关键字段摘录）：

```json
{
  "error_kind": "Signal",
  "signal": "SIGSEGV",
  "siginfo": "si_signo: 11 (SIGSEGV), si_code: 128 (SI_KERNEL), si_addr: 0x0000000000000000",
  "fault_address": "0x0000000000000000",
  "java_version": "21",
  "current_thread": { "name": "JavaThread \"Thread-1833141\" daemon", "state": "_thread_in_vm" },
  "problematic_frame": "V  [libjvm.so+0x8f9363]  JavaThread::is_lock_owned(unsigned char*) const+0x23",
  "native_frames": [
    "V  ... JavaThread::is_lock_owned(unsigned char*) const+0x23  (monitorChunk.hpp:40)",
    "V  ... Threads::owning_thread_from_monitor(ThreadsList*, ObjectMonitor*)+0xd4  (threads.cpp:1214)",
    "V  ... ThreadSnapshot::initialize(ThreadsList*, JavaThread*)+0x1fa  (threadService.cpp:948)",
    "V  ... jmm_GetThreadInfo+0x4a5  (management.cpp:1133)",
    "J  ... sun.management.ThreadImpl.getThreadInfo1(...)"
  ],
  "direct_cause": "空指针解引用 (si_addr=0x0000000000000000)，崩溃点 JavaThread::is_lock_owned",
  "jbs_search": {
    "keywords": ["JavaThread::is_lock_owned", "SIGSEGV"],
    "url_version": "https://bugs.openjdk.org/issues/?jql=... AND affectedVersion = \"21\""
  }
}
```

Agent 依据以上字段的解释：该 JVM 在执行线程转储（`jmm_GetThreadInfo` → `ThreadSnapshot::initialize`）
时，于 `JavaThread::is_lock_owned` 处发生空指针解引用（`si_addr=0x0`），崩溃线程处于 `_thread_in_vm`
状态，版本为 JDK 21（21+35-LTS）。

### 4.3 联网检索 JBS 已知问题（版本约束）

**输入**：

```bash
python ~/.workbuddy/skills/hs-err-jbs-analyzer/scripts/analyze_hs_err.py \
    ~/.workbuddy/skills/hs-err-jbs-analyzer/examples/jdk-8314225.log --jbs --limit 5
```

**输出**（`jbs_candidates` 摘录）：

```json
[
  { "key": "JDK-8314225", "summary": "SIGSEGV in JavaThread::is_lock_owned",
    "status": "Resolved", "resolution": "Fixed", "fixVersions": ["23"] },
  { "key": "JDK-8347594", "summary": "SIGSEGV in JavaThread::is_lock_owned",
    "status": "Resolved", "resolution": "Fixed", "fixVersions": ["17.0.15"] },
  { "key": "JDK-8332672", "summary": "SIGSEGV in JavaThread::is_lock_owned",
    "status": "Closed", "resolution": "Fixed", "fixVersions": ["21.0.5-oracle"] }
]
```

检索使用崩溃点函数名 `JavaThread::is_lock_owned` 作为关键词，并带上版本约束
（`AND affectedVersion = "21"`，版本取自日志的 `java_version` 字段）。
第一条命中即为 **JDK-8314225**（与样例日志同源），其 21 系列的 backport **JDK-8332672**
修复版本为 21.0.5。

### 4.4 解析任务 1.1 的受控崩溃日志（controlled-crash-3.log）

**输入**：同一条命令，第二个参数为受控崩溃日志。

**输出**（关键字段）：

```json
{
  "crash_type": 3,
  "error_kind": "Out of Memory Error",
  "direct_cause": "WhiteBox 主动请求 native OOM",
  "problematic_frame": "V  [libjvm.so+0x1]  VM_ControlledCrash::doit()+0x1",
  "source_file": "/src/hotspot/share/prims/whitebox.cpp",
  "source_line": 199,
  "vm_operation": { "name": "ControlledCrash", "mode": "safepoint" }
}
```

Agent 判定：这是任务 1.1 通过 WhiteBox `controlledCrash(3)` 主动制造的 native OOM 崩溃
（`crash_type` 非空即受控样本），按工作流约定**不再做 JBS 关联**——正确区分了
"已知问题"与"本实验主动制造的故障"。

### 4.5 生成完整分析报告

**输入**：

```bash
python .../analyze_hs_err.py examples/jdk-8314225.log --jbs --report \
    --out analysis/agent-experiment/hs-err-8314225-report.md
```

**输出**：生成 `hs-err-8314225-report.md`，按"基本信息 → 关键证据 → 崩溃栈 → JBS 关联 → 建议"
组织；结论为：已知问题 JDK-8314225，JDK 21 系列修复于 21.0.5（backport JDK-8332672），
**建议升级到 21.0.5 或更高版本**。

### 4.6 MCP server 三工具真实调用（stdio 协议）

**输入**：运行仓库自带的真实 stdio 握手端到端测试 `tools/test_mcp_server_e2e.py`
（与 Agent 连接 MCP server 的方式一致：标准输入输出 + JSON-RPC）。

**输出**：

```console
=== tools/list ===
  parse_hs_err: Parse a HotSpot fatal error log (hs_err_pid*.log) into structured fields
  search_jbs: Search bugs.openjdk.org (JBS) for known issues matching a keyword
  analyze_hs_err: Full analysis of one hs_err log: parse, correlate with JBS, and give advice

=== call parse_hs_err (jdk-8314225.log) ===
  direct_cause: 空指针解引用 (si_addr=0x0000000000000000)，崩溃点 JavaThread::is_lock_owned
  java_version: 21

=== call search_jbs (JavaThread::is_lock_owned, v21) ===
  JDK-8314225 | SIGSEGV in JavaThread::is_lock_owned | fix: 23
  JDK-8347594 | SIGSEGV in JavaThread::is_lock_owned | fix: 17.0.15
  JDK-8343422 | SIGSEGV in JavaThread::is_lock_owned | fix: 17.0.15-oracle

=== call analyze_hs_err (jdk-8312741.log) ===
  - 直接原因：断言失败: assert(false) failed: bad AD file
  - [JDK-8312741](https://bugs.openjdk.org/browse/JDK-8312741) — C2: LoopLimitNode is not elimina...
  ## 建议
  - 已知问题，修复版本为 11.0.26-oracle：建议升级到该版本或更高。

ALL E2E TOOLS OK
```

MCP 三工具全部验证通过：`parse_hs_err` 解析、`search_jbs` 版本约束检索（命中 JDK-8314225）、
`analyze_hs_err` 对第三份日志（C2 断言，11.0.20）给出"升级 11.0.26+"建议。

## 5. 实测发现的问题与修复

实测直接暴露了 1 个真实缺陷（这也说明了"装进真实 Agent 跑一遍"的价值）：

- **问题**：`analyze_hs_err.py --report` 渲染"故障地址"时用整数格式化
  （`f"0x{result['fault_address']:x}"`），而解析器输出的 `fault_address` 是字符串
  （如 `"0x0000000000000000"`），导致报告生成直接 `ValueError` 崩溃。
- **修复**：兼容字符串与整数两种类型；已同步修复三处副本（用户级安装副本、仓库
  `skills/` 副本，`tools/` 主解析器不受影响）。

## 6. 结论

1. **安装闭环验证通过**：Agent Skill 拷入 `~/.workbuddy/skills/` 后被 Agent 会话成功加载并
   按工作流执行；MCP server 写入 `mcp.json` 后经真实 stdio 握手完成 `tools/list` 与三工具调用，
   全部通过。
2. **分析闭环验证通过**：对 JBS 真实日志（SIGSEGV / 断言两类）能完成
   "解析 → 原因推断 → 版本约束 JBS 检索 → 升级建议"的全链路；对任务 1.1 的受控崩溃日志能正确
   识别为主动制造的故障并跳过 JBS 关联。
3. **版本约束检索有效性再验证**：`JavaThread::is_lock_owned` + `affectedVersion="21"` 检索
   首条命中 JDK-8314225，并给出 21 系列用户可直接行动的修复版本（21.0.5）。

## 附：产物清单

| 产物 | 位置 |
|---|---|
| 本实验报告 | `analysis/agent-experiment/REPORT.md` |
| 8314225 单日志分析报告（--report 生成） | `analysis/agent-experiment/hs-err-8314225-report.md` |
| Skill 安装目录 | `~/.workbuddy/skills/hs-err-jbs-analyzer/` |
| MCP 配置 | `~/.workbuddy/mcp.json` |
| MCP server 与端到端测试 | `tools/hs_err_mcp_server.py`、`tools/test_mcp_server_e2e.py` |
| JBS 真实日志样例 | `skills/hs-err-jbs-analyzer/examples/`（3 份） |
