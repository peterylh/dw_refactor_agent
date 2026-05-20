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
- 避免循环导入：如果出现，说明模块划分有问题。
- 第三方依赖最小化：能用标准库解决的不引入外部包。
- import 顺序：标准库 → 第三方库 → 本项目模块，各组之间空一行。

---

## 9. 可测试性

- 业务逻辑与 I/O 分离：纯计算函数不依赖数据库、文件系统。
- 依赖通过参数注入，而非在函数内部直接构造。
- 避免模块级副作用（模块导入时不应触发数据库连接等操作）。

---

## 10. 数据结构优先

- 优先使用内置数据结构（`dict`、`list`、`set`、`tuple`）。
- 结构化数据用 `dataclass` 或 `NamedTuple`，而非裸字典。
- 选择正确的数据结构：频繁查找用 `dict`/`set`，有序遍历用 `list`。

---

## 11. 简洁但不炫技

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

## 12. 错误信息要有用

- 报错信息应包含：**什么出错了 + 实际值是什么 + 期望什么**。
- 自定义异常用于业务错误，标准异常用于编程错误。

```python
# ✗
raise ValueError("参数错误")

# ✓
raise ValueError(f"表名不能为空，收到: {table_name!r}")
```

---

## 13. 幂等与安全

- 脚本和任务函数应设计为可重复执行（幂等性）。
- 危险操作（DELETE、DROP、覆盖文件）需要确认机制或 `--dry-run` 模式。
- 密码和密钥永远不写入代码或日志。

---

## 14. 注释的使用原则

- 注释解释 **why**（为什么），不解释 **what**（代码在做什么）。
- 代码无法自解释时才写注释。
- TODO 注释必须包含上下文说明，避免孤立的 `# TODO: fix this`。
- 删除注释掉的代码，交给版本控制管理历史。
