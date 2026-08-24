# 协作说明

## 仓库职责

- `task-controlled-crash`：规划、构建记录、报告、Error Log 解析器和脱敏分析样本。
- [TencentKona-25/task](https://github.com/112345-cpn/TencentKona-25/tree/task)：JDK 源码和 jtreg 测试修改。

修改 HotSpot 或 jtreg 源码时，先在 Kona fork 的任务分支中提交；修改报告、解析器或项目说明时，直接提交到本仓库的 `main` 分支（较大改动可先建立分支）。

## 本地测试

```bash
python -m unittest tools.test_parse_hs_err
python tools/parse_hs_err.py analysis/fixtures/controlled-crash-3.log
```

JDK 构建和 jtreg 测试命令见 `docs/BUILD.md`。不要提交完整构建目录、原始带主机信息的 `hs_err` 日志或本地配置文件。
