# 溯源核对清单

本清单由 scripts/verify_numbers.py 从 out/seed_dataset.json 独立重算；聚合值只用于对账，不参与计算。发布版为 out/published_v2.md。

## 15 个抽样数字

| 序号 | 月报位置 | 来源表 | 计算口径 | 手算值 | 聚合值 | 发布版读数 | 结果 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 管理摘要 / 运行总次数 | runs | count(runs) | 210 | 210 | 210 | 一致 |
| 2 | 管理摘要 / 成功次数 | runs.status | count(status == success) | 207 | 207 | 207 | 一致 |
| 3 | 运行稳定性 / 退化事件 | incidents.type | count(type == degraded) | 2 | 2 | 2 | 一致 |
| 4 | 运行稳定性 / P0 失败 | incidents.type | count(type == p0_failure) | 1 | 1 | 1 | 一致 |
| 5 | 管理摘要 / 成功率 | runs.status | success / total × 100 | 98.5714 | 98.5714 | 98.5714 | 一致 |
| 6 | 管理摘要 / 事件总数 | incidents | count(incidents) | 3 | 3 | 3 | 一致 |
| 7 | 管理摘要 / 红队 | redteam_findings | count(redteam_findings) | 12 | 12 | 12 | 一致 |
| 8 | 管理摘要 / 复核事件 | review_events | count(review_events) | 3000 | 3000 | 3,000 | 一致 |
| 9 | 管理摘要 / accepted | review_events.decision | count(decision == accepted) | 2300 | 2300 | 2,300 | 一致 |
| 10 | 管理摘要 / rejected | review_events.decision | count(decision == rejected) | 700 | 700 | 700 | 一致 |
| 11 | 管理摘要 / 拒绝率 | review_events.decision | rejected / total × 100 | 23.3333 | 23.3333 | 23.3333 | 一致 |
| 12 | 工具质量排名 / low_sample | review_events.sample_group | count(sample_group == low_sample) | 19 | 19 | 19 | 一致 |
| 13 | 管理摘要 / p95 | runs.latency_ms | sorted(latency)[ceil(0.95×n)-1] | 4130 | 4130 | 4130 | 一致 |
| 14 | 管理摘要 / 平均质量分 | runs.quality_score | mean(quality_score) | 0.8481 | 0.8481 | 0.8481 | 一致 |
| 15 | 工具质量排名 / 排名范围 | review_events / tools | count(tools with reviews >= threshold) | 6 | 6 | 6 | 一致 |

## 全量类别对账

| 类别 | 手算值 | 聚合值 | 发布版可见 | 结果 |
| --- | --- | --- | --- | --- |
| 红队状态 open | 3 | 3 | 是 | 一致 |
| 红队状态 triaged | 3 | 3 | 是 | 一致 |
| 红队状态 in_progress | 2 | 2 | 是 | 一致 |
| 红队状态 fixed | 2 | 2 | 是 | 一致 |
| 红队状态 verified | 2 | 2 | 是 | 一致 |
| 拒绝原因 low_confidence | 100 | 100 | 是 | 一致 |
| 拒绝原因 policy_violation | 100 | 100 | 是 | 一致 |
| 拒绝原因 duplicate | 100 | 100 | 是 | 一致 |
| 拒绝原因 missing_context | 100 | 100 | 是 | 一致 |
| 拒绝原因 out_of_scope | 100 | 100 | 是 | 一致 |
| 拒绝原因 format_error | 100 | 100 | 是 | 一致 |
| 拒绝原因 manual_reject | 100 | 100 | 是 | 一致 |
| 复核数 tool-01 | 497 | 497 | 是 | 一致 |
| 复核数 tool-02 | 497 | 497 | 是 | 一致 |
| 复核数 tool-03 | 497 | 497 | 是 | 一致 |
| 复核数 tool-04 | 497 | 497 | 是 | 一致 |
| 复核数 tool-05 | 497 | 497 | 是 | 一致 |
| 复核数 tool-06 | 496 | 496 | 是 | 一致 |
| 复核数 tool-07 | 19 | 19 | 是 | 一致 |
| low_sample 阈值 | 30 | 30 | 是 | 一致 |
| P0 恢复运行 | run-20261112-tool-03 | run-20261112-tool-03 | 是 | 一致 |

结论：15 个抽样数字与全量类别全部一致。
