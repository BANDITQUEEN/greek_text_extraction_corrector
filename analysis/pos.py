import csv, sys, random, unicodedata
from collections import Counter, defaultdict
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0,".")
import spacy, lexicon_filter as LF

C=list(csv.DictReader(open("lexicon_corrections.elpass.csv",encoding="utf-8-sig")))
random.seed(7)
byfile=defaultdict(list)
for r in C: byfile[r["filename"]].append(r)
pick=random.sample(sorted(byfile), 30)
wanted={f:byfile[f] for f in pick}
print(f"sampling {sum(len(v) for v in wanted.values()):,} corrections across {len(pick)} files")

def mojibake(t):
    # unambiguous encoding damage: a final sigma inside the word,
    # or the theta/zeta family this corpus's broken font produces
    return ("ς" in t[:-1]) or any(c in t for c in "θζϊφ") and t!=t

def damaged(t):
    return "ς" in t[:-1] or "ϊ" in t or "ϋ" in t

nlp=spacy.load("el_core_news_md")
pos_all=Counter(); pos_dmg=Counter(); seen=0
examples=defaultdict(list)
for fn,rows in wanted.items():
    p=LF.INPUT_DIR/fn
    if not p.exists(): continue
    tokens={r["original"] for r in rows}
    for is_sep,ch in LF.split_pages(p.read_text(encoding="utf-8")):
        if is_sep: continue
        if not any(t in ch for t in tokens): continue
        for tok in nlp(ch):
            if tok.text in tokens:
                seen+=1
                pos_all[tok.pos_]+=1
                if damaged(tok.text): pos_dmg[tok.pos_]+=1
                if len(examples[tok.pos_])<6: examples[tok.pos_].append(tok.text)

print(f"\ntagged {seen:,} corrected tokens in real context\n")
print(f"{'POS':8s} {'all corrected':>14s} {'of those, visibly damaged':>26s}   examples")
for p,n in pos_all.most_common():
    d=pos_dmg.get(p,0)
    print(f"{p:8s} {n:>8,} ({n/seen:5.1%}) {d:>14,} ({d/max(n,1):5.1%})   {', '.join(examples[p][:5])}")
