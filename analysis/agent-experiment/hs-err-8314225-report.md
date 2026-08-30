# hs_err 崩溃分析报告

## 基本信息

- 日志文件：`C:\Users\lenovo\.workbuddy\skills\hs-err-jbs-analyzer\examples\jdk-8314225.log`
- JRE 版本：Java(TM) SE Runtime Environment (21.0+35) (build 21+35-LTS-2513)
- VM 类型：Java HotSpot(TM) 64-Bit Server VM (21+35-LTS-2513, mixed mode, sharing, tiered, compressed class ptrs, z gc, linux-amd64)
- 崩溃类型：Signal
- 直接原因：空指针解引用 (si_addr=0x0000000000000000)，崩溃点 JavaThread::is_lock_owned
- Problematic frame：V  [libjvm.so+0x8f9363]  JavaThread::is_lock_owned(unsigned char*) const+0x23
- 崩溃线程：JavaThread "Thread-1833141" daemon（state=_thread_in_vm）

## 关键证据

- 故障地址：`0x0000000000000000`

### 崩溃栈顶部

```
V  [libjvm.so+0x8f9363]  JavaThread::is_lock_owned(unsigned char*) const+0x23  (monitorChunk.hpp:40)
```
```
V  [libjvm.so+0xea3a84]  Threads::owning_thread_from_monitor(ThreadsList*, ObjectMonitor*)+0xd4  (threads.cpp:1214)
```
```
V  [libjvm.so+0xe9f65a]  ThreadSnapshot::initialize(ThreadsList*, JavaThread*)+0x1fa  (threadService.cpp:948)
```
```
V  [libjvm.so+0xe9f914]  ThreadDumpResult::add_thread_snapshot(JavaThread*)+0x64  (threadService.cpp:573)
```
```
V  [libjvm.so+0xc01665]  jmm_GetThreadInfo+0x4a5  (management.cpp:1133)
```
```
J  1904181 sun.management.ThreadImpl.getThreadInfo1([JI[Ljava/lang/management/ThreadInfo;)V java.management@21 (0 bytes) @ 0x00007f2b0c159b95 [0x00007f2b0c159aa0+0x00000000000000f5]
```
（共 11 帧，仅显示前 6 帧）

## JBS 已知问题关联

- 检索关键词：`JavaThread::is_lock_owned, SIGSEGV`
- 子系统提示：gc
- 日志版本：21（用于版本约束检索）
- 关键词检索：https://bugs.openjdk.org/issues/?jql=text%20~%20%22JavaThread%3A%3Ais_lock_owned%22
- 版本约束检索：https://bugs.openjdk.org/issues/?jql=text%20~%20%22JavaThread%3A%3Ais_lock_owned%22%20AND%20affectedVersion%20%3D%20%2221%22

### JBS 候选 issue

- [JDK-8314225](https://bugs.openjdk.org/browse/JDK-8314225) — SIGSEGV in JavaThread::is_lock_owned（Resolved，fix 23）
- [JDK-8347594](https://bugs.openjdk.org/browse/JDK-8347594) — SIGSEGV in JavaThread::is_lock_owned（Resolved，fix 17.0.15）
- [JDK-8343422](https://bugs.openjdk.org/browse/JDK-8343422) — SIGSEGV in JavaThread::is_lock_owned（Closed，fix 17.0.15-oracle）
- [JDK-8322049](https://bugs.openjdk.org/browse/JDK-8322049) — SIGSEGV in JavaThread::is_lock_owned（Closed，fix 22）
- [JDK-8332672](https://bugs.openjdk.org/browse/JDK-8332672) — SIGSEGV in JavaThread::is_lock_owned（Closed，fix 21.0.5-oracle）

## 建议

- 已知问题，修复版本为 **23**：建议升级到该版本或更高。
- 若无法升级：参照 issue 描述临时规避（如关闭触发路径、调整 GC/编译器参数）。

---

由 `hs-err-jbs-analyzer` skill 自动生成。
