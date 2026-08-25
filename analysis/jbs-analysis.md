# JBS 真实崩溃日志解析实践

任务 1.2 的完整链路是“解析 HotSpot Error Log → 分析直接原因 → 关联 Java Bug System 已知问题 → 给出解决方案或建议”。前两步此前用自制 controlledCrash 样本验证过；本文用 JBS 上**别人的真实崩溃日志**走完全部四步，并与官方结论对照。

## 方法

1. 选 3 个已有官方结论（Resolved / Fixed，fixVersion 明确）的 HotSpot 崩溃 bug，覆盖三种错误形态和两个平台：
   - JDK-8314225：SIGSEGV，linux-amd64，ZGC，JDK 21 GA
   - JDK-8303086：SIGSEGV，bsd-aarch64（macOS），G1，JVMTI，JDK 21 pre-GA
   - JDK-8312741：Internal Error 断言失败，linux-amd64，C2，JDK 11.0.20 fastdebug
2. 日志取自各 issue 描述/附件中的 hs_err 片段（JBS 公开内容，本地保存为 `jdk-<id>.log`，不入库）。
3. 解析：`python3 tools/parse_hs_err.py <log>`，读 `direct_cause`、`java_version`、`jbs_search`。
4. 关联：打开解析器生成的 `jbs_search.url_version`（关键词 + `affectedVersion` 约束），核对命中的 issue。
5. 验证：用 JBS REST API 记录检索条数与排序，读取 fixVersion、backport 与关联 issue。

选这 3 个 bug 的原因：都有确定的修复版本，解析器的结论可以和官方结论对照，而不是自说自话。

## 结果总览

| 日志 | 解析出的直接原因 | 检索：关键词 → 加版本约束 | 命中 issue | 官方修复 |
| --- | --- | --- | --- | --- |
| jdk-8314225.log | 空指针解引用（si_addr=0x0），崩溃点 `JavaThread::is_lock_owned` | 351 条（第 1）→ 19 条（第 1） | JDK-8314225 | 23；backport 22 / 21.0.5 / 17.0.15 |
| jdk-8303086.log | 低地址解引用，疑似空指针加字段偏移（si_addr=0x560），崩溃点 `JavaThread::is_interp_only_mode` | 32 条（第 1）→ 9 条（第 1） | JDK-8303086 | 22；backport 21 / 21.0.1 |
| jdk-8312741.log | 断言失败：`assert(false) failed: bad AD file` | 461 条（目标不在前 10）→ 1 条（唯一） | JDK-8312741 | 11.0.26-oracle |

检索条数与排序为 2026-08-25 经 JBS REST API 复核的快照。

## 案例一：JDK-8314225 SIGSEGV in JavaThread::is_lock_owned

issue：<https://bugs.openjdk.org/browse/JDK-8314225>

**输入**：JDK 21 GA（21+35）linux-amd64，ZGC，RunThese8H 压测中崩溃。

**解析器输出（关键字段）**：

```
error_kind:        Signal / SIGSEGV
direct_cause:      空指针解引用 (si_addr=0x0)，崩溃点 JavaThread::is_lock_owned
java_version:      21
current_thread:    JavaThread "Thread-1833141" daemon, state=_thread_in_vm
problematic_frame: V [libjvm.so+0x8f9363] JavaThread::is_lock_owned(unsigned char*) const+0x23
native_frames:     is_lock_owned ← Threads::owning_thread_from_monitor ← ThreadSnapshot::initialize ← ThreadDumpResult::add_thread_snapshot …
```

**解读**：调用链说明崩溃发生在**线程转储（thread dump）路径**：生成 ThreadSnapshot 时反查 ObjectMonitor 的持有线程，`is_lock_owned` 判断地址是否落在本线程的 monitor chunk 栈区间内，期间访问了空地址。崩溃线程是普通业务 daemon 线程、状态 `_thread_in_vm`，与高并发压测下触发转储的场景吻合。

**JBS 关联**：

- `text ~ "JavaThread::is_lock_owned"`：351 条，目标第 1；
- 加 `affectedVersion = "21"`：19 条，目标第 1（其余为 backport 副本）。

**官方结论**：主修复进 23；backport：22（JDK-8322049）、21.0.5（JDK-8333424、JDK-8332672-oracle）、17.0.15（JDK-8343422、JDK-8347594）。后续清理见关联 issue JDK-8331661（简化 is_lock_owned 逻辑）。

**建议（线上遇到同栈崩溃时）**：

1. 升级到 21.0.5+（21 维护线）或对应 backport 版本，这是唯一彻底的修复方式；
2. 无法及时升级时，从调用链看崩溃发生在 thread dump 路径，降低高并发下触发转储（jstack、`Thread.getAllStackTraces`、JFR 线程转储）的频率可以缩小暴露面——这是缓解，不是修复；
3. 崩溃点在 VM 内部代码，应用侧没有可用的规避补丁。

## 案例二：JDK-8303086 SIGSEGV in JavaThread::is_interp_only_mode()

issue：<https://bugs.openjdk.org/browse/JDK-8303086>

**输入**：JDK 21 pre-GA slowdebug 构建（21-internal，2023-02-16）bsd-aarch64，G1，JVMTI `GetStackTraceSuspendedStressTest` 压测。这个案例同时验证了解析器对 macOS（`libjvm.dylib`）日志的兼容。

**解析器输出（关键字段）**：

```
error_kind:        Signal / SIGSEGV
direct_cause:      低地址解引用，疑似空指针加字段偏移 (si_addr=0x560)，崩溃点 JavaThread::is_interp_only_mode
java_version:      21
current_thread:    JavaThread "JVMTI agent thread" daemon, state=_thread_in_vm
problematic_frame: V [libjvm.dylib+0xebf5cc] JavaThread::is_interp_only_mode()+0x14
native_frames:     is_interp_only_mode ← JvmtiThreadState::is_interp_only_mode ← JvmtiEventControllerPrivate::recompute_thread_enabled ← recompute_enabled …
```

**解读**：崩溃链全部位于 JVMTI 事件控制器重算路径。`si_addr=0x560` 是典型的“空指针 + 字段偏移”模式：对 NULL 对象读字段。该 issue 的关联 issue JDK-8311177（载体线程上切换 interpreter only mode）指向 JVMTI interp-only 模式切换的问题，与解析器“空指针字段访问”的推断方向一致；根因细节以 issue 讨论为准。

**JBS 关联**：

- `text ~ "JavaThread::is_interp_only_mode"`：32 条，目标第 1；
- 加 `affectedVersion = "21"`：9 条，目标第 1。

**官方结论**：主修复进 22；backport 进 21 正式版（JDK-8311543，即该修复赶在 21 GA 前合入）和 21.0.1（JDK-8312884）。

**建议**：

1. 该日志来自 21 GA 之前的内部构建；正式发布的 21 及以上版本已包含修复；
2. 仍在用 21 内部/EA 构建的用户，升级到 21 GA 或 21.0.1+；
3. 无法升级时的缓解：降低 JVMTI agent 对 suspended 线程并发调用 GetStackTrace 的压力，或暂时关闭会触发 interp-only 模式切换的 agent 事件。

## 案例三：JDK-8312741 C2: LoopLimitNode is not eliminated

issue：<https://bugs.openjdk.org/browse/JDK-8312741>

**输入**：OpenJDK 11.0.20 fastdebug，linux-amd64，`-Xcomp` 跑修改版 `compiler.codegen.TestBooleanVect`。

**解析器输出（关键字段）**：

```
error_kind:        Internal Error (opto/matcher.cpp:1591)
assert_message:    bad AD file
direct_cause:      断言失败: assert(false) failed: bad AD file
java_version:      11.0.20
current_thread:    JavaThread "C2 compilerThread0" daemon, state=_thread_in_native
problematic_frame: V [libjvm.so+0x10] Matcher::Matcher()+0x1
native_frames:     Matcher::Matcher ← Compile::Compile ← C2Compiler::compile_method ← CompileBroker::invoke_compiler_on_method
```

**解读**：C2 编译线程在 Matcher 构造阶段断言失败。“bad AD file”字面意思是 AD 文件（架构描述文件）里找不到匹配指令，但多数情况不是 AD 文件真的写错，而是前端图优化留下了不该存在的节点。该 issue 标题“LoopLimitNode is not eliminated”就是根因：LoopLimitNode 未被消除，存活到了 Matcher 阶段。

**JBS 关联（本案例最能说明版本约束的价值）**：

- `text ~ "bad AD file"`：**461 条**——这条断言消息被几十个不同根因的 C2 bug 共用，按时间排序目标不在前 10；
- 加 `affectedVersion = "11.0.20"`：**1 条**，唯一命中 JDK-8312741。

也就是说：**关键词回答“是什么类型的错”，版本约束回答“是哪一个 bug”**。解析器把 `assert_message` 作为主检索词（而不是崩溃点函数 `Matcher::Matcher`），正是因为断言消息的区分度更高。

**官方结论**：修复进 11.0.26（oracle 维护线）。

**建议**：

1. 升级到 11.0.26+；
2. 短期规避：去掉 `-Xcomp`（该崩溃只在强制全编译下复现）；
3. 注意：遇到同一条断言消息不要直接套用别的 bug 的结论，先按版本约束检索确认。

## 解析器为支持真实日志新增的能力

| 能力 | 说明 |
| --- | --- |
| JBS 格式容忍 | 头部正则接受网页复制产生的 `#  JRE version:` 双空格等噪声 |
| 真实线程行 | 兼容 `daemon [_thread_in_vm, id=...]` 布局，新增 `current_thread.state` |
| assert 识别 | 提取 `assert(...)/guarantee(...) failed: msg` 为 `assert_message` |
| 直接原因推断 | 按 si_addr 分级（0x0 空指针 / <0x10000 空指针加字段偏移 / MAPERR / ACCERR），附崩溃点函数 |
| `java_version` | 从 JRE version 行提取短版本号（如 `21`、`11.0.20`） |
| `jbs_search.url_version` | 关键词 + `affectedVersion` 约束的 JBS 检索 URL |

以上能力都有回归测试覆盖：`tools/test_parse_hs_err.py::test_real_world_jbs_log`（内嵌 JDK-8314225 风格的最小真实格式样本）。

## 局限

- 样本只有 3 个、且都是已有官方结论的 bug；对没有结论的日志，本流程只能给出“解析结果 + 候选 issue”，最终定位仍需人工确认版本与调用栈匹配。
- `affectedVersion` 约束依赖 JBS issue 的填写规范；维护者漏填 affects 版本时会漏检（此时退回纯关键词检索）。
- `direct_cause` 是基于 siginfo 与崩溃帧的 best-effort 推断，不替代人工读栈。
- 检索条数是 2026-08-25 的快照，会随新 issue 增长。

## 复现

```bash
# 解析（任意 hs_err 日志）
python3 tools/parse_hs_err.py /path/to/hs_err_pid.log

# 解析结果中查看 JBS 检索 URL：
#   jbs_search.url          纯关键词检索
#   jbs_search.url_version  关键词 + affectedVersion 约束

# 用 REST API 复核命中（示例）
curl -s 'https://bugs.openjdk.org/rest/api/2/search?jql=text%20~%20%22JavaThread%3A%3Ais_lock_owned%22%20AND%20affectedVersion%20%3D%20%2221%22&maxResults=5&fields=summary'
```

三个样本日志来自下列 issue 的公开描述/附件（本地未入库）：

- <https://bugs.openjdk.org/browse/JDK-8314225>
- <https://bugs.openjdk.org/browse/JDK-8303086>
- <https://bugs.openjdk.org/browse/JDK-8312741>
