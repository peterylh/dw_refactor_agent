# Python 编码规范（大模型编程适用）

> 本规范面向大模型代码生成场景，强调**原则性约束**而非细节格式。
> 目标：生成的代码应可读、可维护、可测试。

---

## 1. 不要硬编码

- 魔法数字、路径、URL、数据库名等一律提取为**常量、配置项或参数**。
- 优先从环境变量、配置文件或函数参数获取可变值。
- 日志消息和用户提示中的字符串除外。

```python
# ✗
conn = connect("192.168.1.100", 9030, "root", "password")

# ✓
conn = connect(config.DB_HOST, config.DB_PORT, config.DB_USER, config.DB_PASSWORD)
```

---

## 2. 不要重复（DRY）

- 相同逻辑出现两次以上，必须抽取为函数或类。
- 相似的数据结构用循环或数据驱动代替逐项罗列。
- 但不要为了消除重复而引入过度抽象——可读性优先。

---

## 3. 函数职责单一

- 每个函数只做一件事，函数名即为这件事的描述。
- 函数体超过 **50 行**时考虑拆分。
- 避免函数既有返回值又有副作用（如既修改全局状态又返回结果）。

---

## 4. 命名即文档

- 变量、函数、类的命名应自解释，减少对注释的依赖。
- 布尔变量用 `is_`、`has_`、`should_` 等前缀。
- 避免无意义缩写（`cnt` → `count`，`tmp` → 给出具体含义）。
- 遵循 PEP 8 命名风格：`snake_case` 函数/变量，`PascalCase` 类名，`UPPER_CASE` 常量。

---

## 5. 显式优于隐式

- 函数参数和返回值添加 **type hints**。
- 不要依赖隐式类型转换或隐式全局状态。
- 用具名参数代替位置参数（参数超过 3 个时）。
- 公开函数写 docstring，说明参数、返回值和异常。

```python
def load_table(table_name: str, *, limit: int = 1000) -> pd.DataFrame:
    """从数据库加载指定表数据。

    Args:
        table_name: 目标表名（含库名前缀）。
        limit: 最大返回行数。

    Returns:
        表数据 DataFrame。

    Raises:
        ValueError: 表名为空时抛出。
    """
```

---

## 6. 防御式编程

- 对外部输入（用户输入、文件、网络、数据库结果）做校验，不要假设数据总是合法的。
- 使用 `pathlib.Path` 而非字符串拼接路径。
- 资源获取使用 `with` 语句（文件、连接、锁）。
- 捕获异常时指定具体类型，禁止裸 `except:`。

```python
# ✗
try:
    result = do_something()
except:
    pass

# ✓
try:
    result = do_something()
except (ConnectionError, TimeoutError) as e:
    logger.warning("操作失败: %s", e)
    raise
```

---

## 7. 日志优于 print

- 生产代码使用 `logging` 模块，不要用 `print` 调试。
- 日志分级：`DEBUG` 过程细节，`INFO` 关键步骤，`WARNING` 异常但可恢复，`ERROR` 失败。
- 日志消息包含足够的上下文（表名、行数、耗时等），便于排查。

---

## 8. 模块化与依赖管理

- 每个 `.py` 文件有清晰的单一职责。
- `src/` 下的生产 Python 代码和 `tests/` 下的测试 Python 代码，物理行数超过
  **3000 行**时必须按职责拆分。
- 物理行数按文件实际行数统计，可使用 `wc -l <file.py>` 检查，空行和注释也计入。
- 若修改前文件已经超过 3000 行，本次涉及该文件的功能开发、Bug 修复或重构必须同时
  完成拆分，不得继续增加单文件规模。
- `warehouses/` 下的数仓资产及生成工具、`benchmarks/`、`scripts/`、自动生成文件和
  第三方 vendored 代码不受该阈值限制；生成或第三方资产应能从路径、文件头或生成脚本
  明确识别。
- 3000 行是强制拆分上限，不是建议目标；未达到该阈值时，仍应根据职责边界和维护成本
  判断是否拆分。
- 拆分必须按职责进行，不得仅为降低行数机械搬移代码。
- 避免循环导入：如果出现，说明模块划分有问题。
- 第三方依赖最小化：能用标准库解决的不引入外部包。
- import 顺序：标准库 → 第三方库 → 本项目模块，各组之间空一行。

---

## 9. 可测试性

- 业务逻辑与 I/O 分离：纯计算函数不依赖数据库、文件系统。
- 依赖通过参数注入，而非在函数内部直接构造。
- 避免模块级副作用（模块导入时不应触发数据库连接等操作）。

---

## 10. 测试用例质量

- 测试必须验证**业务行为或稳定契约**，不要只验证“函数能跑完”。
- 禁止把下面这类断言作为主要断言：`len(result) > 0`、`len(result) >= N`、`isinstance(result, list)`、`result is not None`、`"xxx" in sql`、`"xxx" in prompt`。
- 如果确实需要检查数量、类型或字符串片段，必须同时断言关键结构或语义结果，例如具体血缘边、目标表、字段映射、错误码、状态流转。
- SQL 测试优先使用解析后的 AST 或结构化结果断言，不要依赖格式化后的字符串空格、大小写或渲染顺序。
- LLM prompt 测试只守稳定契约：输入上下文是否进入 prompt、JSON schema 字段是否存在、系统字段是否不暴露。不要逐句锁定中文文案。
- 不要测试私有状态（如 `_deps`、`_cache`）作为首选；优先通过公开方法验证行为。只有没有公开观察点时，才允许少量白盒断言。
- 相同逻辑的正反例用 `pytest.mark.parametrize` 或表驱动测试合并，避免为每个标量值、每个微小分支写一个独立用例。
- 每个测试都应能回答：如果这条测试失败，说明哪个用户可见行为或工程契约坏了？

```python
# ✗ 表面测试：错误映射也可能通过
entries = extract_lineage(sql)
assert len(entries) >= 2

# ✓ 行为测试：验证关键血缘契约
assert {
    (e["source_table"], e["source_column"], e["target_table"], e["target_column"])
    for e in entries
} >= {
    ("ods_order", "order_id", "dwd_order", "order_id"),
    ("ods_order", "customer_id", "dwd_order", "customer_id"),
}
```

---

## 11. 数据结构优先

- 优先使用内置数据结构（`dict`、`list`、`set`、`tuple`）。
- 结构化数据用 `dataclass` 或 `NamedTuple`，而非裸字典。
- 选择正确的数据结构：频繁查找用 `dict`/`set`，有序遍历用 `list`。

---

## 12. 简洁但不炫技

- 列表推导式适用于简单转换；嵌套超过两层时改用循环。
- 不要为了"Pythonic"牺牲可读性。
- 一行代码只做一件事。

```python
# ✗ 过度压缩
result = {k: [x for x in v if x > 0] for k, v in data.items() if len(v) > 2}

# ✓ 可读版本
result = {}
for key, values in data.items():
    if len(values) > 2:
        result[key] = [x for x in values if x > 0]
```

---

## 13. 错误信息要有用

- 报错信息应包含：**什么出错了 + 实际值是什么 + 期望什么**。
- 自定义异常用于业务错误，标准异常用于编程错误。

```python
# ✗
raise ValueError("参数错误")

# ✓
raise ValueError(f"表名不能为空，收到: {table_name!r}")
```

---

## 14. 幂等与安全

- 脚本和任务函数应设计为可重复执行（幂等性）。
- 危险操作（DELETE、DROP、覆盖文件）需要确认机制或 `--dry-run` 模式。
- 密码和密钥永远不写入代码或日志。

---

## 15. 注释的使用原则

- 注释解释 **why**（为什么），不解释 **what**（代码在做什么）。
- 代码无法自解释时才写注释。
- TODO 注释必须包含上下文说明，避免孤立的 `# TODO: fix this`。
- 删除注释掉的代码，交给版本控制管理历史。
