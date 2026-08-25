# 任务 1.1 阶段报告

源码正式提交位置：
[TencentKona-25/task](https://github.com/112345-cpn/TencentKona-25/tree/task)。本报告记录的是完成 1.1 时的构建和测试结果；本次重新整理仓库时没有重新构建 JDK。

## 完成情况

本阶段完成了 WhiteBox `controlledCrash(int)` 接口、五种受控崩溃实现、jtreg 测试程序，以及 Kona JDK 25 的 release 和 fastdebug 构建。两种构建上的自动测试均通过，五份 fastdebug 崩溃日志也已生成。任务 1.1 已完成，下一步开始任务 1.2 的日志解析。

## 实现内容

WhiteBox 增加了 `controlledCrash(int)`。Java 侧传入编号，native 入口检查范围后创建 `VM_ControlledCrash`，最后由 VMThread 执行。

这样处理的主要原因是让错误日志记录当前 VM operation。后续看到 `VM_ControlledCrash` 时，可以确认这是测试主动触发的故障，而不是运行过程中随机出现的问题。

| 编号 | 触发方式 | 实际日志结果 |
| --- | --- | --- |
| 1 | `fatal` | `Internal Error` |
| 2 | `guarantee(false, ...)` | `Internal Error` |
| 3 | `vm_exit_out_of_memory` | `Out of Memory Error` |
| 4 | 写入非法地址 | `SIGSEGV` |
| 5 | 整数除零 | `SIGFPE` |

输入不在 1 到 5 时抛出 `IllegalArgumentException`，不会执行崩溃。

## 构建记录

release 构建已经完成，产物位于：

```text
~/TencentKona-25-master/build/linux-x86_64-release/images/jdk
```

版本检查结果为 `25.0.4-internal`。

## release 测试记录

配置 `/opt/jtreg` 后运行：

```bash
make CONF=linux-x86_64-release test \
  TEST="jtreg:test/hotspot/jtreg/runtime/ErrorHandling/ControlledCrash.java"
```

2026 年 8 月 21 日的实际结果：

```text
Test results: passed: 1
PASS: 1
FAIL: 0
ERROR: 0
SKIP: 0
TEST SUCCESS
```

`ControlledCrash.java` 内部循环执行编号 1 到 5。每次都检查子 JVM 不是正常退出、错误日志确实存在，并且日志中包含 `VM_ControlledCrash`。测试文件最终通过，说明五个编号都完成了这些检查。

## fastdebug 构建和测试

fastdebug 构建产物位于：

```text
~/TencentKona-25-master/build/linux-x86_64-fastdebug/images/jdk
```

最初在链接 `libjvm.so` 时，Linux 使用 signal 9 结束了 `ld`。系统日志同时记录了 OOM kill，可以确定是 WSL 内存不足，而不是源码编译错误。当时 WSL 只有 2 GB 内存和 1 GB swap。将其调整为 8 GB 内存和 8 GB swap 后，继续运行原来的 `make` 命令，fastdebug 构建完成。

fastdebug 版本信息：

```text
openjdk version "25.0.4-internal" 2026-07-21
OpenJDK Runtime Environment (fastdebug build 25.0.4-internal-adhoc.test.TencentKona-25-master)
OpenJDK 64-Bit Server VM (fastdebug build 25.0.4-internal-adhoc.test.TencentKona-25-master, mixed mode, sharing)
```

随后运行同一个 jtreg 测试，结果为：

```text
PASS: 1
FAIL: 0
ERROR: 0
SKIP: 0
TEST SUCCESS
```

## 崩溃日志样本

使用 fastdebug JDK 分别触发编号 1 到 5，已经在本地保存五份完整日志：

```text
~/TencentKona-25-master/crash-logs/fastdebug/controlled-crash-1.log
~/TencentKona-25-master/crash-logs/fastdebug/controlled-crash-2.log
~/TencentKona-25-master/crash-logs/fastdebug/controlled-crash-3.log
~/TencentKona-25-master/crash-logs/fastdebug/controlled-crash-4.log
~/TencentKona-25-master/crash-logs/fastdebug/controlled-crash-5.log
```

初步核对结果：编号 1 和 2 的日志以 `Internal Error` 开头，编号 3 是 native OOM，编号 4 是 `SIGSEGV`，编号 5 是 `SIGFPE`。五份日志都能关联到 `VM_ControlledCrash`。

原始日志包含主机名、用户目录和环境变量，目前不直接提交到公开仓库。后续可以提交去除本机信息后的样本或解析结果。

## 阶段结论

任务 1.1 的接口、实现、构建和测试均已完成。release 与 fastdebug 测试结果一致，五种崩溃都能稳定复现并在日志中标记 `VM_ControlledCrash`，可以作为后续日志解析和原因分析的输入。

## 任务 1.2 当前进度

日志解析与崩溃分析工具链已完成，五个子项全部落地：

1. **解析真实 hs_err**：`tools/parse_hs_err.py` 兼容 JBS 网页复制的双空格格式、真实 JavaThread 行、assert 消息和 siginfo 细节，4 个单元测试覆盖（`tools/test_parse_hs_err.py`）。
2. **推断直接原因**：输出 `direct_cause` / `_inferred_cause` / `fault_address`，区分本实验主动制造的崩溃与真实缺陷。
3. **关联 JBS 已知问题**：解析器生成"关键词 + affectedVersion"约束的检索 URL，3 个有官方结论的真实 bug（JDK-8314225 / 8303086 / 8312741）全部命中原 issue。
4. **给出解决建议**：三案例报告见 `analysis/jbs-analysis.md`（官方结论 + 升级/规避建议）。
5. **工具链封装**：Agent Skill（`skills/hs-err-jbs-analyzer/`）+ MCP server（`tools/hs_err_mcp_server.py`，parse_hs_err / search_jbs / analyze_hs_err 三工具）。

对照任务要求的进度表见 [README.md](README.md#任务-12-对照)，MCP server 安装见 [docs/MCP.md](docs/MCP.md)。
