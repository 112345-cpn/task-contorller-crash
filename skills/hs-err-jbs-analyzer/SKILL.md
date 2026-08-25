---
name: hs-err-jbs-analyzer
description: 解析 HotSpot hs_err 崩溃日志，推断直接原因，并关联 Java Bug System（JBS）已知问题、给出修复建议。当用户提供 JVM 崩溃日志（hs_err_pid*.log、.txt 或 JBS issue 附件），或询问"这个崩溃怎么回事/是不是已知 bug/怎么修"时使用。也用于批量分析多条崩溃日志。触发词：hs_err、JVM crash、崩溃日志、SIGSEGV、Internal Error、JBS、Java Bug System。
agent_created: true
---

# hs-err-jbs-analyzer

将 HotSpot 崩溃日志（`hs_err_pid*.log`）解析为结构化字段，推断直接原因，
并关联 Java Bug System（JBS）上的已知 issue，最终给出升级/规避建议。
适用于单个或批量 JVM 崩溃日志分析。

## 工作流

按顺序执行；联机检索失败时降级为仅本地解析，不要中断。

### 第 1 步：定位并解析日志

用 `scripts/analyze_hs_err.py` 解析一个或多个日志文件，输出 JSON：

```bash
python scripts/analyze_hs_err.py <hs_err.log> [更多日志...]
```

关键输出字段（详见 `references/hs_err_structure.md`）：

- `error_kind` / `signal` / `crash_type`：崩溃类型
- `direct_cause`：直接原因（受控样本为确定结论；真实日志为推断，用词"疑似/推断"）
- `problematic_frame` / `frame_symbol`：崩溃点
- `current_thread`：崩溃线程（name/id/state）
- `fault_address` / `segv_code` / `assert_message`：关键证据
- `java_version` / `jre_version`：版本（JBS 版本约束检索的输入）
- `jbs_search`：真实日志才有，含 `keywords`/`url`/`url_version`

### 第 2 步：向用户解释直接原因

用解析结果向用户说明：

1. 崩溃类型（SIGSEGV / Internal Error / OOM…）
2. 直接原因：空指针解引用（`si_addr=0x0`）/ 低地址解引用 / 断言失败 `assert_message` /
   受控样本的对应错误类型
3. 崩溃点函数与源码位置（`Internal Error` 行的 `source_file:line`）
4. 崩溃线程状态（`_thread_in_vm` / `_thread_in_native`）与 VM 操作

受控样本（`crash_type` 非空）不再进行 JBS 关联——它是本实验主动制造的崩溃。

### 第 3 步：联机检索 JBS 已知问题（真实日志）

```bash
python scripts/analyze_hs_err.py <hs_err.log> --jbs --limit 5
```

- 脚本用 `jbs_search.url_version`（版本约束检索）查询 JBS REST API，返回候选 issue
  （key/summary/status/fixVersions）。
- 若 `--jbs` 失败（无网络等），改用本地输出的 `url_version` 链接给用户自行打开。
- 检索策略与实证见 `references/jbs_search_strategy.md`：
  - assert 崩溃优先用断言消息当关键词
  - SIGSEGV 用崩溃点函数名
  - **务必保留版本约束**（`AND affectedVersion = "版本"`）——纯关键词命中可差两个数量级

### 第 4 步：给出建议

- 命中已知 issue 且 `fixVersions` 非空：建议升级到修复版本（取列表中最新的 backport），
  无法升级时给临时规避手段（关闭触发路径、调整 GC/编译器参数等）。
- 命中同类型 issue 但未修复：建议跟踪该 issue。
- 未命中任何 issue：提示"可能是新问题"，建议向 JBS 提交，并附解析字段作复现信息。

### 第 5 步（可选）：生成分析报告

```bash
python scripts/analyze_hs_err.py <hs_err.log> --jbs --report --out hs-err-analysis.md
```

## 使用脚本的注意事项

- 脚本位于 `scripts/`，直接从任意目录用绝对路径运行即可：
  `python <skill目录>/scripts/analyze_hs_err.py <日志> --jbs --report`
- 脚本依赖同一目录的 `parse_hs_err.py`（与仓库 `tools/parse_hs_err.py` 保持同步）。
- `--report` 输出的 Markdown 以"基本信息 → 关键证据 → 崩溃栈 → JBS 关联 → 建议"组织，
  可直接作为给用户/导师的分析材料。

## 示例

`examples/` 目录含 3 份真实 JBS 日志（已确认答案，可作正确性对照）：

| 样例 | 命中 issue | 修复版本 |
|---|---|---|
| `jdk-8314225.log`（SIGSEGV, ZGC, 21） | JDK-8314225 | 21.0.5+ |
| `jdk-8303086.log`（SIGSEGV, JVMTI, 21） | JDK-8303086 | 21 GA |
| `jdk-8312741.log`（assert bad AD file, C2, 11.0.20） | JDK-8312741 | 11.0.26+ |

验证示例：

```bash
python scripts/analyze_hs_err.py examples/jdk-8314225.log --jbs --report
```
