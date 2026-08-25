# JBS 检索策略（经验实证）

目标：从一条崩溃日志找到 Java Bug System（JBS, bugs.openjdk.org）上对应的已知
issue。纯关键词搜“是什么类型的错”，**加版本约束**才是“是哪一个 bug”的关键。

## 检索词选择（按优先级）

1. **assert 消息**（断言崩溃时）：如 `bad AD file`。断言消息在 JBS 标题中常原样出现，
   区分度最高。注意：同一断言可能被多个不同根因的 bug 共用（见案例 3）。
2. **崩溃点函数名**（SIGSEGV 时）：如 `JavaThread::is_lock_owned`。JBS 标题惯例就是
   `SIGSEGV in <函数名>`，直接命中率极高。
3. **信号名**：如 `SIGSEGV`。作为兜底关键词，单独用区分度太低。

## 版本约束（最重要的技巧）

```
text ~ "关键词" AND affectedVersion = "版本"
```

- 版本取自日志 `# JRE version:` 的 `java_version`（`21.0` → `21`，`11.0.20` 原样保留）。
- 解析器生成的 `jbs_search.url_version` 即此格式的可点击链接。
- **实证数据**：

| 关键词 | 纯关键词命中 | 加版本约束后 | 结论 |
|---|---|---|---|
| `JavaThread::is_lock_owned` + ver 21 | 351 条 | 19 条，JDK-8314225 排第 1 | 版本约束精准 |
| `JavaThread::is_interp_only_mode` + ver 21 | 32 条 | 9 条，JDK-8303086 排第 1 | 精准 |
| `bad AD file` + ver 11.0.20 | 461 条 | **唯一命中** JDK-8312741 | 不加约束目标不在前 10 |

## REST API 用法（联机查询）

```
GET https://bugs.openjdk.org/rest/api/2/search
  ?jql=text ~ "JavaThread::is_lock_owned" AND affectedVersion = "21"
  &maxResults=5
  &fields=summary,status,resolution,fixVersions
```

- 无认证、无速率限制限制（合理频率）。
- `fixVersions` 含修复版本（含 backport，如 `21.0.5`、`17.0.15`），是“给建议”的依据。
- 关联 issue（backport/relates-to）可从 `issuelinks` 字段获取：
  `GET /rest/api/2/issue/JDK-8314225?fields=issuelinks`。

## 已用本策略验证的案例

| 日志 | 检索词 | 命中 | 修复版本 |
|---|---|---|---|
| JDK-8314225（ZGC, 21） | `JavaThread::is_lock_owned` + ver 21 | JDK-8314225 | 21.0.5 / 17.0.15 / 22 / 23 |
| JDK-8303086（JVMTI, 21） | `JavaThread::is_interp_only_mode` + ver 21 | JDK-8303086 | 21（GA 前合入） |
| JDK-8312741（C2, 11.0.20） | `bad AD file` + ver 11.0.20 | JDK-8312741 | 11.0.26 |

完整分析见仓库 `analysis/jbs-analysis.md`。
