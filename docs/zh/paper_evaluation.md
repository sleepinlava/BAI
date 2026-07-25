# 论文评测协议

## 两条证据轨道

ABI 论文将 Agent 可操作性与生物学有效性作为两条独立证据轨道。ABI-Bench 测量 Agent 是否能
发现、规划、诊断、授权、执行并检查生物信息工作流；真实数据案例测量已完成流程能否恢复预注册
生物学端点。dry-run 分数不能支持生物学有效性主张，成功的真实案例也不能单独证明 ABI 相对
baseline 改善了 Agent。

## 以隐私需求为动机的本地模型 benchmark

主 benchmark 面向**本地可部署、自托管的语言模型**。这对应实验室和临床环境中的现实约束：
原始基因组数据、样本标识、文件路径和中间结果不能默认发送到托管 API。论文主张因此只适用于
实际测量的模型 checkpoint、服务配置、量化和硬件，不外推到所有本地模型或 frontier model。

所有既有 ABI-Bench 结果全部从本轮分析中排除。新实验必须从干净 benchmark commit 和冻结的
study manifest 开始。

### 确认性模型设计

- 在观察结果前选择至少三个相互独立的模型家族。
- 每个家族评测一个 small 和一个 medium 配置，使用匹配的精度或同一种量化方法；不能从
  native 与 4-bit 的不匹配组合推断参数规模效应。
- 在 runtime attestation 中记录 checkpoint revision/hash、tokenizer、context length、
  temperature、最大输出 token、推理引擎及版本、量化、GPU/VRAM、并发、timeout 与 retry policy。
- 同一模型配置的 G1/G2/G3/G4 使用相同 system prompt、任务 prompt、工具实现、fixture 和服务策略。
- 随机化或区组化组顺序并固定并发，避免温度、显存和排队漂移变成处理效应。
- 重复运行用于估计配置内变异。跨模型外推的统计单位是模型家族，而不是运行次数或任务数。

### 分组与估计量

| 组 | 操作表面 | 用途 |
| --- | --- | --- |
| G1 | README + shell | 文档与 shell baseline |
| G2 | 通用工具调用 | 检验无约束工具是否已经足够 |
| G3 | ABI 生命周期 | 完整契约驱动控制层 |
| G4 | 信息量匹配的静态文档 | 区分可调用生命周期控制与单纯信息量 |

主要估计量是 `causal_core_v0_8` 上配对的 `G3−G1`、`G3−G2` 和 `G3−G4`。
`hidden_robustness_v0_9` 上的隐藏诊断鲁棒性单独报告。ABI 原生机制探针和真实执行任务是描述性
证据，不得混入主要因果总分。

### 隐私与隔离控制

- 模型服务器与 benchmark harness 运行在受控本地网络内。
- 计分任务期间关闭外网访问。
- 只挂载任务 fixture 与必要文档，不暴露无关研究数据。
- prompt 和模型轨迹不得保留到批准的 benchmark artifact root 之外。
- 只公开合成/公开 fixture 与汇总分数，不公开受保护样本内容。

### Preflight 门禁

只有同时满足以下条件才可填充正式指标：

1. benchmark 仓库干净且 commit 已冻结；
2. task、fixture、scorer、group profile、model registry 和 runtime attestation 哈希已冻结；
3. 所有必需的 model × group × task × replicate 单元齐全；
4. G1/G2/G4 trace 不含 ABI 生命周期泄漏；
5. public causal suite 与 hidden robustness suite 分别通过匹配的 preflight；
6. 排除与重试规则在观察结果前已固定。

在此之前，`metrics.tsv` 中 Agent 可操作性行保持 `pending_new_run` 且 estimate 为空。

## 生物学验证

Airway 与 ST93 MRSA 是配对 running example，SCAPP 是旗舰 case study。它们的机器可读端点、
方法和限制位于 `docs/paper_examples/`；这些真实数值独立于已抛弃的 ABI-Bench 结果。

## 规范指标表

`metrics.tsv` 采用 long-form、主张级 schema。每行记录 evidence track、claim role、status、
workflow/model、dataset/suite、metric、estimate、适用时的区间和分子/分母、unit、source 与
limitation。只有状态为 `pending_new_run`、`pending_independent_truth` 或 `not_assessed` 时，空值才有
明确语义。
