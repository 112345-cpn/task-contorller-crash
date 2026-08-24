# WhiteBox controlledCrash 实验

这是任务一的独立仓库。代码基于 Tencent Kona JDK 25，在 WhiteBox 中增加了一个运行期崩溃入口：

```java
WhiteBox.getWhiteBox().controlledCrash(type);
```

`type` 取值为 1 到 5，分别触发 fatal、guarantee 失败、native OOM、非法地址访问和整数除零。每次崩溃都应生成 HotSpot Error Log，后续用这些日志做原因分析。

任务 1.1 已完成：release 和 fastdebug 两种 JDK 均构建成功，五种受控崩溃在两种构建上都通过了 jtreg 自动测试。目前开始任务 1.2 的日志解析工作。

## 仓库分工

本仓库是整个项目的入口，主要放任务规划、实验报告、测试说明和 Error Log 分析工具。

真正的 Kona JDK 源码修改已经直接提交到个人 fork，方便按 Kona 源码的正常方式查看和审核：

- Fork 仓库：[112345-cpn/TencentKona-25](https://github.com/112345-cpn/TencentKona-25)
- 任务分支：[task](https://github.com/112345-cpn/TencentKona-25/tree/task)
- 对应提交：[Add WhiteBox controlled crash task](https://github.com/112345-cpn/TencentKona-25/commit/32a5876c380f2ecaadefa99038c431e20d400f08)
- 分支基线：官方 `Tencent/TencentKona-25` 的 `universal` 分支

源码修改的位置如下：

- `src/hotspot/share/prims/whitebox.cpp`
- `src/hotspot/share/runtime/vmOperation.hpp`
- `test/lib/jdk/test/whitebox/WhiteBox.java`
- `test/hotspot/jtreg/runtime/ErrorHandling/ControlledCrash.java`

查看或复现源码修改时，以 fork 仓库的 `task` 分支为准；本仓库中的 `code/` 和补丁文件只是实验过程中的辅助备份。

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
- [ ] 关联 Java Bug System 已知问题并给出建议
- [ ] 创建 Agent Skill
- [ ] 创建 MCP server

## 任务 1.2 对照

| 导师要求 | 当前状态 | 对应材料 |
| --- | --- | --- |
| 解析 HotSpot Error Log | 已完成第一版 | `tools/parse_hs_err.py`、`analysis/fastdebug-summary.json` |
| 分析崩溃的直接原因 | 已完成五份受控样本的初步分析 | `analysis/REPORT.md` |
| 关联 Java Bug System 中的已知问题 | 尚未开始 | 下一步工作 |
| 给出解决方案或建议 | 尚未开始 | 等已知问题检索完成后补充 |
| 创建 Agent Skill | 尚未开始 | 后续实现 |
| 创建 MCP server | 尚未开始 | 后续实现 |

本次构建基于 Kona JDK 25，release 版本信息为：

```text
openjdk version "25.0.4-internal" 2026-07-21
OpenJDK Runtime Environment (build 25.0.4-internal-adhoc.test.TencentKona-25-master)
OpenJDK 64-Bit Server VM (build 25.0.4-internal-adhoc.test.TencentKona-25-master, mixed mode, sharing)
```

## 仓库内容

- `controlled-crash.patch`：早期实验中保留的源码差异备份，不是主要交付物。
- `code/`：本次修改涉及的四个源码文件备份，正式源码以 fork 仓库的 `task` 分支为准。
- `PLAN.md`：任务安排。
- `REPORT.md`：目前的实现和构建记录。
- `docs/BUILD.md`：release 和 fastdebug 构建命令。
- `tools/parse_hs_err.py`：HotSpot Error Log 字段解析器。
- `tools/test_parse_hs_err.py`：解析器单元测试。
- `analysis/`：去环境化解析结果和初步分析报告。

## 历史补丁

项目早期曾用补丁在另一份 Kona 25 源码树中重放修改。导师要求改为直接在 fork 仓库提交，因此现在不需要通过补丁完成交付。

如果只是为了复现实验，进入 Kona 25 源码仓库后可以执行：

```bash
git am /path/to/task-contorller-crash/controlled-crash.patch
```

核心修改位置：

- `src/hotspot/share/prims/whitebox.cpp`
- `src/hotspot/share/runtime/vmOperation.hpp`
- `test/lib/jdk/test/whitebox/WhiteBox.java`
- `test/hotspot/jtreg/runtime/ErrorHandling/ControlledCrash.java`

对应的完整源码文件见 `code/` 目录；根目录的 `controlled-crash.patch` 用于在另一份 Kona 源码树中重放修改。

## 测试入口

构建完成后，在 Kona 源码目录运行：

```bash
make CONF=linux-x86_64-release test \
  TEST="jtreg:test/hotspot/jtreg/runtime/ErrorHandling/ControlledCrash.java"
```

这个测试会分别启动子 JVM。这样一个子 JVM 崩溃后，剩余编号仍然可以继续测试。

本次 release 测试结果为 `PASS 1、FAIL 0、ERROR 0`。一个测试文件内部已经依次检查了 1 到 5。

fastdebug 构建和相同的自动测试也已经完成，结果同样为 `PASS 1、FAIL 0、ERROR 0`。五份原始 `hs_err` 日志保存在本地实验环境中；日志带有主机名和环境变量，因此没有直接提交到公开仓库。

代码来自 OpenJDK/Tencent Kona 源码树，对应源文件保留原有许可证和版权声明。
