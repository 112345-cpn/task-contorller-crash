# WhiteBox controlledCrash 实验

这是任务一的项目入口仓库。实验基于 Tencent Kona JDK 25，在 WhiteBox 中增加了一个运行期崩溃入口：

```java
WhiteBox.getWhiteBox().controlledCrash(type);
```

`type` 取值为 1 到 5，分别触发 fatal、guarantee 失败、native OOM、非法地址访问和整数除零。每次崩溃都应生成 HotSpot Error Log，后续用这些日志做原因分析。

任务 1.1 已完成：release 和 fastdebug 两种 JDK 均构建成功，五种受控崩溃在两种构建上都通过了 jtreg 自动测试。任务 1.2 的第一版日志解析和直接原因分析已完成，并用 3 个 JBS 真实崩溃日志验证了已知问题关联和解决建议（见 `analysis/jbs-analysis.md`）。

说明：构建和测试结果记录在 `REPORT.md`；当前 JDK 源码修改请以 Kona fork 的 `task` 分支为准。

## 仓库分工

本仓库是整个项目的入口，主要放任务规划、实验报告、测试说明和 Error Log 分析工具。

真正的 Kona JDK 源码修改已经直接提交到个人 fork，方便按 Kona 源码的正常方式查看和审核：

- Fork 仓库：[112345-cpn/TencentKona-25](https://github.com/112345-cpn/TencentKona-25)
- 任务分支：[task](https://github.com/112345-cpn/TencentKona-25/tree/task)
- 对应提交：[FEAT(whitebox): Add controlledCrash diagnostic entry](https://github.com/112345-cpn/TencentKona-25/commit/f7f8d82b56d8b9dbef4e3dbcbde1bc958b6634d6)
- 分支基线：官方 `Tencent/TencentKona-25` 的 `universal` 分支

源码修改的位置如下：

- `src/hotspot/share/prims/whitebox.cpp`
- `src/hotspot/share/runtime/vmOperation.hpp`
- `test/lib/jdk/test/whitebox/WhiteBox.java`
- `test/hotspot/jtreg/runtime/ErrorHandling/ControlledCrash.java`

查看或复现源码修改时，以 fork 仓库的 `task` 分支为准。本仓库不重复保存 JDK 源码修改。

## 建议查看顺序

1. 先看本文，了解两个仓库的分工和源码入口。
2. 再看 `PLAN.md`，了解任务安排和完成情况。
3. 查看 `REPORT.md`，了解构建、测试和 1.1 阶段结果。
4. 在 Kona fork 的 `task` 分支中查看实际源码修改。
5. 最后查看 `tools/` 和 `analysis/`，了解 Error Log 解析部分。

## 当前进度

- [x] 完成 WhiteBox Java 接口
- [x] 完成 HotSpot C++ 实现和 native 注册
- [x] 完成按编号触发的 jtreg 测试程序
- [x] 完成 release 版本构建
- [x] 在 release JDK 上完成 1 到 5 的自动测试
- [x] 完成 fastdebug 版本构建
- [x] 在 fastdebug JDK 上完成 1 到 5 的自动测试
- [x] 在本地保存五种崩溃的完整日志样本
- [x] 实现第一版日志解析并完成五份样本的直接原因初步分析
- [x] 关联 Java Bug System 已知问题并给出建议（第一版，3 个真实 JBS 日志验证）
- [x] 创建 Agent Skill（hs-err-jbs-analyzer，见 `skills/`）
- [x] 创建 MCP server（hs-err-jbs-analyzer，见 `tools/hs_err_mcp_server.py`）

## 任务 1.2 对照

| 导师要求 | 当前状态 | 对应材料 |
| --- | --- | --- |
| 解析 HotSpot Error Log | 已完成第一版，兼容 JBS 真实日志格式 | `tools/parse_hs_err.py`、`analysis/fastdebug-summary.json` |
| 分析崩溃的直接原因 | 已完成五份受控样本的初步分析；真实日志按 siginfo 与崩溃帧推断 | `analysis/REPORT.md`、`analysis/jbs-analysis.md` |
| 关联 Java Bug System 中的已知问题 | 第一版完成，3 个真实 JBS 日志全部命中原 bug | `analysis/jbs-analysis.md` |
| 给出解决方案或建议 | 第一版完成（升级版本 / 规避手段） | `analysis/jbs-analysis.md` |
| 创建 Agent Skill | 已完成（hs-err-jbs-analyzer：解析→原因→JBS 关联→建议全流程） | `skills/hs-err-jbs-analyzer/` |
| 创建 MCP server | 已完成（parse_hs_err / search_jbs / analyze_hs_err 三工具，stdio） | `tools/hs_err_mcp_server.py`、`docs/MCP.md` |

## 仓库内容

工具链（`tools/`、`skills/`、`docs/MCP.md`）要求 **Python >= 3.10**：解析器使用了
`X | None` 联合类型等 3.10+ 语法，`mcp` 2.x 依赖也要求 3.10+，旧版解释器会直接报
语法错误。建议用 `python3.10` 及以上版本运行。

- `PLAN.md`：任务安排。
- `REPORT.md`：目前的实现和构建记录。
- `docs/BUILD.md`：release 和 fastdebug 构建命令。
- `tools/parse_hs_err.py`：HotSpot Error Log 字段解析器（工具本体，CI 与 MCP server 均依赖）。
- `tools/test_parse_hs_err.py`：解析器单元测试。
- `tools/hs_err_mcp_server.py`：MCP server（解析 / JBS 检索 / 完整分析三工具）。
- `tools/test_mcp_server_e2e.py`：MCP server 端到端自测（stdio 协议拉起真实服务，跨平台：复用当前解释器、样本取仓库内相对路径）。
- `docs/MCP.md`：MCP server 安装、配置与使用说明。
- `skills/`：Agent Skill `hs-err-jbs-analyzer`（解析→原因→JBS 关联→建议的工作流封装，AI 便携版）。
- `analysis/`：去环境化解析结果、初步分析报告和 JBS 真实日志实践。

## tools/ 与 skills/ 的分工

- `tools/` 是**工具本体**：主解析器、MCP server、单测都在这，受 CI 覆盖，`docs/MCP.md` 的配置直接引用。
- `skills/` 是**给 AI 用的便携封装**：从 `tools/` 的成果打包成自包含目录，拷到 `~/.workbuddy/skills/` 即装即用，不依赖仓库其他路径。
- `skills/hs-err-jbs-analyzer/scripts/parse_hs_err.py` 与 `tools/parse_hs_err.py` 是同一份代码的两个副本。
  **维护约定：改动解析器逻辑以 `tools/` 版本为准（有 CI 验证），改完把新文件同步覆盖到 skill 的 `scripts/` 副本，保持两边一致。**

## 测试入口

JDK 构建和 jtreg 测试命令见 [docs/BUILD.md](docs/BUILD.md)，release 与 fastdebug 的测试结果见 [REPORT.md](REPORT.md)。

代码来自 OpenJDK/Tencent Kona 源码树，对应源文件保留原有许可证和版权声明。
