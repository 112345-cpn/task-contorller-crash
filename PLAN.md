# 任务计划

## 第一阶段：受控崩溃（已完成）

先让 Java 程序能够明确指定崩溃类型。接口放在 WhiteBox 中，不作为普通业务 API 使用。

目前支持五种情况：

1. HotSpot fatal
2. guarantee 检查失败
3. native OOM
4. 非法地址访问
5. 整数除零

## 第二阶段：构建和测试（已完成）

分别构建 release 和 fastdebug。两套构建使用不同目录，方便比较错误日志里的调试信息。

release 和 fastdebug 均已构建完成，并通过相同的 controlledCrash 自动测试。

## 第三阶段：准备日志样本（已完成）

每个编号已经单独运行并保存对应的 HotSpot Error Log。

## 第四阶段：日志解析（进行中）

第一版解析程序已经完成，提取以下信息：

- JVM 版本
- 崩溃编号
- 错误类型
- 当前线程
- Problematic frame
- VM operation
- native 调用栈

五份 fastdebug 样本的直接原因已经完成初步分析。解析器已兼容 JBS 真实日志格式（网页复制噪声、真实线程行、assert 消息），字段提取和原因判断见 `analysis/jbs-analysis.md`。

## 第五阶段：已知问题和解决建议（第一版完成）

使用解析结果生成检索关键词，关联 Java Bug System 中的已知问题，并给出解决方案或排查建议。需要明确区分“本实验主动制造的崩溃”和 Java Bug System 中真实缺陷的复现。

第一版已用 3 个有官方结论的真实 JBS bug 验证全链路：解析出的直接原因与官方结论一致；解析器生成“关键词 + affectedVersion”约束的检索 URL，三个案例全部命中原 bug（其中 bad AD file 案例从 461 条候选收敛到唯一命中）。过程与建议见 `analysis/jbs-analysis.md`。

## 第六阶段：Agent Skill 和 MCP server（未开始）

日志解析和分析流程稳定后，再封装 Agent Skill 和 MCP server。Agent Skill 负责规定分析流程；MCP server 负责提供日志读取、解析和 Bug 检索工具。

## 最终交付

- Kona fork 的 `task` 分支中的 WhiteBox 源码修改
- 构建说明
- 五种崩溃日志的脱敏摘要，以及代表性可复现样本
- 日志分析报告
- 日志解析工具
- Agent Skill 和 MCP server 的初版

说明：JDK 源码修改不在本仓库重复保存，正式源码以
[TencentKona-25/task](https://github.com/112345-cpn/TencentKona-25/tree/task) 为准。
