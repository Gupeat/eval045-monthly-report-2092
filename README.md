# EVAL-045 月报全流程演练

虚构会员空间平台的 2026-11 质量月报演练：固定种子生成数据，依次运行 EVAL-041 汇总、EVAL-042 归因、EVAL-043 渲染、EVAL-044 审阅发布，产出草稿、发布版 PDF/Markdown、溯源清单和问题清单。

所有数据均为虚构，不含真实会员、员工或客户信息。

## 快速开始

环境：Python 3.11+，并安装 python-docx、Pillow。生成 PDF 需要本机 Microsoft Edge 或 Chromium；可用 EDGE_BIN 指定可执行文件。

安装依赖并运行完整流水线：

    python -m pip install -e ".[dev]"
    python run_all.py

Windows 也可以使用：

    .\run_all.ps1

Linux/macOS 使用：

    ./run_all.sh

运行后生成：

- out/seed_dataset.json：固定种子 20261001 的 210 条运行、3 条事件、12 条红队发现、3000 条复核事件
- out/aggregate.json、out/attribution.json：EVAL-041/042 输出
- out/draft.md、out/draft.html、out/draft.docx：待审阅草稿
- out/published_v2.md、out/published_v2.html、out/published_v2.pdf：应用 3 条审阅意见后的发布版
- out/review_comments.json、out/publish_manifest.json：审阅意见与产物哈希
- run.log：五个阶段的退出码、耗时与产物 SHA-256
- trace_checklist.md：15 个抽样数字 + 21 项全量类别的来源、口径、手算值与比对结果
- issue_list.md：演练中发现的问题与建议工单
- artifacts/AC3-events.png：2 次退化 + 1 次 P0 的截图证据

## 验收命令

    python -m pytest -q
    python scripts/verify_numbers.py
    python scripts/eval_pii_scan.py --path out/seed_dataset.json
    python scripts/run_acceptance.py

run_acceptance.py 会先写 FAIL 证据，再依次跑 pytest、流水线、双种子哈希比对、15 个抽样数字 + 21 项类别核对、PII 扫描、AC3 截图和样张检查；全部通过后才写 PASS。它也校验 run.log 的阶段、退出码、产物 SHA，且启动时会删除旧证据，避免旧 PASS 残留。

## 数据口径

- 时间：2026-11-01 至 2026-11-30，7 个工具每天各 1 次夜间运行，共 210 次。
- 运行状态：207 次 success、2 次 degraded、失败 1 次；P0 失败在次日有恢复运行。
- 复核：3000 条 review_events；accepted 2300、rejected 700；7 类拒绝原因各 100 条。
- low_sample：tool-07 只有 19 条复核，低于阈值 30，标注为 low_sample，不参与默认质量排名。
- 红队：12 条发现，覆盖 open、triaged、in_progress、fixed、verified 五种状态。
- 百分比保留 4 位小数；p95 使用最近秩法。

## 固定种子与可重复性

种子为 20261001，时间从固定基准日推算。数据集使用 json.dumps(sort_keys=True, indent=2)，以 UTF-8 字节写入，换行固定为 LF。因此同一环境下两次生成的 JSON 字节与 SHA-256 完全一致；验收脚本会生成两个副本并做哈希比对。

## 上游替换点

EVAL-041..044 尚未作为上游模块交付，本仓库用 stubs/ 下的最小实现跑通流程。真实接入时保持以下命令行契约：

- stubs/eval041_aggregate.py --dataset <json> --out <json>
- stubs/eval042_attribute.py --dataset <json> --aggregate <json> --out <json>
- stubs/eval043_render.py --dataset <json> --aggregate <json> --attribution <json> --out-dir <dir>
- stubs/eval044_review_publish.py --dataset <json> --aggregate <json> --attribution <json> --draft <md> --out-dir <dir>

替换时保留 out/ 下的文件名，run_all.py 和 scripts/run_acceptance.py 不需要改。

## 已知限制

- eval-pii-scan 是本地 mock（scripts/eval_pii_scan.py，安装后也可用 `eval-pii-scan` 命令），只覆盖 email、手机号、身份证、银行卡、常见 token 模式，不等同平台扫描器。
- PDF 由本机 Edge/Chromium headless 渲染；没有浏览器的环境会失败，需设置 EDGE_BIN 或替换渲染器。
- 所有数据均为合成数据；本演练不连接真实会员、CRM 或平台数据库。
- low_sample 阈值固定为 30；变更阈值需要同时更新报告与核对清单。

## 目录

    seed_month.py             固定种子数据生成器
    run_all.py                五阶段流水线
    stubs/                    EVAL-041..044 最小实现
    scripts/                  验收、溯源、PII 扫描、AC3 截图
    tests/                    15 个 pytest 回归
    out/                      生成产物（含发布版 PDF/Markdown）
    artifacts/                AC3 截图与验收/扫描证据

## 证据与审阅

- 发布版报告中的 3 条审阅意见见 out/review_comments.json。
- AC3 截图由 scripts/make_ac3_shot.py 从种子数据重新生成。
- 最终验收状态见 artifacts/acceptance.json 与 artifacts/ACCEPTANCE.md。
