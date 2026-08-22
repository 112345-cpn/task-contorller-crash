# 源码文件

这里放的是本次修改涉及的完整源码文件，目录结构对应 Tencent Kona JDK 25 源码树中的路径。

| 仓库文件 | Kona 源码中的路径 | 作用 |
| --- | --- | --- |
| `src/hotspot/share/prims/whitebox.cpp` | `src/hotspot/share/prims/whitebox.cpp` | 实现 `VM_ControlledCrash`，注册 native 入口，并按编号触发五种崩溃 |
| `src/hotspot/share/runtime/vmOperation.hpp` | `src/hotspot/share/runtime/vmOperation.hpp` | 增加 `VM_ControlledCrash` 的 VM operation 类型 |
| `test/lib/jdk/test/whitebox/WhiteBox.java` | `test/lib/jdk/test/whitebox/WhiteBox.java` | 声明 Java 侧 `controlledCrash(int)` native 方法 |
| `test/hotspot/jtreg/runtime/ErrorHandling/ControlledCrash.java` | `test/hotspot/jtreg/runtime/ErrorHandling/ControlledCrash.java` | 启动五个子 JVM，检查崩溃日志是否生成并包含 `VM_ControlledCrash` |

这些文件是从已经通过 release 和 fastdebug 测试的 Kona 源码树中复制的完整文件。完整修改可以通过仓库根目录的 `controlled-crash.patch` 应用到另一份 Kona 源码树。
