# retail_banking 资产重写结果

## 结果

资产已经从名称启发式基线重写为人工裁决规格驱动的可重复生成项目，固定上游为
Apache Fineract `45d8e24f82c9c42c46a6762b24e102ad2c723824`。

| 层级 | 表数 | 说明 |
|---|---:|---|
| ODS | 277 | 完整银行业务 tenant 表；含下游未采用的语义负例 |
| DIM | 35 | 稳定实体、参考数据、层级和桥接关系 |
| DWD | 69 | 事件、关系、余额及 4 张账户日快照 |
| DWS | 18 | 显式粒度、业务日期、币种、冲正和可加性契约 |
| ADS | 13 | KPI、对账、还款计划及拨备入账监控 |
| 合计 | 412 | 135 个加工任务 |

源表裁决为 100 `human_reviewed`、27 `security_reviewed`、150 `candidate`。
100 个直接语义目标由 35 DIM、65 DWD 组成；4 个易变账户实体另外生成 DWD
日快照，因此物理 DIM/DWD 合计为 104。

## 主要改造

- `semantic_specs/dim_dwd.yaml` 固化 104 条逐表裁决（含 4 个撤回映射的硬负例），
  描述目标层、表类型、主/关联实体、粒度、业务日期、过程、敏感性和允许替代答案。
- `semantic_specs/dws_ads.yaml` 固化 18 DWS 与 13 ADS 的指标公式、单位、币种来源、
  可加性、符号和冲正策略；虚假的“监控”表改为 KPI 或 reconciliation。
- 贷款、存款、股份和 working-capital 账户拆为稳定 DIM 与带 `snapshot_date` 的 DWD
  快照，避免把当前余额伪装成稳定维度属性。
- DWD 统一生成业务日期；无日期的当前状态表使用 ETL 快照日期；继承日期通过已声明
  FK 获取。
- `dwd_account_transfer_transaction` 与 `dwd_loan_installment_charge` 在 DWD 通过上游
  主键一对一补齐聚合键，DWS 不再聚合前连接，消除 fanout 风险。
- restricted 字段按列执行 hash、mask 或 redact；security-excluded 源不生成直接下游。
- `benchmark/input_manifest.yaml` 明确 participant 可见输入和禁止文件；
  `benchmark/private_gold.yaml` 作为必须迁往 evaluator-only 存储的私有答案。

## 验证

- schema identity：412/412 通过。
- 字段血缘：2,011 条直接边、156 条间接边、0 临时表。
- 作业 DAG：135 个节点、156 条跨表边、拓扑层为 `104 -> 18 -> 13`，0 环路；
  另有 6 条预期的执行日快照 `DELETE` 过滤自依赖，由 DAG 单独记录但不参与环路。
- 资产评估：完整性 100、模型元数据健康度 100、代码质量 100、链路长度 100；总分
  81.7。总分主要被“所有中间表必须被下游复用”的通用规则拉低；本项目为冷启动
  benchmark，保留大量终端 DIM/DWD 与未采用 ODS 是有意的语义判别样本。
- 敏感血缘：restricted 表到 non-restricted 表的字段边为 0。
- 定向测试：retail_banking + lineage 共 229 个测试通过。
- 重复生成：生成资产组合 SHA-1 两次均为
  `f1c4f2ace53a73880be004770842081050f38adb`。

全量非 API 测试在当前 Homebrew Python 3.14 环境的收集阶段因缺少
`typing_extensions` 中止；这是本地替代环境依赖问题，不是 retail_banking 测试失败。

## Benchmark 边界

当前版本适合作为候选 benchmark corpus，但不应直接宣称 `gold_v1`。正式发布前仍需：

1. 用真实的两位独立 reviewer 与 adjudicator 身份替换 candidate reviewer 占位符；
2. 实现公式归一化 scorer 与全部 hard-failure 评分测试；
3. 冻结 train/dev/test 或 template holdout，避免用测试表调提示词；
4. 如需历史回填，为 6 张日快照提供逐日 point-in-time ODS 输入；当前任务只允许
   捕获实际执行日状态，并在 metadata 中显式声明不支持历史 replay，避免制造伪历史。

当前已提供 `tools/build_benchmark_bundle.py`，可在源树外生成真正隔离的
`public/` 与 `evaluator/` 目录；prefixless 输出 412 个 opaque DDL、135 个 opaque
task，公开 SQL 中无层前缀和注释。`private_gold.yaml` 已生成 412 条符合
`benchmark_contract.yaml#table_record` 必填字段的 candidate 记录。
