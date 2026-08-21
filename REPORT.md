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

## 尚未完成

目前还没有把五种完整错误日志样本整理进仓库，也没有完成 fastdebug 构建。

下一步整理日志样本，再开始 HotSpot Error Log 字段解析。
