# HotSpot Error Log 初步分析

## 分析范围

本报告分析的是 fastdebug JDK 生成的五份 `controlledCrash` 日志。解析器提取日志中明确出现的字段，结果见 `fastdebug-summary.json`。没有把主机名、用户目录和环境变量放进摘要。

## 结果

| 编号 | 日志类型 | 直接原因 | 证据 |
| --- | --- | --- | --- |
| 1 | `Internal Error` | WhiteBox 主动调用 `fatal` | `whitebox.cpp:193`，错误消息为 `controlled crash requested through WhiteBox (type 1)` |
| 2 | `Internal Error` | `guarantee(false, ...)` 检查失败 | `whitebox.cpp:196`，错误消息为 `guarantee(false) failed` |
| 3 | `Out of Memory Error` | WhiteBox 主动调用 `vm_exit_out_of_memory` | `whitebox.cpp:199`，日志开头明确写出 `Out of Memory Error` |
| 4 | `SIGSEGV` | 向非法地址 `0x400` 写入 | `siginfo` 为 `SEGV_MAPERR`，Problematic frame 为 `VM_ControlledCrash::doit()` |
| 5 | `SIGFPE` | 整数除零 | `siginfo` 为 `FPE_INTDIV`，Problematic frame 为 `VM_ControlledCrash::doit()` |

五份日志的当前线程都是 `VMThread "VM Thread"`，VM operation 都是：

```text
ControlledCrash, mode: safepoint
```

这说明 Java 侧调用先进入 WhiteBox native 方法，再由 VMThread 执行 `VM_ControlledCrash`。日志中的 `VM_ControlledCrash` 是本实验主动触发的标记，不是随机崩溃原因。

## 第 3 类日志的特殊情况

编号 3 在报告 native OOM 后，fastdebug 的错误报告代码又尝试打印带源码信息的 native 栈，日志中出现了：

```text
[error occurred during error reporting ... elfFile.cpp:742]
```

这条信息是错误报告过程中的二次问题，不应覆盖最前面的主原因。主原因仍然是 `whitebox.cpp:199` 的 `vm_exit_out_of_memory`。

## 当前结论和限制

当前只能确认这五份实验日志的直接原因，不能据此声称找到了 Java Bug System 中的已知缺陷。下一步需要根据错误类型、源码位置和 native 栈关键词检索 Java Bug System，并把“已知问题”与“本实验主动制造的故障”区分开。
