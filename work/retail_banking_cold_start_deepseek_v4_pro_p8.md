# retail_banking 冷启动 Benchmark：DeepSeek V4 Pro / 并发 8

## 运行配置

- 时间：2026-07-11 14:00:06–14:20:18（Asia/Shanghai），约 20 分 12 秒
- 模型：`deepseek-v4-pro`
- Endpoint：`https://api.deepseek.com/chat/completions`
- 并发：8
- 最大重试：1
- 单请求超时：240 秒
- `no_cache`：true
- 输入物理表：412（ODS 277、DIM 35、DWD 69、DWS 18、ADS 13）
- LLM 巡检表：122（DIM/DWD/DWS）；ODS 与 ADS 由当前 runner 固定为边界层
- API 调用：143（122 首次 + 21 次重试）

## 结果

总的 middle-layer accuracy 为 **81.15%（99/122）**。

| 期望层 | 正确 | 总数 | Accuracy |
|---|---:|---:|---:|
| DIM | 33 | 35 | 94.29% |
| DWD | 61 | 69 | 88.41% |
| DWS | 5 | 18 | 27.78% |
| DIM + DWD | 94 | 104 | 90.38% |

混淆矩阵：

| 期望 → 预测 | 数量 |
|---|---:|
| DIM → DIM | 33 |
| DIM → DWD | 2 |
| DWD → DWD | 61 |
| DWD → DIM | 6 |
| DWD → DWS | 1 |
| DWD → ADS | 1 |
| DWS → DWS | 5 |
| DWS → ADS | 13 |

生成结果包含 412 个 model、200 个指标，44 张表识别到指标，102 张表识别到实体，
8 张表生成 grain。最终目录新增 38 个业务过程和 37 个语义主题。

## 校验状态

- passed：102
- blocked：20
- metadata warning：37（可与 passed/blocked 重叠）
- 发生重试：21 张表
- API/认证/网络超时失败：0

20 张 blocked 中，18 张是全部 DWS，另外两张是
`gl_aggregation_summary` 和 `loan_arrears_snapshot`。主要校验问题：

- `missing_primary_entities`：18 次；
- `invalid_base_metric_tables`：24 个字段；
- `invalid_base_metrics`：3 个字段。

## 主要错例

- DWS → ADS（13）：`account_transfer_daily`、`cashier_transaction_daily`、
  `client_transaction_daily`、`collection_action_daily`、
  `deposit_hold_event_daily`、`gl_journal_posting_daily`、
  `loan_disbursement_daily`、`loan_installment_charge_due_current`、
  `loan_installment_due_daily`、`loan_ownership_settlement_daily`、
  `office_cash_transfer_daily`、`wc_breach_start_daily`、
  `wc_loan_transaction_daily`。
- DWD → DIM（6）：`bridge_group_customer`、`bridge_office_holiday`、
  `bridge_product_gl_mapping`、`deposit_officer_assignment`、
  `loan_guarantor_relation`、`staff_assignment`。
- DIM → DWD（2）：`bridge_loan_rate`、`working_day_rule`。
- DWD → DWS：`gl_aggregation_summary`。
- DWD → ADS：`loan_arrears_snapshot`。

## Catalog 结果

- Business process：期望 28、生成 38；原始 exact overlap 为 0（生成代码为大写）。
  case-insensitive overlap 仍只有 4，precision 10.53%、recall 14.29%、F1 12.12%。
- Semantic subject：期望 35、生成 37、overlap 17，precision 45.95%、
  recall 48.57%、F1 47.22%。

## 重要解释边界

本轮分数是现有 `benchmarks/table_inspector_layer/run.py` 的 layer benchmark，不能直接
等同于 `benchmark/private_gold.yaml` 定义的完整语义分数：

1. runner 固定 ODS/ADS，只评价 DIM/DWD/DWS；
2. 临时 lineage 只有表节点、没有真实上下游边。DWS 的 downstream count 因此为 0，
   prompt 很容易把终端日汇总判为 ADS，这与 13/18 的 DWS→ADS 高度一致；
3. 122 张候选表的 declared layer 初始均为 DWD。18 张 DWS 虽识别出聚合指标，仍全部被
   DWD 的 primary-entity/base-metric 校验阻断，说明 layer resolution 与字段校验顺序会
   系统性压低 DWS 结果；
4. 当前报告没有完整评分 grain、指标公式、可加性、敏感性和允许替代答案；
5. runner 未保存 DeepSeek `usage`，因此只能确认 143 次调用，不能给出精确 token/费用。

建议下一轮先让 runner 重写并保留真实 lineage edge，再按推断/解析后的层执行字段规则，
并对 catalog code 做 case/canonical normalization，之后再运行一次可比的修正版 benchmark。

## 产物

- JSON 报告：`work/retail_banking_cold_start_deepseek_v4_pro_p8.json`
- 临时生成项目：
  `/private/tmp/retail_banking_cold_start_v4pro_p8/warehouses/retail_banking_generate_llm_benchmark`
- LLM cache：临时项目下 `artifacts/assessment/cache/inspect.json`
