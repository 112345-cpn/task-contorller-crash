# 阶段报告

## 实现内容

WhiteBox 增加了 `controlledCrash(int)`。Java 侧传入编号，native 入口检查范围后创建 `VM_ControlledCrash`，最后由 VMThread 执行。

这样处理的主要原因是让错误日志记录当前 VM operation。后续看到 `VM_ControlledCrash` 时，可以确认这是测试主动触发的故障，而不是运行过程中随机出现的问题。

| 编号 | 触发方式 | 预期现象 |
| --- | --- | --- |
| 1 | `fatal` | HotSpot 主动报告致命错误 |
| 2 | `guarantee(false, ...)` | guarantee 检查失败 |
| 3 | `vm_exit_out_of_memory` | native OOM 报告 |
| 4 | 写入非法地址 | Linux 上通常为 SIGSEGV |
| 5 | 整数除零 | Linux 上通常为 SIGFPE |

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

## 尚未完成

还没有完成 HotSpot Error Log 解析程序、Java Bug System 已知问题检索、解决建议、Agent Skill 和 MCP server。

下一步先实现日志字段解析，输出错误类型、当前线程、Problematic frame、VM operation 和 native 调用栈摘要。
