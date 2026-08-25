# HotSpot hs_err 日志结构速查

JVM 发生 fatal error 时在进程工作目录生成 `hs_err_pid<pid>.log`。本 skill 的解析器
（`scripts/parse_hs_err.py`）按以下区块提取字段；真实日志与受控样本（本项目
controlledCrash 制造）格式有差异，见文末对比。

## 标准区块

| 区块 | 示例 | 解析器提取 |
|---|---|---|
| 错误头 | `# A fatal error has been detected by the Java Runtime Environment:` | `error_kind`（错误类型） |
| 崩溃头 | `#  SIGSEGV (0xb) at pc=0x..., pid=..., tid=...` | `signal`、`crash_type` |
| JRE 版本 | `#  JRE version: Java(TM) SE Runtime Environment (21.0+35) (build 21+35-LTS-2914)` | `jre_version`、`java_version`（如 `21`） |
| VM 信息 | `# Java VM: OpenJDK 64-Bit Server VM (21+35-LTS-2914) ...` | `java_vm` |
| 问题帧 | `# Problematic frame:` + 下一行 `V  [libjvm.so+0x...]  JavaThread::is_lock_owned(...)` | `problematic_frame`、`frame_symbol`（函数名） |
| 当前线程 | `Current thread (0x...):  JavaThread "Thread-1" daemon [_thread_in_vm, id=123, stack(...)]` | `current_thread`（name/id/state） |
| siginfo | `siginfo: si_signo: 11 (SIGSEGV), si_code: 1 (SEGV_MAPERR), si_addr: 0x0000000000000000` | `fault_address`、`segv_code` |
| 注册/栈 | `Registers:`、`Stack:`、`Current CompileTask:` | （未提取） |
| Native frames | `Native frames: (J=compiled Java code, j=interpreted, Vv=VM code, C=native code)` 后每行 `V  [libjvm.so+0x...]  Symbol::foo()+0x1` | `native_frames`（列表） |
| VM 操作 | `VM_Operation (0x...): ... , mode: safepoint, requested by thread 0x...` | `vm_operation`（name/mode） |
| 错误报告链 | `VMError::report_and_die`、`DwarfFile::...` 等帧 | `error_reporting_frames`（与崩溃帧分离） |

## 断言/保证失败

```
#  Internal Error (share/vm/opto/matcher.cpp:1591), pid=..., tid=...
#  Error: assert(false) failed: bad AD file
```

- 解析器识别 `assert(...)/guarantee(...) failed: <消息>` 与 `Error: <消息>`，
  写入 `assert_message`；`direct_cause` 记为“断言失败: <消息>”。
- `Internal Error` 行还带 `source_file:line`，用于定位崩溃源码位置。

## 真实日志 vs 受控样本（本项目 controlledCrash）

| 特征 | 受控样本 | JBS 真实日志 |
|---|---|---|
| 头部空格 | `# JRE version:`（单空格） | 网页复制可能出现 `#  JRE version:`（双空格）——解析器已容忍 |
| 当前线程 | `VMThread "..." [id=...]` | `JavaThread "..." daemon [_thread_in_vm, id=...]` |
| controlledCrash 标记 | 有（帧中含 `VM_ControlledCrash`、错误类型可映射） | 无 |
| 直接原因 | 由受控类型直接给出 | 需从 siginfo + problematic frame 推断（尽力而为） |
| JBS 关联 | 不生成（本实验主动制造，非已知缺陷） | 生成检索关键词与 Jira URL |

## 常见信号与直接原因推断规则

| 信号 | si_addr / si_code | 推断 |
|---|---|---|
| SIGSEGV | `si_addr=0x0` | 空指针解引用 |
| SIGSEGV | `si_addr<0x10000` | 低地址解引用，疑似空指针 + 字段偏移 |
| SIGSEGV | SEGV_MAPERR | 映射区外访问 |
| SIGSEGV | SEGV_ACCERR | 权限违规（只读区写入等） |
| SIGFPE | 整数除零 | 受控样本特征；真实日志少见 |
| Internal Error | assert/guarantee 消息 | 断言失败，看消息与源码位置 |
