**AGENT DOCTOR**

**AI Agent 自动调试、因果归因与验证修复平台**

产品战略 · 技术架构 · MVP · 开源商业化路线

  ----------------------------------------------------------------------------------
  **核心命题\**
  不是"告诉开发者 Agent 哪里看起来有问题"，而是通过可控实验与 counterfactual
  replay，证明故障由什么因素导致，并验证最小修复是否真正解决根因、是否引入新回归。
  ----------------------------------------------------------------------------------

  ----------------------------------------------------------------------------------

版本：v0.1 \| 日期：2026-08-23 \| 文档性质：产品/技术规划草案

# 目录

1\. 执行摘要

2\. 问题定义：Agent 为什么难调试

3\. 产品定位与价值主张

4\. 用户与典型场景

5\. 市场与竞争格局

6\. 产品工作流：Observe → Intervene → Attribute → Repair → Verify

7\. 核心技术架构

8\. Canonical Trace：统一轨迹数据模型

9\. Safe Replay：安全、可重复的重放系统

10\. Intervention Engine：可控干预与故障注入

11\. Causal Attribution：从相关性到因果证据

12\. Experiment Planner：用最少实验区分根因

13\. Repair Engine：最小可逆修复

14\. Verification & Regression：证明修复没有副作用

15\. Agent Eval 指标体系

16\. MVP 范围与明确不做的事情

17\. 12 周实施路线

18\. 开源 → 闭源产品策略

19\. 商业模式与定价假设

20\. 技术护城河与数据飞轮

21\. 研究路线与可发表问题

22\. 风险、失败模式与缓解方案

23\. Demo 设计

24\. Repository / API 草案

25\. 成功标准与下一步

附录 A：竞争对手功能矩阵

附录 B：示例诊断报告

附录 C：公开参考资料

# 1. 执行摘要

Agent Doctor 是一个面向 AI Agent
的自动调试与修复验证平台。它的目标不是再做一个通用
tracing、observability 或 eval
dashboard，而是解决更接近软件工程调试的问题：一次 Agent
失败后，系统能否复现现场、提出可检验的根因假设、通过受控干预验证因果关系、生成最小修复，并用回归集证明修复没有伤害其他能力。

  -----------------------------------------------------------------------
  **一句话定位\**
  Root cause your AI agent with experiments, not guesses. /
  用实验而不是猜测定位 Agent 根因。
  -----------------------------------------------------------------------

  -----------------------------------------------------------------------

## 1.1 产品最终形态

+-----------------------------------------------------------------------+
| Production Incident                                                   |
|                                                                       |
| ↓                                                                     |
|                                                                       |
| Reconstruct Trace & State                                             |
|                                                                       |
| ↓                                                                     |
|                                                                       |
| Safe Replay Sandbox                                                   |
|                                                                       |
| ↓                                                                     |
|                                                                       |
| Generate Competing Hypotheses                                         |
|                                                                       |
| ↓                                                                     |
|                                                                       |
| Controlled Interventions                                              |
|                                                                       |
| ↓                                                                     |
|                                                                       |
| Causal Attribution + Confidence                                       |
|                                                                       |
| ↓                                                                     |
|                                                                       |
| Minimal Repair Candidate                                              |
|                                                                       |
| ↓                                                                     |
|                                                                       |
| Regression Verification                                               |
|                                                                       |
| ↓                                                                     |
|                                                                       |
| Verified Patch / PR Gate                                              |
+=======================================================================+

## 1.2 为什么现在值得做

- Agent eval、tracing、dataset、experiment、CI regression
  已经逐渐基础设施化，说明企业愿意为"可靠上线"付费。

- 现有产品越来越擅长回答"发生了什么""哪一步失败""改完之后总体指标有没有变"，但"为什么失败"往往仍依赖启发式分析或
  LLM judge。

- 2026 年的 AgentChaos 与 Causal Agent Replay 等研究/开源项目说明：fault
  injection 与 counterfactual attribution
  已经成为真实研究问题，但仍处于早期，尤其在生产级安全重放、跨 stack
  归因和自动实验规划上。

- 真正可形成差异的不是再做一个 Agent Eval，而是构建"实验驱动的 Agent
  Debugger"。

## 1.3 核心差异

  ------------------------------------------------------------------------------
  **传统 Eval / Observability**       **Agent Doctor**
  ----------------------------------- ------------------------------------------
  记录 trace / 打分                   重建可实验的失败现场

  LLM 判断哪一步有问题                通过 intervention 改变量并重跑

  相关性 / 解释性结论                 因果效应 + 置信区间 + 可复现实验证据

  给出修改建议                        生成最小 patch 并自动验证

  单点 case 修复                      相似案例 + unrelated regression 一起验证

  主要关注 prompt/model/tool          把
                                      serving、retry、cache、latency、provider
                                      也作为根因候选
  ------------------------------------------------------------------------------

# 2. 问题定义：Agent 为什么难调试

传统软件调试通常依赖确定性输入、可重放程序状态、明确调用栈与较稳定的环境。Agent
系统恰好相反：模型具有随机性，工具与外部 API
有副作用，检索内容会变化，provider latency 与 rate limit
会改变执行路径，重试可能污染 state，甚至 temperature=0 也不能保证 hosted
provider 的 bit-level determinism。

## 2.1 典型错误链

+-----------------------------------------------------------------------+
| tool latency spikes                                                   |
|                                                                       |
| ↓                                                                     |
|                                                                       |
| timeout                                                               |
|                                                                       |
| ↓                                                                     |
|                                                                       |
| retry appends stale observation                                       |
|                                                                       |
| ↓                                                                     |
|                                                                       |
| planner sees duplicated context                                       |
|                                                                       |
| ↓                                                                     |
|                                                                       |
| wrong tool selected                                                   |
|                                                                       |
| ↓                                                                     |
|                                                                       |
| refund executed twice                                                 |
|                                                                       |
| ↓                                                                     |
|                                                                       |
| final outcome = failure                                               |
+=======================================================================+

只看最终 trace，开发者很容易把最后一步"wrong tool
selected"误判成模型能力问题。但如果把 latency 正常化后失败率从 41% 降到
5%，而替换模型几乎没有改善，那么真正的修复点应该在
serving/retry/state，而不是购买更昂贵的模型。

## 2.2 我们要解决的五个问题

> 1\. 如何把一次 production run 记录为足够完整、可以重新实验的 Canonical
> Trace？
>
> 2\. 如何在不重复退款、发邮件、删库等副作用的前提下安全 replay？
>
> 3\. 如何区分 model / prompt / retrieval / tool / serving /
> orchestrator 等多个竞争性根因？
>
> 4\. 如何用尽量少的 counterfactual runs 获得足够可信的因果证据？
>
> 5\. 如何把诊断结果变成最小修复，并证明修复没有造成新的 regression？

# 3. 产品定位与价值主张

## 3.1 不做什么

- 不把"Agent Eval Platform"作为主定位：市场已经有
  Langfuse、Braintrust、Galileo、LangSmith、Phoenix 等成熟玩家。

- 不把"Chaos Engineering for Agents"本身作为唯一创新：已有
  AgentChaos、Chaosync 以及相关开源工作。

- 不把"production trace replay"本身作为唯一卖点：Taso 已经明确在做
  production-like sandbox replay 与 baseline/challenger change
  verification。

- 不把"让 LLM 看 trace 后生成 root cause"作为技术核心：这很容易被现有
  observability/eval 平台复制。

## 3.2 要占的位置

  -----------------------------------------------------------------------
  **定位\**
  Agent Incident Autopsy / Agent Causal
  Debugger：从生产事故出发，以实验为中心完成 Reproduce → Diagnose →
  Intervene → Attribute → Repair → Verify。
  -----------------------------------------------------------------------

  -----------------------------------------------------------------------

## 3.3 对客户的直接价值

  ------------------------------------------------------------------------------
  **客户问题**                        **产品价值**
  ----------------------------------- ------------------------------------------
  "到底是模型差还是基础设施有 bug？"  通过跨 stack intervention 分离 model 与
                                      serving/tool/retrieval 影响。

  "这个 prompt 修改真的修了吗？"      同一 incident + variants + unrelated
                                      regression 自动验证。

  "为什么昨天成功率突然掉了？"        将 production failure cluster
                                      转成可重放实验并定位根因。

  "我不敢对退款/支付 Agent 做         cassette + tool virtualization + sandbox
  replay。"                           state 避免真实副作用。

  "每个失败都要人工盯 trace 太慢。"   自动生成假设、优先选择信息量最高的实验。
  ------------------------------------------------------------------------------

# 4. 用户与典型场景

## 4.1 目标用户

  ---------------------------------------------------------------------------------
  **用户**                **核心痛点**                      **第一价值**
  ----------------------- --------------------------------- -----------------------
  AI/Agent Engineer       trace 很长、错误难复现            自动复现 + root-cause
                                                            evidence

  Backend / Platform      怀疑                              跨 stack 干预实验
  Engineer                retry、timeout、cache、provider   

  AI Infra / SRE          线上 incident 需要可证明根因      failure cluster +
                                                            reliability regression

  ML/LLM Engineer         不知道该改 prompt、model 还是     Repair Ladder +
                          fine-tune                         最小修改

  Engineering Manager     上线前无法量化 change risk        verified patch /
                                                            release gate
  ---------------------------------------------------------------------------------

## 4.2 第一批最适合的场景

- 客服/退款 Agent：工具有强副作用，policy gate 明确，容易定义
  success/failure。

- 内部运营 Agent：会调用 CRM、工单、数据库、邮件等多个工具，retry/state
  bug 价值高。

- RAG + tool Agent：可同时研究 retrieval、context、model、tool latency
  的耦合。

- 代码/DevOps Agent：可用测试作为 deterministic outcome grader，便于验证
  attribution 与 repair。

# 5. 市场与竞争格局（截至 2026-08-23）

当前市场已经证明"Agent
可靠性"是一个真实赛道，但不同公司占据的层次不同。Agent Doctor 不应与
tracing/eval 正面竞争，而应位于 observation 与 verification 之间更深的
experimental debugging 层。

  ---------------------------------------------------------------------------------------------------------------------------------------
  **玩家**          **公开能力重点**                                     **与本项目重叠**   **仍可差异化的地方**
  ----------------- ---------------------------------------------------- ------------------ ---------------------------------------------
  Galileo           Agent Reliability；Graph/trace；failure              高                 把"解释型 RCA"升级为受控实验与因果证据
                    mode；root-cause recommendations；tool/flow metrics                     

  Braintrust        数据集、scorer、step/trace                           中高               主动实验规划、跨 stack
                    eval、production→eval、CI、sandbox/fault-injection                      attribution、自动修复闭环
                    指南                                                                    

  Langfuse          开源 tracing、datasets、experiments、online/offline  中                 不争 observability；作为上游 trace source
                    eval、CI regression                                                     集成

  Taso              production traces→runnable env；baseline/challenger  高                 从"验证 change"转向"寻找 root cause
                    replay；change-impact report；real tools                                的干预实验"

  AgentChaos        非侵入式 LLM API runtime fault injection；65 fault   中                 扩展到
                    configs；robustness research                                            tool/retrieval/serving/orchestrator，并连接
                                                                                            repair

  Causal Agent      step-level do-intervention；counterfactual           很高               生产级 safe replay、跨 stack
  Replay            replay；effect/CI；Shapley attribution                                  variable、experiment planner、repair
                                                                                            verification
  ---------------------------------------------------------------------------------------------------------------------------------------

  -----------------------------------------------------------------------
  **竞争判断\**
  "Agent Eval"已经拥挤；"Agent Chaos"已有人做；"Counterfactual
  Replay"已有研究与 OSS。仍值得切的是：生产级 Safe Replay + 跨 Stack
  因果归因 + 主动实验规划 + Verified Repair 的完整闭环。
  -----------------------------------------------------------------------

  -----------------------------------------------------------------------

# 6. 产品工作流：Observe → Intervene → Attribute → Repair → Verify

## 6.1 用户体验

+-----------------------------------------------------------------------+
| \$ agentdoctor diagnose incident_827.json                             |
|                                                                       |
| FAILURE: unauthorized refund                                          |
|                                                                       |
| TOP HYPOTHESES                                                        |
|                                                                       |
| 1\. retry/state corruption 0.47                                       |
|                                                                       |
| 2\. ambiguous system prompt 0.31                                      |
|                                                                       |
| 3\. model decision instability 0.14                                   |
|                                                                       |
| 4\. retrieval 0.08                                                    |
|                                                                       |
| PLANNED EXPERIMENTS                                                   |
|                                                                       |
| E1 normalize tool latency                                             |
|                                                                       |
| E2 replay with clean retry state                                      |
|                                                                       |
| E3 ablate suspect prompt rule                                         |
|                                                                       |
| E4 resample model policy                                              |
|                                                                       |
| ROOT CAUSE (after 42 runs)                                            |
|                                                                       |
| retry/state corruption                                                |
|                                                                       |
| Estimated causal contribution: 0.72                                   |
|                                                                       |
| 95% CI: \[0.61, 0.82\]                                                |
|                                                                       |
| SUGGESTED PATCH                                                       |
|                                                                       |
| retry_policy.append_previous_observation = false                      |
|                                                                       |
| VERIFICATION                                                          |
|                                                                       |
| 27/27 production incidents fixed                                      |
|                                                                       |
| 198/200 synthetic variants pass                                       |
|                                                                       |
| No significant unrelated regression                                   |
+=======================================================================+

## 6.2 关键原则

- Root cause 必须和实验 evidence 绑定，而不是只输出自然语言解释。

- 每个 repair 都需要 before/after comparison 与 regression guard。

- 所有具有副作用的 tool 默认不能在真实 production 重放。

- 因果结论必须允许"不确定"：输出 effect、confidence interval、residual
  nondeterminism。

- 平台应能作为 Langfuse/Braintrust/OTel 等 tracing
  工具的下游，而不是要求客户迁移全部 observability。

# 7. 核心技术架构

+-----------------------------------------------------------------------+
| Agent SDK / OTel / Existing Trace Platform                            |
|                                                                       |
| │                                                                     |
|                                                                       |
| ▼                                                                     |
|                                                                       |
| ┌─────────────────┐                                                   |
|                                                                       |
| │ Trace Ingestor │                                                    |
|                                                                       |
| └────────┬────────┘                                                   |
|                                                                       |
| ▼                                                                     |
|                                                                       |
| ┌─────────────────┐                                                   |
|                                                                       |
| │ Canonical Trace │                                                   |
|                                                                       |
| │ + State Snapshot│                                                   |
|                                                                       |
| └────────┬────────┘                                                   |
|                                                                       |
| ▼                                                                     |
|                                                                       |
| ┌─────────────────┐                                                   |
|                                                                       |
| │ Safe Replay │◄──── Cassette / Mock / Sandbox                        |
|                                                                       |
| └────────┬────────┘                                                   |
|                                                                       |
| ▼                                                                     |
|                                                                       |
| ┌─────────────────┐                                                   |
|                                                                       |
| │ Hypothesis Eng. │                                                   |
|                                                                       |
| └────────┬────────┘                                                   |
|                                                                       |
| ▼                                                                     |
|                                                                       |
| ┌─────────────────┐                                                   |
|                                                                       |
| │ Experiment │                                                        |
|                                                                       |
| │ Planner │                                                           |
|                                                                       |
| └────────┬────────┘                                                   |
|                                                                       |
| ▼                                                                     |
|                                                                       |
| Model / Prompt / Retrieval / Tool / Serving Interventions             |
|                                                                       |
| │                                                                     |
|                                                                       |
| ▼                                                                     |
|                                                                       |
| ┌─────────────────┐                                                   |
|                                                                       |
| │ Attribution Eng.│                                                   |
|                                                                       |
| └────────┬────────┘                                                   |
|                                                                       |
| ▼                                                                     |
|                                                                       |
| ┌─────────────────┐                                                   |
|                                                                       |
| │ Repair Engine │                                                     |
|                                                                       |
| └────────┬────────┘                                                   |
|                                                                       |
| ▼                                                                     |
|                                                                       |
| ┌─────────────────┐                                                   |
|                                                                       |
| │ Regression Gate │                                                   |
|                                                                       |
| └─────────────────┘                                                   |
+=======================================================================+

## 7.1 组件职责

  --------------------------------------------------------------------------------------
  **组件**                **职责**                             **MVP 技术建议**
  ----------------------- ------------------------------------ -------------------------
  Trace Ingestor          采集                                 Python SDK +
                          model/tool/retrieval/latency/state   OpenTelemetry

  Canonical Trace         统一不同 Agent framework 的语义      Pydantic schema +
                                                               JSONL/Parquet

  Replay Runtime          重放模型决策与外部依赖               async Python runtime

  Tool Virtualization     拦截有副作用的工具                   cassette + policy +
                                                               mock/sandbox

  Intervention Engine     对变量做 do-style 操作               typed intervention API

  Experiment Planner      选择下一次实验                       规则版→Bayesian/active
                                                               info gain

  Attribution Engine      计算 effect 与置信区间               Monte Carlo + bootstrap /
                                                               contrastive

  Repair Engine           生成最小可逆 patch                   prompt/tool/config/code
                                                               templates + LLM

  Regression Runner       验证 original/variants/unrelated     pytest-style runner + CI
  --------------------------------------------------------------------------------------

# 8. Canonical Trace：统一轨迹数据模型

Replay 和 causal diagnosis 的基础不是漂亮的 trace
UI，而是"足够完整的可实验状态"。Canonical Trace 必须记录决策时 Agent
看见了什么、调用了什么、工具返回什么、系统延迟/错误是什么，以及哪些外部状态不可安全重放。

## 8.1 建议的数据结构

+-----------------------------------------------------------------------+
| Trace {                                                               |
|                                                                       |
| trace_id, run_id, agent_version, environment,                         |
|                                                                       |
| initial_input, final_output, outcome,                                 |
|                                                                       |
| steps: \[                                                             |
|                                                                       |
| Step {                                                                |
|                                                                       |
| index, timestamp, type,                                               |
|                                                                       |
| prompt_snapshot, message_history, model_config,                       |
|                                                                       |
| action, tool_name, tool_args,                                         |
|                                                                       |
| observation, retrieval_docs,                                          |
|                                                                       |
| latency_ms, retry_count, error,                                       |
|                                                                       |
| state_hash, side_effect_class, provenance                             |
|                                                                       |
| }                                                                     |
|                                                                       |
| \],                                                                   |
|                                                                       |
| external_dependencies,                                                |
|                                                                       |
| grader_results,                                                       |
|                                                                       |
| reproducibility_metadata                                              |
|                                                                       |
| }                                                                     |
+=======================================================================+

## 8.2 必须记录的 provenance

- 模型 provider/model/version/endpoint、temperature、seed（如果存在）。

- system prompt、tool schema、MCP server/schema version。

- 检索 query、top-k、文档 ID/version、embedding/index version。

- HTTP/tool latency、status code、retry/backoff、cache hit/miss。

- agent code revision、orchestrator version、feature flags。

- 每个 tool 的 side-effect class：read-only / idempotent-write /
  destructive-write / external-payment。

# 9. Safe Replay：安全、可重复的重放系统

## 9.1 三种 replay 模式

  ---------------------------------------------------------------------------------
  **模式**                **用途**                     **风险**
  ----------------------- ---------------------------- ----------------------------
  Cassette Replay         直接返回录制过的             真实性较低；不反映外部变化
                          tool/retrieval 结果；最稳定  

  Sandbox Replay          在隔离 DB/API 环境执行真实   搭建成本高，但适合写操作
                          tool                         

  Live Read-only Replay   对只读外部依赖进行真实调用   存在数据漂移与网络
                                                       nondeterminism
  ---------------------------------------------------------------------------------

## 9.2 Tool virtualization policy

+-----------------------------------------------------------------------+
| read_only_tool → live or cassette                                     |
|                                                                       |
| idempotent_write → sandbox by default                                 |
|                                                                       |
| destructive_write → mock/sandbox only                                 |
|                                                                       |
| payment/refund/email → never live during causal replay                |
+=======================================================================+

## 9.3 Replay fidelity 指标

- Action Match Rate：无干预 replay 与原 run 的 action/tool 选择一致率。

- State Match Rate：关键 state hash 一致率。

- Observation Fidelity：重放 observation 与原始 observation
  的相似/等价程度。

- Residual Nondeterminism：即使控制变量后仍无法消除的随机性。

- Replay Safety：是否触发真实副作用；目标必须为 0。

# 10. Intervention Engine：可控干预与故障注入

## 10.1 干预维度

  -----------------------------------------------------------------------------
  **层**                              **示例 Intervention**
  ----------------------------------- -----------------------------------------
  Model                               替换
                                      provider/model；固定/改变采样；resample
                                      决策

  Prompt                              删除/替换单条 instruction；改
                                      few-shot；改 policy boundary

  Context                             删除 stale history；截断/恢复消息；改变
                                      memory

  Retrieval                           gold docs；空检索；固定排名；改变
                                      top-k；stale docs

  Tool                                改变 schema/description；异常；malformed
                                      JSON；错误值

  Serving                             latency；timeout；429/5xx；stream
                                      cut；cache；retry/backoff

  Orchestrator                        改变 max
                                      steps、router、handoff、retry/state merge

  Environment                         DB snapshot、feature
                                      flag、clock、external service state
  -----------------------------------------------------------------------------

## 10.2 Intervention API 草案

+-----------------------------------------------------------------------+
| with intervene(trace) as x:                                           |
|                                                                       |
| x.tool(\"search_orders\").latency(ms=100)                             |
|                                                                       |
| x.retry_policy(clear_stale_observation=True)                          |
|                                                                       |
| x.prompt.replace(rule_id=\"refund_policy\", text=NEW_RULE)            |
|                                                                       |
| result = replay.run(n=20)                                             |
+=======================================================================+

# 11. Causal Attribution：从相关性到因果证据

最核心的技术主张是：把"root cause"从 trace pattern matching 或 LLM
explanation，升级为 intervention-based evidence。对某个变量 X
做干预，如果在其他条件尽可能固定时 outcome Y
的失败概率显著变化，则可以估计 X 对失败的因果贡献。

## 11.1 基础 effect

+-----------------------------------------------------------------------+
| Effect(X) = P(failure \| baseline) - P(failure \| do(X = patched))    |
|                                                                       |
| Example:                                                              |
|                                                                       |
| Baseline failure = 0.41                                               |
|                                                                       |
| Normalize latency failure = 0.06                                      |
|                                                                       |
| Estimated effect = 0.35 (35 percentage points)                        |
+=======================================================================+

## 11.2 需要输出什么

- Point estimate：失败概率变化或业务损失变化。

- Confidence interval：避免把随机 LLM 波动包装成确定结论。

- Replay fidelity：如果重放本身不稳定，要显式降低结论可信度。

- Competing hypotheses：不能只测试一个最喜欢的解释，要与替代解释比较。

- Interaction effects：例如 latency × retry policy
  共同导致失败，单变量可能都不充分。

## 11.3 第一版不要追求完美"因果发现"

MVP 更现实的做法是"候选根因集合 + 受控对照实验 + effect
ranking"，而不是宣称从任意复杂多 Agent 系统自动恢复完整 causal
graph。只要可以稳定区分几类高价值问题（prompt vs model、retrieval vs
model、latency/retry vs model），就已经具有产品价值。

# 12. Experiment Planner：用最少实验区分根因

暴力枚举干预会迅速产生数千次模型调用。Experiment Planner
的目标是：在当前证据下，选择最能区分 competing hypotheses
的下一次实验。这个组件既能降低成本，也可能成为长期技术护城河。

## 12.1 V0：规则式

- 如果出现 timeout/retry/error → 优先 normalize serving + replay clean
  state。

- 如果 wrong tool 且 tool descriptions 高度相似 → 优先
  schema/description ablation。

- 如果回答缺信息且 retrieval recall 异常 → 优先 gold-context
  intervention。

- 如果相同 context 下 decision variance 高 → 优先 policy resampling /
  model swap。

## 12.2 V1：Bayesian hypothesis updating

+-----------------------------------------------------------------------+
| P(H_i \| evidence) ∝ P(evidence \| H_i) P(H_i)                        |
|                                                                       |
| Choose next experiment e\* = argmax_e ExpectedInformationGain(e) /    |
| Cost(e)                                                               |
+=======================================================================+

## 12.3 成本目标

产品要避免"诊断一个 incident 比 incident 本身贵 1000
倍"。早期可以设定默认预算，例如每个 incident 20--60 次 counterfactual
run，超过预算必须解释为什么继续。

# 13. Repair Engine：最小可逆修复

## 13.1 Repair Ladder

+-----------------------------------------------------------------------+
| Low risk / reversible                                                 |
|                                                                       |
| 1\. Context patch                                                     |
|                                                                       |
| 2\. Prompt patch                                                      |
|                                                                       |
| 3\. Tool description/schema patch                                     |
|                                                                       |
| 4\. Agent policy / retry / state patch                                |
|                                                                       |
| 5\. Retrieval configuration patch                                     |
|                                                                       |
| 6\. Application code patch                                            |
|                                                                       |
| 7\. Adapter / LoRA fine-tune                                          |
|                                                                       |
| 8\. Localized model editing                                           |
|                                                                       |
| High risk / hard to reverse                                           |
+=======================================================================+

原则：如果一条 tool description 就能修，就不要 fine-tune；如果 retry
state 才是根因，就不要通过换更贵模型"掩盖"基础设施问题。

## 13.2 修复候选评分

  -----------------------------------------------------------------------
  **维度**                            **说明**
  ----------------------------------- -----------------------------------
  Expected Fix Rate                   预计对当前 failure cluster 的改善

  Regression Risk                     对其他任务/能力的潜在伤害

  Operational Risk                    部署、回滚、权限和数据风险

  Cost Impact                         token/API/infra 成本变化

  Latency Impact                      p50/p95 延迟变化

  Reversibility                       是否可一键回滚

  Evidence Strength                   根因诊断证据有多强
  -----------------------------------------------------------------------

# 14. Verification & Regression：证明修复没有副作用

## 14.1 三层测试集

  -----------------------------------------------------------------------
  **集合**                            **目的**
  ----------------------------------- -----------------------------------
  A. Original Incident                确认原始事故已修复

  B. Incident Variants                避免只过一个具体 prompt；测试泛化

  C. Unrelated Regression Set         检查对其他业务/agent 行为的副作用
  -----------------------------------------------------------------------

## 14.2 Patch Verification 报告

+-----------------------------------------------------------------------+
| PATCH VERIFIED                                                        |
|                                                                       |
| Root cause confidence 0.89                                            |
|                                                                       |
| Original incident FAIL → PASS                                         |
|                                                                       |
| Similar cases 79% → 98%                                               |
|                                                                       |
| Unrelated tasks 94.2% → 94.1%                                         |
|                                                                       |
| Tool error rate 8.1% → 1.3%                                           |
|                                                                       |
| Cost/run +3.8%                                                        |
|                                                                       |
| p95 latency +1.7%                                                     |
|                                                                       |
| Decision: SAFE TO REVIEW                                              |
+=======================================================================+

## 14.3 自动生成回归测试

每一个确认的生产事故都应该沉淀为 regression asset：原 trace、期望 policy
boundary、replay
environment、grader、修复前后结果。这样产品会形成"越用越难复发"的数据飞轮。

# 15. Agent Eval 指标体系

产品本身仍需要一套完整的 Agent Eval
指标，但它们是诊断输入，不是产品差异化本身。建议分
outcome、trajectory、tool、recovery、efficiency、replay/diagnosis 七类。

  --------------------------------------------------------------------------
  **类别**                            **指标示例**
  ----------------------------------- --------------------------------------
  Outcome                             Task Success、Business Rule
                                      Pass、End-state correctness

  Tool                                Tool Selection Accuracy、Argument
                                      Accuracy、Tool Error Rate

  Trajectory                          Action Correctness、Loop
                                      Rate、Premature Stop、Step Efficiency

  Recovery                            Timeout Recovery、Retry
                                      Correctness、Fallback Success、Failure
                                      Containment

  Retrieval                           Recall@k、Context
                                      Sufficiency、Staleness、Groundedness

  Efficiency                          Tokens、Cost/run、p50/p95
                                      latency、Steps/run

  Replay                              Action Match、State Match、Residual
                                      Nondeterminism

  Diagnosis                           Root-cause accuracy、Top-k causal
                                      recall、Experiment
                                      cost、Time-to-evidence

  Repair                              Fix rate、Regression rate、Rollback
                                      rate、Patch size
  --------------------------------------------------------------------------

# 16. MVP 范围与明确不做的事情

## 16.1 MVP 支持

- Python。

- OpenAI-compatible chat/tool calling；可额外接 Anthropic adapter。

- Single-agent tool loop。

- Function calling / MCP 风格工具。

- 简单 RAG trace（query + retrieved docs + rank）。

- JSON/JSONL trace；CLI 优先。

- 四类干预：Model/Prompt、Tool、Retrieval、Serving/Retry。

- Cassette replay + mock/sandbox hooks。

## 16.2 MVP 明确不做

- 复杂 multi-agent coordination。

- Computer-use/browser GUI replay。

- 自动修改闭源模型权重。

- 完整企业 dashboard。

- 全自动 causal graph discovery。

- 在 production 对支付/删除/邮件等副作用工具进行 live replay。

  -----------------------------------------------------------------------
  **MVP 判断标准\**
  只要能稳定完成两个强 demo：① 证明"看似模型差，其实是 serving/retry"；②
  定位一个具体 prompt/tool policy 缺陷并自动生成、验证
  patch，就足够进入开源发布。
  -----------------------------------------------------------------------

  -----------------------------------------------------------------------

# 17. 12 周实施路线

  ----------------------------------------------------------------------------------------
  **周**                  **里程碑**              **交付物/验收**
  ----------------------- ----------------------- ----------------------------------------
  1--2                    V0 Trace                Canonical schema；OpenAI tool-call
                                                  recorder；trace JSON；基础 graders

  3--4                    V0 Replay               cassette tool replay；model
                                                  replay；action-match/reproducibility
                                                  report

  5                       Fault Injection         latency/timeout/429/5xx/malformed/tool
                                                  error/retrieval ablation

  6                       Serving demo            构造 latency→retry→stale-state
                                                  failure；能通过干预识别

  7--8                    Attribution V0          候选假设；A/B intervention；Monte Carlo
                                                  effect + CI；ranking

  9                       Prompt/Tool repair      生成 prompt/tool schema
                                                  patch；diff；自动应用到 sandbox

  10                      Regression              original + variants + unrelated
                                                  suite；before/after report

  11                      CLI polish              diagnose / replay / intervene /
                                                  verify；HTML/Markdown report 可选

  12                      Open-source launch      README、两个
                                                  demo、benchmark、architecture
                                                  doc、GitHub Action skeleton
  ----------------------------------------------------------------------------------------

## 17.1 第一个月只看三个工程指标

- Replay fidelity：无干预时能否较高概率重现相同关键 action。

- Safety：所有 destructive side effects 是否被成功隔离。

- Attribution sanity：在"人为植入已知根因"的 synthetic benchmark
  上能否找回 ground truth。

# 18. 开源 → 闭源产品策略

## 18.1 开源层：开发者一个人就能用

- Canonical trace schema 与 recorder。

- 本地 cassette replay runtime。

- Intervention API 与基础 fault injectors。

- 基础 counterfactual effect 计算。

- CLI / pytest integration。

- 少量 demo benchmark 与可扩展 adapter interface。

## 18.2 商业层：团队、规模和 intelligence

- Production incident ingestion 与 failure clustering。

- Managed sandbox / snapshot / parallel replay fleet。

- Experiment Planner 与自动 hypothesis generation。

- 跨 stack causal attribution engine。

- Automatic repair + large regression execution。

- 历史 incident intelligence、团队协作、RBAC/SSO/Audit/VPC。

  -----------------------------------------------------------------------
  **商业化原则\**
  Open-source the experimental runtime. Monetize the intelligence,
  compute, collaboration, and production safety layer.
  -----------------------------------------------------------------------

  -----------------------------------------------------------------------

# 19. 商业模式与定价假设

早期不要急于精准定价，先验证"客户愿不愿意让系统接入生产
trace、愿不愿意为一次 incident 的自动诊断节省工程时间付费"。定价可以围绕
replay compute、production trace volume、team/enterprise governance
三条轴。

  -----------------------------------------------------------------------------------
  **层级**                **可能形态**            **目的**
  ----------------------- ----------------------- -----------------------------------
  OSS                     免费本地 CLI/runtime    GitHub adoption、benchmark、社区
                                                  adapter

  Developer Cloud         \$20--50/月 + compute   个人/小团队保存 runs、并行 replay

  Team                    \$200--800/月           production ingestion、failure
                                                  clusters、CI verification

  Enterprise              年合同                  VPC、SSO/RBAC、retention、private
                                                  judge、SLA、support
  -----------------------------------------------------------------------------------

真正有潜力的企业价值不是"多一个 dashboard"，而是减少高价值 Agent
incident 的 MTTR、避免错误归因导致的无效模型升级，以及把手工
debug/verify 过程自动化。

# 20. 技术护城河与数据飞轮

## 20.1 不可能成为护城河的东西

- trace UI

- 基础 LLM judge

- 普通 prompt comparison

- 单纯 fault injection

- 通用 dashboard

## 20.2 可能形成护城河的东西

> 1\. 真实 failure → intervention → outcome 的结构化数据集。
>
> 2\. 跨 stack failure taxonomy 与可验证 causal pattern。
>
> 3\. Experiment Planner：用较少 runs 获得足够 evidence。
>
> 4\. Safe Replay：对有副作用 Agent 的高保真隔离执行能力。
>
> 5\. Repair success dataset：什么 root cause 应该优先用什么最小 patch。
>
> 6\. 历史 incident intelligence：新事故与过去 failure cluster
> 的迁移学习/匹配。

## 20.3 数据飞轮

+-----------------------------------------------------------------------+
| Production failure                                                    |
|                                                                       |
| ↓                                                                     |
|                                                                       |
| Diagnose experiments                                                  |
|                                                                       |
| ↓                                                                     |
|                                                                       |
| Validated causal labels                                               |
|                                                                       |
| ↓                                                                     |
|                                                                       |
| Verified repair                                                       |
|                                                                       |
| ↓                                                                     |
|                                                                       |
| Regression asset                                                      |
|                                                                       |
| ↓                                                                     |
|                                                                       |
| Better hypothesis priors / planner                                    |
|                                                                       |
| ↓                                                                     |
|                                                                       |
| Fewer experiments for next incident                                   |
+=======================================================================+

# 21. 研究路线与可发表问题

这个产品天然具有研究问题，尤其适合把"serving-stack confounds"延伸到
agent failure attribution。研究成果可以反过来增强产品 credibility。

  -----------------------------------------------------------------------
  **研究问题**                        **可能实验**
  ----------------------------------- -----------------------------------
  Model vs Serving 归因               同一任务固定模型/上下文，只注入
                                      latency、retry、cache、provider
                                      fault，观察误归因率

  最小实验预算                        比较 brute-force、rule
                                      planner、Bayesian information gain
                                      的 runs/cost/accuracy

  Replay fidelity 对 causal accuracy  系统改变
  的影响                              action-match/state-match，测
                                      attribution bias

  交互根因                            latency × retry、retrieval ×
                                      context truncation 等二阶
                                      interaction

  LLM-judge RCA vs intervention RCA   在 planted-ground-truth benchmark
                                      上比较 Top-1/Top-k accuracy

  Repair validity                     建议式 repair 与 verified repair
                                      的真实 fix/regression rate 差异
  -----------------------------------------------------------------------

## 21.1 自建 benchmark

最重要的是建立"planted root cause benchmark"：故意植入已知故障（例如
stale state、bad schema、timeout+retry、wrong retrieval、ambiguous
prompt），然后看系统能否恢复真实根因。这比只在真实 trace
上让人主观判断"解释像不像"更可信。

# 22. 风险、失败模式与缓解方案

  ----------------------------------------------------------------------------------------
  **风险**                **表现**                **缓解**
  ----------------------- ----------------------- ----------------------------------------
  Replay 不忠实           重放路径与原 run 差太远 action/state fidelity
                                                  指标；cassette；局部 replay；降低结论
                                                  confidence

  实验成本太高            一次 incident 数百美元  budget-aware planner；缓存；local
                                                  model；早停

  副作用事故              replay 再次退款/发信    side-effect
                                                  typing；deny-by-default；sandbox/mock

  因果过度宣称            把 stochastic           CI、competing hypothesis、植入 ground
                          correlation 当因果      truth benchmark

  竞争者快速跟进          Galileo/Taso            聚焦 safe replay + experiment planner +
                          加入类似功能            serving-stack evidence

  修复过拟合              只修一个 case           variants + unrelated regression +
                                                  cluster validation

  客户不愿上传数据        PII/商业敏感            local OSS
                                                  runtime；VPC；redaction；metadata-only
                                                  mode
  ----------------------------------------------------------------------------------------

# 23. Demo 设计

## Demo A：Model Wasn't the Problem

目标：展示本项目最重要的差异------模型看起来失败，但真正根因来自
serving/retry。

+-----------------------------------------------------------------------+
| Baseline                                                              |
|                                                                       |
| Model A success = 71%                                                 |
|                                                                       |
| Model B success = 84%                                                 |
|                                                                       |
| Naive conclusion: Model B is better.                                  |
|                                                                       |
| AgentDoctor interventions:                                            |
|                                                                       |
| 1\) swap model only → 75%                                             |
|                                                                       |
| 2\) normalize tool latency → 89%                                      |
|                                                                       |
| 3\) clear stale retry state → 92%                                     |
|                                                                       |
| Diagnosis:                                                            |
|                                                                       |
| latency → retry → duplicated observation → planner loop               |
|                                                                       |
| Recommendation:                                                       |
|                                                                       |
| fix retry-state merge; do not upgrade model                           |
+=======================================================================+

## Demo B：Verified Prompt/Tool Repair

目标：从一次错误退款事故开始，定位具体 policy/tool
描述缺陷，自动生成最小 diff，再通过 100+ variants 与 unrelated
regression 验证。

+-----------------------------------------------------------------------+
| Incident: refund_order called before get_order verification           |
|                                                                       |
| Causal test:                                                          |
|                                                                       |
| \- model resample small improvement                                   |
|                                                                       |
| \- retrieval replacement no improvement                               |
|                                                                       |
| \- tool description patch large improvement                           |
|                                                                       |
| Patch:                                                                |
|                                                                       |
| \- \"Refund an order when requested.\"                                |
|                                                                       |
| \+ \"Refund only after get_order verifies eligibility and order_id.\" |
|                                                                       |
| Verification:                                                         |
|                                                                       |
| Original case: PASS                                                   |
|                                                                       |
| 100 variants: 96 → 100 PASS                                           |
|                                                                       |
| 500 unrelated: no significant regression                              |
+=======================================================================+

# 24. Repository / API 草案

+-----------------------------------------------------------------------+
| agent-doctor/                                                         |
|                                                                       |
| ├─ src/agentdoctor/                                                   |
|                                                                       |
| │ ├─ trace/                                                           |
|                                                                       |
| │ │ ├─ schema.py                                                      |
|                                                                       |
| │ │ ├─ recorder.py                                                    |
|                                                                       |
| │ │ └─ adapters/                                                      |
|                                                                       |
| │ ├─ replay/                                                          |
|                                                                       |
| │ │ ├─ runtime.py                                                     |
|                                                                       |
| │ │ ├─ cassette.py                                                    |
|                                                                       |
| │ │ └─ sandbox.py                                                     |
|                                                                       |
| │ ├─ interventions/                                                   |
|                                                                       |
| │ │ ├─ model.py                                                       |
|                                                                       |
| │ │ ├─ prompt.py                                                      |
|                                                                       |
| │ │ ├─ tool.py                                                        |
|                                                                       |
| │ │ ├─ retrieval.py                                                   |
|                                                                       |
| │ │ └─ serving.py                                                     |
|                                                                       |
| │ ├─ attribution/                                                     |
|                                                                       |
| │ │ ├─ contrastive.py                                                 |
|                                                                       |
| │ │ ├─ monte_carlo.py                                                 |
|                                                                       |
| │ │ └─ confidence.py                                                  |
|                                                                       |
| │ ├─ planner/                                                         |
|                                                                       |
| │ ├─ repair/                                                          |
|                                                                       |
| │ ├─ regression/                                                      |
|                                                                       |
| │ └─ cli.py                                                           |
|                                                                       |
| ├─ benchmarks/                                                        |
|                                                                       |
| ├─ examples/                                                          |
|                                                                       |
| ├─ tests/                                                             |
|                                                                       |
| └─ docs/                                                              |
+=======================================================================+

## 24.1 CLI 草案

+-----------------------------------------------------------------------+
| agentdoctor record \-- python app.py                                  |
|                                                                       |
| agentdoctor inspect trace.json                                        |
|                                                                       |
| agentdoctor replay trace.json \--n 10                                 |
|                                                                       |
| agentdoctor intervene trace.json \--tool-timeout search_orders=2s     |
|                                                                       |
| agentdoctor diagnose trace.json \--budget 40                          |
|                                                                       |
| agentdoctor repair trace.json \--target prompt                        |
|                                                                       |
| agentdoctor verify patch.diff \--suite regression/refund              |
+=======================================================================+

## 24.2 Python API 草案

+-----------------------------------------------------------------------+
| from agentdoctor import record, diagnose, verify                      |
|                                                                       |
| with record(name=\"refund-incident\") as run:                         |
|                                                                       |
| agent.run(user_request)                                               |
|                                                                       |
| report = diagnose(                                                    |
|                                                                       |
| run.trace,                                                            |
|                                                                       |
| hypotheses=\[\"model\", \"prompt\", \"tool\", \"serving\"\],          |
|                                                                       |
| budget=40,                                                            |
|                                                                       |
| )                                                                     |
|                                                                       |
| patch = report.best_repair()                                          |
|                                                                       |
| verification = verify(patch, suites=\[\"incident\", \"variants\",     |
| \"unrelated\"\])                                                      |
+=======================================================================+

# 25. 成功标准与下一步

## 25.1 技术成功标准

  -----------------------------------------------------------------------
  **阶段**                            **最低验收标准**
  ----------------------------------- -----------------------------------
  Replay                              在 synthetic/small agent benchmark
                                      上，无干预关键 action match ≥ 80%
                                      或明确报告不可重现

  Attribution                         对 planted root-cause benchmark 的
                                      Top-1 ≥ 70%，Top-3 ≥ 90%

  Cost                                典型 incident 默认诊断预算 ≤ 60 次
                                      agent runs

  Safety                              destructive tool live side-effect =
                                      0

  Repair                              目标 failure cluster 明显改善且
                                      unrelated regression 无统计显著下降

  Developer UX                        从 trace 到第一份 diagnosis report
                                      ≤ 3 条 CLI 命令
  -----------------------------------------------------------------------

## 25.2 产品验证问题

> 1\. 开发者是否愿意把真实失败 trace 交给系统重放？
>
> 2\. 他们当前一次高价值 Agent incident 的人工 debug 时间是多少？
>
> 3\. "因果证据"是否比"AI root-cause explanation"明显提升信任？
>
> 4\. 哪一类 incident 最愿意付费：客服、支付、RAG、coding、ops？
>
> 5\. 他们更愿意为 production ingestion、managed sandbox 还是 diagnosis
> compute 付费？

## 25.3 现在最应该做的第一件事

  ---------------------------------------------------------------------------------
  **建议\**
  先实现 Demo A 的完整最小闭环：构造一个"serving latency → retry/state → agent
  failure"的可重复场景；让系统自动记录、replay、干预、归因，并输出"不要换模型，修
  retry/state"的证据报告。它既能验证技术，也能成为项目最有辨识度的 README 演示。
  ---------------------------------------------------------------------------------

  ---------------------------------------------------------------------------------

# 附录 A：竞争对手功能矩阵（公开能力快照）

  -----------------------------------------------------------------------------------------------------------------------------------
  **能力**          **Galileo**        **Braintrust**     **Langfuse**       **Taso**       **AgentChaos**   **CAR**        **Agent
                                                                                                                            Doctor
                                                                                                                            目标**
  ----------------- ------------------ ------------------ ------------------ -------------- ---------------- -------------- ---------
  Tracing           ✓                  ✓                  ✓                  集成/环境      ---              记录轨迹       集成

  Dataset/Eval      ✓                  ✓                  ✓                  ✓              研究 benchmark   有限           基础

  CI Regression     部分/平台化        ✓                  ✓                  ✓              ---              ---            ✓

  Fault Injection   有限/可靠性        指南/模拟          自定义             非核心         ✓                intervention   ✓

  Production-like   非核心公开卖点     sandbox 方法       实验 runner        ✓              ---              ✓              ✓ Safe
  Replay                                                                                                                    Replay

  Root-cause        ✓                  人工/agent 辅助    trace/eval         行为差异证据   诊断研究         ✓ causal       ✓ causal
  Explanation                                                                                                               

  Counterfactual    未见核心公开能力   未见核心公开能力   未见核心公开能力   change         非核心           ✓              ✓
  Causality                                                                  comparison                                     

  Serving-stack     有限               可自定义           可观测指标         cost/latency   LLM API faults   step-level     重点
  Attribution                                                                compare                                        

  Auto Experiment   未见成熟公开能力   未见               未见               未见           ---              budget         重点
  Planner                                                                                                    estimators     

  Verified Repair   建议/优化          coding-agent 可修  实验比较           推荐 change    ---              ---            重点
                                                                             follow-up                                      
  -----------------------------------------------------------------------------------------------------------------------------------

注：矩阵只根据公开网站/文档进行产品定位判断，不代表这些公司内部或私有版本绝对没有相关能力。竞争功能变化很快，应在真正立项/融资前再次核对。

# 附录 B：示例诊断报告

+-----------------------------------------------------------------------+
| AGENT DOCTOR INCIDENT REPORT                                          |
|                                                                       |
| Incident: refund-2026-08-23-827                                       |
|                                                                       |
| Outcome: unauthorized refund                                          |
|                                                                       |
| REPRODUCIBILITY                                                       |
|                                                                       |
| Action match rate: 0.86                                               |
|                                                                       |
| State match rate: 0.92                                                |
|                                                                       |
| Residual nondeterminism: moderate                                     |
|                                                                       |
| HYPOTHESES (posterior)                                                |
|                                                                       |
| H1 retry/state 0.51                                                   |
|                                                                       |
| H2 prompt 0.24                                                        |
|                                                                       |
| H3 model 0.15                                                         |
|                                                                       |
| H4 tool schema 0.07                                                   |
|                                                                       |
| H5 retrieval 0.03                                                     |
|                                                                       |
| EXPERIMENT EVIDENCE                                                   |
|                                                                       |
| Normalize latency failure 0.44 → 0.21                                 |
|                                                                       |
| Clear stale retry observation failure 0.44 → 0.06                     |
|                                                                       |
| Swap model failure 0.44 → 0.39                                        |
|                                                                       |
| Gold retrieval failure 0.44 → 0.42                                    |
|                                                                       |
| Prompt ablation failure 0.44 → 0.35                                   |
|                                                                       |
| ROOT CAUSE                                                            |
|                                                                       |
| Retry state contamination after timeout                               |
|                                                                       |
| Estimated effect: 0.38                                                |
|                                                                       |
| 95% CI: \[0.27, 0.48\]                                                |
|                                                                       |
| REPAIR                                                                |
|                                                                       |
| Clear previous failed observation before retry merge.                 |
|                                                                       |
| VERIFY                                                                |
|                                                                       |
| 27 production incidents: 27/27 pass                                   |
|                                                                       |
| 200 variants: 196/200 pass                                            |
|                                                                       |
| Unrelated suite: 94.3% → 94.2%                                        |
|                                                                       |
| Cost/run: +0.8%                                                       |
|                                                                       |
| p95 latency: -3.1%                                                    |
|                                                                       |
| DECISION: PATCH VERIFIED; READY FOR HUMAN REVIEW                      |
+=======================================================================+

# 附录 C：公开参考资料

以下来源用于竞争格局和研究方向核对。产品功能更新很快，本文按 2026-08-23
的公开资料编写。

**\[1\] Galileo Agent Reliability Platform ---**
[[https://galileo.ai/blog/galileo-agent-reliability-platform]{.underline}](https://galileo.ai/blog/galileo-agent-reliability-platform)\
Agent Reliability、failure mode analysis、root-cause
recommendations、tool/agent metrics。

**\[2\] Galileo Evaluate Docs ---**
[[https://promptquality.docs.galileo.ai/]{.underline}](https://promptquality.docs.galileo.ai/)\
Tool Selection Quality、Tool Errors、Action Advancement、Action
Completion 等指标。

**\[3\] Braintrust --- Agent Evaluation ---**
[[https://www.braintrust.dev/articles/agent-evaluation]{.underline}](https://www.braintrust.dev/articles/agent-evaluation)\
Agent step/outcome eval、sandbox simulation、fault injection 方法。

**\[4\] Braintrust --- Agent Evaluation Platform ---**
[[https://www.braintrust.dev/learn/ai-agent-evaluation/v0]{.underline}](https://www.braintrust.dev/learn/ai-agent-evaluation/v0)\
step span、experiment diff、production trace→dataset、replay test
cases。

**\[5\] Langfuse --- Evaluation Overview ---**
[[https://langfuse.com/docs/evaluation/overview]{.underline}](https://langfuse.com/docs/evaluation/overview)\
online/offline eval、datasets、experiments、CI/CD regression。

**\[6\] Langfuse --- Datasets ---**
[[https://langfuse.com/docs/evaluation/experiments/datasets]{.underline}](https://langfuse.com/docs/evaluation/experiments/datasets)\
production traces 转 dataset 与 versioned datasets。

**\[7\] Taso Labs ---**
[[https://tasolabs.com/]{.underline}](https://tasolabs.com/)\
production traces→runnable environments；production-like
sandbox；baseline/challenger change verification。

**\[8\] AgentChaos (arXiv:2608.06790) ---**
[[https://arxiv.org/abs/2608.06790]{.underline}](https://arxiv.org/abs/2608.06790)\
runtime non-intrusive LLM API fault injection；crash/omission/value
faults；65 configurations；诊断仍有明显空间。

**\[9\] Causal Agent Replay (arXiv:2606.08275) ---**
[[https://arxiv.org/abs/2606.08275]{.underline}](https://arxiv.org/abs/2606.08275)\
通过 do-intervention 与 counterfactual run-forward 做 step-level causal
attribution。

**\[10\] Causal Agent Replay GitHub ---**
[[https://github.com/jaineet17/causal-agent-replay]{.underline}](https://github.com/jaineet17/causal-agent-replay)\
开源实现、replay fidelity、Monte Carlo confidence intervals 等工程细节。
