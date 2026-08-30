# 日志分析

`tools/parse_hs_err.py` 是第一版 HotSpot Error Log 解析器。它只提取日志中明确出现的字段，不把实验性判断伪装成已知 Bug 结论。

初步分析结论见 `REPORT.md`，五份去环境化 JSON 结果见 `fastdebug-summary.json`。

用 JBS 真实崩溃日志（别人的日志，非自制样本）验证“解析 → 直接原因 → 关联已知问题 → 建议”全链路的实践见 `jbs-analysis.md`。

将 Agent Skill 与 MCP server 实际安装进 AI Agent（WorkBuddy/CodeBuddy 系）并分析 hs_err 日志的完整实验过程见 `agent-experiment/REPORT.md`。

运行单个文件：

```bash
python3 tools/parse_hs_err.py /path/to/hs_err_pid.log
```

批量处理 controlledCrash 日志：

```bash
python3 tools/parse_hs_err.py \
  --directory /path/to/crash-logs/fastdebug \
  --output analysis/fastdebug-summary.json
```

本目录中的 `fastdebug-summary.json` 是五份本地日志的去环境化摘要。原始日志包含主机名、用户目录和环境变量，因此没有直接放入公开仓库。

`fixtures/controlled-crash-3.log` 是一份脱敏的最小样本，用来复现解析器对 native OOM 及错误报告器二次错误的区分。完整原始日志仍保留在本地实验环境，不作为公开交付物。
