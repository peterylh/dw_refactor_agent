# Semantic-aware Code Review HTML Design

日期：2026-07-13

## 目标

生成一份独立 HTML，帮助审阅者先判断本次 semantic-aware verification 的整体行为是否
正确，再快速定位到主要代码模块。内容可以有技术细节，但不逐行复述 diff，也不替代源
代码审查。

## 信息架构

页面采用已确认的“审阅报告式混合结构”：

1. 顶部结论区展示改动目标、最终 Review 状态、自动化测试和 shop 实库验收结果。
2. 功能主线说明语义判定、风险传播、验证边界、轻量 replan、shadow-run 和 compare。
3. 场景矩阵对比 `equivalent`、`changed`、`unknown` 的执行、anchor、compare 和结果语义。
4. 安全边界集中解释 rename 误判、stale plan、跨 worktree、TOCTOU 和 QA marker。
5. 模块索引按文件列出职责、主要改动和建议 Review 关注点，并链接到本地源文件。
6. 持久化产物图区分 manifest、analysis inputs、plan、shadow result 和 compare result。
7. Review findings 按严重度呈现“问题、修复、验证证据”。
8. 最后给出 shop 真实验收和仍然存在的运行边界。

## 视觉与交互

- 使用适合技术审阅的中性深色页面，强调可读性而非装饰。
- 桌面端采用左侧 sticky 目录与右侧正文；窄屏自动变为单列。
- 使用少量状态色区分 passed、warning、critical 和 informational。
- 关键流程使用 HTML/CSS 卡片与连线表达，不引入外部图片或运行时依赖。
- 提供浅色/深色切换、当前章节导航高亮和返回顶部；关闭 JavaScript 后正文仍完整可读。
- 文件链接使用相对仓库路径，便于从当前 worktree 打开对应代码。

## 内容来源与边界

内容以最终提交、设计说明和持久化 Review 报告为准。页面保留必要的函数名、产物字段和
验收数字，但不复制大段源代码，不展示密码、数据库连接信息或完整内部环境配置。

最终交付写入 `docs/semantic_aware_verification_code_review.html`，不部署、不修改生产代码，
也不改变现有 refactor 产物格式。

## 验证

- 检查 HTML 结构、锚点、文件链接和无外部资源依赖。
- 在桌面与移动视口检查布局、横向溢出和控制台错误。
- 核对页面中的测试数量、shop run、执行范围和 compare 结果与最终 Review 报告一致。

