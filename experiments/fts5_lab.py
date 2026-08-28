#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FTS5 中文检索最小实验
用三条知识 + 一个真实失败问法，把「店保」为什么捞不到，一步步跑出来看。

跑法：
    python3 fts5_lab.py          # 跑完整实验
    python3 fts5_lab.py -i       # 跑完之后进交互模式，自己输问题试
"""
import sqlite3
import sys

# ============================================================
# 知识库（对应 D1/D2/D3）
# ============================================================
DOCS = [
    (1, "两年保修是店铺保修还是官方保修",
        "本店销售的机器提供两年保修，由店铺承担，非厂商官方保修。"),
    (2, "电池健康度低于80%可以更换",
        "电池健康度低于 80% 的，在保修期内可免费更换一次。"),
    (3, "退货地址在深圳龙华",
        "退货请寄往深圳市龙华区，具体地址联系客服获取。"),
]

QUERY = "你们的两年保修是店保吗"


def line(title=""):
    print("\n" + "=" * 66)
    if title:
        print(title)
        print("=" * 66)


# ============================================================
# 极简中文分词器
# 真实项目里用 jieba。这里手写一个小词典版，让你看清「分词」这一步
# 到底在干什么 —— 它决定了词级 FTS 能不能命中。
# ============================================================
VOCAB = ["两年", "保修", "店铺", "官方", "电池", "健康度", "更换",
         "退货", "地址", "深圳", "龙华", "机器", "厂商", "客服",
         "你们", "店保"]          # ← 注意：「店保」在词典里，但知识库里没这个词


def tokenize(text, vocab=VOCAB):
    """最大正向匹配：从左往右，每次尽量匹配最长的词。"""
    out, i = [], 0
    while i < len(text):
        for size in range(4, 0, -1):          # 先试 4 字，再 3、2、1
            piece = text[i:i + size]
            if piece in vocab:
                out.append(piece)
                i += size
                break
        else:                                  # 一个词都没匹配上
            i += 1                             # 跳过这个字（的、是、吗…）
    return out


def trigrams(text):
    """所有连续三字符片段。"""
    return [text[i:i + 3] for i in range(len(text) - 2)]


# ============================================================
# 建库
# ============================================================
db = sqlite3.connect(":memory:")

# 路 A：词级 —— 存的是分好词、用空格隔开的文本
db.execute("CREATE VIRTUAL TABLE fts_word USING fts5(seg, tokenize='unicode61')")
# 路 B：trigram —— 存原文，SQLite 自己切三字片段
db.execute("CREATE VIRTUAL TABLE fts_tri  USING fts5(raw, tokenize='trigram')")

for doc_id, title, body in DOCS:
    full = title + " " + body
    db.execute("INSERT INTO fts_word(rowid, seg) VALUES (?,?)",
               (doc_id, " ".join(tokenize(full))))
    db.execute("INSERT INTO fts_tri(rowid, raw) VALUES (?,?)", (doc_id, full))
db.commit()


# ============================================================
# 实验一：分词这一步到底做了什么
# ============================================================
line("实验一 · 分词：一句话被切成了什么")

print(f"\n顾客问题：{QUERY}")
q_words = tokenize(QUERY)
print(f"切出来的词：{q_words}")

print(f"\nD1 原文：{DOCS[0][1]}")
d1_words = tokenize(DOCS[0][1] + " " + DOCS[0][2])
print(f"切出来的词：{d1_words}")

hit = [w for w in q_words if w in d1_words]
miss = [w for w in q_words if w not in d1_words]
print(f"\n  对上的词：{hit}")
print(f"  对不上的：{miss}   ← 「店保」在这儿断了")
print("\n  原因：知识库里写的是「店铺」，顾客说的是「店保」。")
print("  两个不同的词，倒排表里查不到，词级这一路对此无能为力。")


# ============================================================
# 实验二：词级 FTS 检索 + BM25
# ============================================================
line("实验二 · 词级 FTS（路 A）")

# FTS5 里 bm25() 返回的是负数，越小越相关；取负号变成越大越相关
q_expr = " OR ".join(q_words)
print(f"\n查询表达式：{q_expr}")
rows = db.execute(
    "SELECT rowid, -bm25(fts_word) AS score FROM fts_word "
    "WHERE fts_word MATCH ? ORDER BY score DESC", (q_expr,)).fetchall()

print("\n  排名  文档  BM25分   标题")
for rank, (rid, score) in enumerate(rows, 1):
    print(f"   {rank}    D{rid}   {score:6.3f}   {DOCS[rid-1][1]}")
word_rank = {rid: r for r, (rid, _) in enumerate(rows, 1)}

print("\n  注意 D2 也被捞出来了 —— 因为它正文里有「保修」两个字。")
print("  BM25 让 D1 排在前面：D1 命中的词更多、文档更短。")


# ============================================================
# 实验三：trigram 检索
# ============================================================
line("实验三 · trigram（路 B）")

qt = trigrams(QUERY)
dt = trigrams(DOCS[0][1])
print(f"\n问题切片：{qt}")
print(f"D1 标题切片：{dt}")
print(f"\n  重合的片段：{[t for t in qt if t in dt]}")
print(f"  没对上的：  {[t for t in qt if t not in dt]}")
print("\n  「是店保」「店保吗」对不上 D1 的「是店铺」「店铺保」。")
print("  差一个字，整个片段就断了 —— trigram 也救不了「店保」。")

rows = db.execute(
    "SELECT rowid, -bm25(fts_tri) AS score FROM fts_tri "
    "WHERE fts_tri MATCH ? ORDER BY score DESC",
    (" OR ".join(f'"{t}"' for t in qt),)).fetchall()
print("\n  排名  文档  BM25分")
for rank, (rid, score) in enumerate(rows, 1):
    print(f"   {rank}    D{rid}   {score:6.3f}")
tri_rank = {rid: r for r, (rid, _) in enumerate(rows, 1)}


# ============================================================
# 实验四：别名路 —— 人工把「店保」补上
# ============================================================
line("实验四 · 别名路（路 C）")

ALIASES = {
    1: ["两年保修是店铺保修还是官方保修", "店保", "保修是店保吗", "保修是谁负责"],
    2: ["电池健康度低于80%可以更换", "电池能换吗", "电池保修"],
    3: ["退货地址在深圳龙华", "退货寄哪", "退货地址"],
}


def bigrams(s):
    return {s[i:i + 2] for i in range(len(s) - 1)}


def dice(a, b):
    """字符二元组 Dice 系数：2×交集 ÷ (两边总数)"""
    A, B = bigrams(a), bigrams(b)
    if not A or not B:
        return 0.0
    return 2 * len(A & B) / (len(A) + len(B))


print(f"\n顾客原话：{QUERY}\n")
alias_score = {}
for did, names in ALIASES.items():
    best_name, best = None, 0.0
    for n in names:
        s = dice(QUERY, n)
        if s > best:
            best, best_name = s, n
    alias_score[did] = best
    print(f"  D{did}  最高分 {best:.3f}   命中别名「{best_name}」")

print("\n  D1 拿到高分，靠的是运营手写的别名「保修是店保吗」。")
print("  这一路不猜，只认人写过的对应关系 —— 所以权重给到全场最高 1.30。")
print("  代价：没人写「店保」这个别名，这一路就完全失效。")

alias_rows = sorted([(d, s) for d, s in alias_score.items() if s >= 0.30],
                    key=lambda x: -x[1])
alias_rank = {d: r for r, (d, _) in enumerate(alias_rows, 1)}
print(f"\n  过 0.30 门槛并进入召回的：{[f'D{d}' for d, _ in alias_rows]}")


# ============================================================
# 实验五：语义路（用假向量演示，真实环境调 embedding 服务）
# ============================================================
line("实验五 · 语义向量（路 D）")

# 真实项目里这是 embedding 模型输出的 1024 维向量。
# 这里直接给出「模型会算出来的」相似度，重点看它的行为特征。
SEMANTIC = {1: 0.87, 2: 0.41, 3: 0.12}

print("\n  文档   余弦相似度")
for d, s in SEMANTIC.items():
    print(f"   D{d}      {s:.2f}    {DOCS[d-1][1]}")
print("\n  D1 拿到 0.87 —— 它完全没管有没有共同的字，只看意思。")
print("  这是四路里唯一一路，在没有别名的情况下也能救回「店保」。")
print("  它的短板在型号：XK-2000 和 XK-3000 在它眼里意思几乎一样。")

sem_rows = sorted(SEMANTIC.items(), key=lambda x: -x[1])
sem_rank = {d: r for r, (d, _) in enumerate(sem_rows, 1)}


# ============================================================
# 实验六：RRF 融合
# ============================================================
line("实验六 · RRF 融合四路")

WEIGHTS = {"词级": 1.00, "trigram": 1.00, "别名": 1.30, "语义": 1.15}
RANKS = {"词级": word_rank, "trigram": tri_rank, "别名": alias_rank, "语义": sem_rank}
K = 60

print(f"\n各路排名（k={K}）：\n")
header = "  文档  " + "".join(f"{p:>10}" for p in WEIGHTS)
print(header)
for d in (1, 2, 3):
    cells = "".join(f"{('第'+str(RANKS[p][d])) if d in RANKS[p] else '—':>10}"
                    for p in WEIGHTS)
    print(f"   D{d}  {cells}")

print("\n逐条算分：\n")
final = {}
for d in (1, 2, 3):
    total, parts = 0.0, []
    for path, w in WEIGHTS.items():
        r = RANKS[path].get(d)
        if r is None:
            parts.append(f"{path}未进=0")
            continue
        c = w / (K + r)
        total += c
        parts.append(f"{path} {w}/{K}+{r}={c:.4f}")
    final[d] = total
    print(f"  D{d}: " + "  +  ".join(parts))
    print(f"       合计 = {total:.4f}\n")

print("最终排序：")
for rank, (d, s) in enumerate(sorted(final.items(), key=lambda x: -x[1]), 1):
    print(f"  第{rank}名  D{d}  {s:.4f}   {DOCS[d-1][1]}")

print("\n  注意：从头到尾没有任何一个原始分数参与计算。")
print("  BM25 的 2.336、Dice 的 0.667、余弦的 0.87 —— 全都只用来排名次，")
print("  排完就丢掉。这就是 RRF 绕开量纲问题的方式。")


# ============================================================
# 交互模式
# ============================================================
def interactive():
    line("交互模式 · 自己输问题试（回车退出）")
    while True:
        try:
            q = input("\n问题> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q:
            break

        ws = tokenize(q)
        print(f"  分词：{ws or '（一个词都没切出来）'}")
        if ws:
            rs = db.execute(
                "SELECT rowid, -bm25(fts_word) FROM fts_word WHERE fts_word MATCH ? "
                "ORDER BY 2 DESC", (" OR ".join(ws),)).fetchall()
            print(f"  词级命中：{[f'D{r}({s:.2f})' for r, s in rs] or '无'}")
        else:
            print("  词级命中：无（切不出词就查不了）")

        ts = trigrams(q)
        if ts:
            rs = db.execute(
                "SELECT rowid, -bm25(fts_tri) FROM fts_tri WHERE fts_tri MATCH ? "
                "ORDER BY 2 DESC", (" OR ".join(f'"{t}"' for t in ts),)).fetchall()
            print(f"  trigram命中：{[f'D{r}({s:.2f})' for r, s in rs] or '无'}")

        al = {d: max(dice(q, n) for n in ns) for d, ns in ALIASES.items()}
        al = {d: s for d, s in al.items() if s >= 0.30}
        print(f"  别名命中：{[f'D{d}({s:.2f})' for d, s in sorted(al.items(), key=lambda x:-x[1])] or '无（都没过0.30）'}")


if __name__ == "__main__":
    if "-i" in sys.argv:
        interactive()
    else:
        print("\n（加 -i 参数可以进交互模式，自己输问题试）")