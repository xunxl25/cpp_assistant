# GESP 真题 PDF → JSON 批量入库流水线

> 版本：2026-11-08 | 实战验证：gesp-5 全部 12 期（202309~202609）+ gesp-5-sample，共 300 题，答案与官方表 100% 匹配
> 适用：未来 gesp-6/7/8 及更高级别入库、任何一次新考试后补录

## 一、设计原则（为什么这么设计）

1. **VLM 只当"眼睛"，不当"脑子"**：视觉模型只做转录（OCR），不做题。解题、格式化、校验全部拆到独立环节。链条越长，单点错误叠加越失控（用户早期 GLMchat prompt"按位置抄答案"版本差异大，就是反面教训）
2. **官方答案表是最高优先级 ground truth**：GESP 真题每份卷首/判断题章节前都有官方答案表，直接提取比任何模型推理都硬。模型解题仅作交叉验证
3. **一切校验程序化，禁止手敲答案串**：本流水线两次因手打答案串出错，全部由程序化提取纠正。任何答案对照必须来自代码提取，不允许人工转录
4. **schema 以库内既有文件为基准**：新 json 必须与库内已验证文件字段完全一致（字段名、顺序、值域、知识点集合）

## 二、流水线总览

```
PDF
 ├─[fitz 200dpi 导页图]→ 页面图片 ×N
 │    └─[VLM 转录prompt]→ transcript（每页一个 json）
 ├─[fitz 文字层]→ 第1页选择题答案表（正则提取 15 个 A-D）
 │    └─ 判断题 √/× 是特殊字体，文字层提不出 → [VLM 读表prompt] 读 10 个符号
 ├─[逐题推理]（agent 自己解题）+ [可执行题 g++ 编译运行验证]
 └─[组装脚本]（Python，逐题硬编码）→ question_bank json
      └─[校验]：答案 vs 官方表 / schema vs 库内基准 / id 唯一 / 知识点集合
           └─[build_question_bank_index()] 重建索引 → 用户 commit
```

## 三、逐步操作手册

### 步骤 0：准备与摸底

```python
import fitz
doc = fitz.open('pdf_from_CCF/gespN/gesp-N-YYYYMM.pdf')
for i, page in enumerate(doc):
    t = page.get_text()
    # 找三个锚点："单选题"（第1页）、"判断题"（答案表所在页）、"编程题"（截断点）
```

- 记录：总页数、编程题起始页（= 转录截断页）、判断题答案表所在页
- **GESP 卷面固定结构**：15 单选（30分）+ 10 判断（20分）+ 编程题。只处理前 25 题

### 步骤 1：导出页面图（200dpi 够用）

```python
for i in range(目标页数):  # 到编程题起始页为止，编程题起始页若含判断题尾也要
    doc[i].get_pixmap(dpi=200).save(f'page_{i+1:02d}.png')
```

### 步骤 2：VLM 逐页转录

调用方式（沙箱内 z-ai CLI）：
```bash
z-ai vision -p "<转录prompt>" -i page_XX.png -o vlm_YYYYMM_pXX.json
```

**转录 prompt 模板**（保持简短，禁止解题）：
> 这是 GESP N级 YYYYMM 真题的连续页面（第 X 页）。完整转录页面上所有内容：答案表格（如有，逐格列出）、章节标题、所有题目的题号、题干、代码（完整保留缩进）、选项。数学公式用文本表达。只转录，不解题，不跳过任何题目。

**答案表读表 prompt**（判断题专用）：
> 这张图片顶部有一个判断题答案表格，共10列，每列一个符号（对勾或叉）。从左到右逐个报告：格式如 1=√ 2=× ...。只报告符号。

**工程注意**：
- 每页约 1.5~2 分钟，批量用脚本循环 + 重试（见 `batch_transcribe.sh` 模式）
- **会撞 429 限流**：失败页等 2 分钟再试；不要并行双脚本重试同一页（加剧限流）
- 跨页题目（代码/选项跨页）转录会截断，需要补一次针对性转录（"只转录第 X 题的 B 选项"），VLM 能指出内容在下一页
- 第 1 页 prompt 里强调"答案表格逐格列出"

### 步骤 3：程序化提取官方答案

```python
# 选择题：PDF 第 1 页文字层
import re
t1 = doc[0].get_text()
letters = re.findall(r'[A-D]', t1.split('答案')[1][:60])  # 取前 15 个

# 判断题：VLM 读表后程序化转换（禁止手敲！）
syms = re.findall(r'[√×✓✗]', vlm_content)
tf = ''.join('T' if s in '√✓' else 'F' for s in syms[:10])
```

存入 `official_answers.py`：`{"YYYYMM": {"sc": "CCDAB...", "tf": "TFFTT..."}}`

### 步骤 4：逐题推理 + 编译验证

- agent 自己逐题解题（这一步就是"模型做题"，但错误会被步骤 5 暴露）
- **可执行题（"运行以下代码输出什么"类）：真实 g++ 编译运行核对**——比推理硬得多
- 已知坑：
  - 二分查找计数题：最后一次循环条件失败**不进入循环体**，times 不自增（202403 SC8 栽过）
  - 快排 pivot 影响的官方口径是**时间复杂度**（B），不选"时间+空间"（202403 SC13 栽过）
  - "假快速幂"（调用自身两次）实际是 O(n) 不是 O(log n)

### 步骤 5：组装脚本（每份一个 build_YYYYMM.py）

结构：`sc(i, kp, question, options, answer, explanation)` / `tf(...)` helper + 逐题 append + 末尾自动核对：

```python
off = OFFICIAL["YYYYMM"]
mine_sc = "".join(q["answer"] for q in Q[:15])
mine_tf = "".join(q["answer"] for q in Q[15:])
# MATCH 则写入 question_bank/，MISMATCH 则列出题号回去修正推理
```

**schema 规范（与库内一致的硬要求）**：
- 字段及顺序：`id, exam, knowledge_points, type, question, options, answer, explanation`
- `id`：`gesp-{level}-{yyyymm}-sc-{n}` / `gesp-{level}-{yyyymm}-tf-{n}`
- `exam`：`{"type": "GESP", "level": N, "date": "yyyymm"}`（**6 位 yyyymm，唯一标准**）
- `type`：`single_choice` / `true_false`（小写）
- 判断题 **必须带** `options: {"T": "正确", "F": "错误"}`（库内惯例）
- `answer`：选择题 `A/B/C/D`；判断题 **`T`/`F`**（库内主流 171:29，虽兼容 true/false 但新数据一律用 T/F）
- `knowledge_points`：必须落在库内已有集合（从既有 gesp-5 文件收集），确实不匹配则留空 `[]`
- 代码嵌入 question 字段用 `\n` 换行，保持缩进

### 步骤 6：全量校验（组装后必跑）

```python
# 1. 字段结构与库内基准 diff
# 2. exam 结构、题数 15+10、answer 值域
# 3. 全库 id 唯一性
# 4. 知识点 ∈ 库内集合
# 5. 索引重建验证：
build_question_bank_index()
# sqlite: data/question_bank_index.db, 表 question_index, 列 question_id/exam_level/source_file...
```

### 步骤 7：交付

- json 文件发送给用户 → 用户放入 `question_bank/` → 本地重建索引 → commit + push（用户掌控 commit）
- 沙箱同步：处理用户 push 前先 `git pull`；若有 untracked 冲突（上次交付残留），先清理再 pull

## 四、成本参考

- VLM 调用：每份约 10~13 次（转录 6~13 页 + 读表 1 + 跨页补录），7 份共约 76 次
- 时间：每页转录 1.5~2 分钟，一份 15~30 分钟，批量需小时级（含限流重试）

## 五、历史决策记录

- 2026-11-08：gesp-5 十二期全部入库（350 题），流水线定型。之前的手动/GLMchat 方案归档为"单份应急"用途
- 图片代码题（卷面代码为图片）：视觉转录可完全还原为文本代码，"（参照原PDF代码）"兜底在视觉方案下未再使用
- `true/false` vs `T/F` 历史不一致：代码已兼容（加载时归一化），不做数据迁移（用户决策 2026-11-08）
