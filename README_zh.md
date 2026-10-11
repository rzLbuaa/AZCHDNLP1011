# ACHDNLP 算法参考实现

本库用于展示论文的建库、检索、证据片段封装、生成、验证及消融逻辑。**它是根据论文方法编写的参考实现，不是原始临床部署代码，也不承诺复现论文中的临床数值。** 原始病例库、完整诊断本体、原始提示词及服务执行记录不随库发布。

## 执行

在仓库根目录安装并运行：

```bash
python -m pip install -e ".[dev]"
python -m achdnlp demo --all-arms
pytest
```

离线示例无需API或网络。`DemoBackend`由确定性规则驱动，仅检查流程，不代表真实LLM性能。示例包含23条人工构造的历史记录、8条构造查询和独立的测试标签；不是临床记录的改写或抽样。

分步运行：

```bash
python build_db.py --output runs/resource
python retrieve_generate.py --resource runs/resource --arms A,B,C,D --output runs/matched
python run_ablations.py --resource runs/resource --output runs/all
```

单个消融的入口在`experiments/`。例如：

```bash
python experiments/02_no_history.py --resource runs/resource
python experiments/03_findings_only.py --resource runs/resource
python experiments/04_preverification.py --resource runs/resource
python experiments/10_lexical_verification.py --resource runs/resource
```

`D`从同一次A生成结果取得验证前快照，不重新生成。A与C使用同一次冻结的检索结果和顺序，C仅去掉显式专家标签及标签先验。B仅移除历史输入，保留其他处理。因此B不等同于`LLM_ONLY`。

## 真实服务

`configs/backend_http.yaml`使用环境变量，不保存密钥。PowerShell示例：

```powershell
$env:ACHDNLP_BASE_URL = "https://your-authorized-service.example/v1"
$env:ACHDNLP_MODEL = "your-model-identifier"
$env:ACHDNLP_API_KEY = "your-local-credential"
python retrieve_generate.py --resource runs/resource --backend configs/backend_http.yaml --allow-remote --arms A,B,C,D --output runs/remote
```

示例URL和模型名必须由实际获批服务替换。八个`configs/backends/backend_*.yaml`只保留论文中的归档别名作为配置标签，并分别读取实际模型、地址和密钥；不据此认定这些字符串是供应商公开版本。

使用自己的数据时，建立独立配置，将`data_kind`改为`local_research`，提供本地审定的本体和规则，再单独建库。`--allow-remote`是明确的联网授权；默认不会发送病例。简单标识符检测不是完整去标识化工具。

## 输入边界

建库：`record_id`、`findings`、`expert_labels`，可选`modality`、`source`。历史专家标签必须已规范化或能唯一匹配本体名称。字符TF-IDF仅对`findings`拟合，标签在检索后加入。

推理：`record_id`、`findings`、可选`modality`和`cohort`。`cohort`只用于结果分组。参考诊断单独放在评估文件中，推理对象拒绝额外标签字段。

```bash
python -m achdnlp convert --input historical.csv --output historical.jsonl --id-column case_id --findings-column "影像学表现" --labels-column expert_labels
```

CSV的`expert_labels`列用`|`分隔多个规范标识符。程序不会从未审核的自由文本诊断中自动编造标准标签。病例表中的其他列不会自动传给模型。不使用错误年龄记录，不做OCR，也不处理影像。

## 结果与断点

每次运行输出：`manifest.json`、`records/*.json`、`predictions.jsonl`、`completion.json`及使用的系统提示词。快照包含规范化候选、原始顺序、证据、状态及生成摘要哈希。对象的原始出现、规范化候选和最终显示数量分开记录。

已有运行目录只能在数据、配置、代码和依赖版本一致时继续，避免把不同实验混在一个断点文件中。技术失败被保留，不改写成诊断阴性或正常完成。`D`在A验证失败但生成成功时仍可取得原始生成结果。

```bash
python -m achdnlp evaluate --predictions runs/matched/predictions.jsonl --references data/demo/references.jsonl --output runs/matched/metrics.json
```

首项命中和任一命中分别计算；首项无法规范化时不会删除首项来提升后面的正确诊断。完整报告合格率只使用外部独立评分，不由诊断命中或验证器状态推定。

## 论文对应与披露

`docs/parameter_provenance.md`区分论文明确给出的约束和本库的例示参数。0.70/0.25/0.05权重、MMR参数、自适应触发阈值、小型规则库和提示词文字均不是论文原始配置的恢复。

论文只列举了部分原18种配置，本库不补造缺失配置。实现覆盖已描述的A--D、固定检索数量、rules-only、LLM-only、text-RAG、lexical verification、self-review和count-matched gating；`ID_ONLY`作为机制补充，`CF_LABELS`明确列为未来方向的离线反事实扩展。R0是A别名，不额外调用模型。

代码注释只保留必要说明，设计依据集中放在`docs/`。`docs/release_scope.md`提供与实际交付范围一致的代码可用性声明。`docs/publication_checklist.md`列出许可证确认、仓库版本归档、数据访问和工具使用披露要求。仓库代码格式不替代期刊所要求的真实制作过程披露。
