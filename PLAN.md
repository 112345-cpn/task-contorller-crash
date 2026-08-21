# 任务计划

## 1. 先完成可重复的崩溃

先让 Java 程序能够明确指定崩溃类型。接口放在 WhiteBox 中，不作为普通业务 API 使用。

计划支持五种情况：

1. HotSpot fatal
2. guarantee 检查失败
3. native OOM
4. 非法地址访问
5. 整数除零

## 2. 构建两种 JDK

分别构建 release 和 fastdebug。两套构建使用不同目录，方便比较错误日志里的调试信息。

release 和 fastdebug 均已构建完成，并通过相同的 controlledCrash 自动测试。

## 3. 保存测试日志

每个编号已经单独运行并保存对应的 HotSpot Error Log。下一步从日志中提取以下信息：

- JVM 版本
- 崩溃编号
- 错误类型
- 当前线程
- Problematic frame
- VM operation
- native 调用栈

## 4. 开始日志分析

第一版分析程序只做字段提取，不直接下复杂结论。字段稳定后再增加 Java Bug System 检索，以及解决建议。

## 5. 最终交付

- WhiteBox 修改补丁
- 构建说明
- 五种崩溃日志样本
- 日志分析报告
- 日志解析工具
- Agent Skill 和 MCP server 的初版
