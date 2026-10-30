import csv, re, sys, time
from collections import Counter, defaultdict
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0,".")
import spacy, stanza, lexicon_filter as LF

C=list(csv.DictReader(open("lexicon_corrections.elpass.csv",encoding="utf-8-sig")))
def titlecase(w): return len(w)>1 and w[0].isupper() and w[1:].islower()
cap=[r for r in C if titlecase(r["original"]) and int(r["page_char_start"])>3]
byfile=defaultdict(set)
for r in cap: byfile[r["filename"]].add(r["original"])
print(f"{len(cap):,} capitalised corrections across {len(byfile)} files")

# collect target occurrences: (page_text, offset, token)
jobs=[]; PAGES=140
for fn,toks in sorted(byfile.items()):
    p=LF.INPUT_DIR/fn
    if not p.exists(): continue
    for is_sep,ch in LF.split_pages(p.read_text(encoding="utf-8")):
        if is_sep: continue
        hits=[]
        for t in toks:
            for m in re.finditer(r"(?<![^\W\d_])"+re.escape(t)+r"(?![^\W\d_])", ch):
                hits.append((m.start(), t))
        if hits: jobs.append((ch, hits))
        if len(jobs)>=PAGES: break
    if len(jobs)>=PAGES: break
n_tok=sum(len(h) for _,h in jobs)
print(f"benchmarking {n_tok:,} token occurrences over {len(jobs)} pages\n")

nlp=spacy.load("el_core_news_md")
t0=time.time()
sp={}
for pi,(ch,hits) in enumerate(jobs):
    doc=nlp(ch)
    at={t.idx:(t.pos_,t.ent_type_) for t in doc}
    for off,tok in hits: sp[(pi,off)]=at.get(off,("<split>",""))
t_spacy=time.time()-t0

snlp=stanza.Pipeline("el", processors="tokenize,mwt,pos", verbose=False,
                     tokenize_no_ssplit=False, use_gpu=False)
t0=time.time()
st={}
for pi,(ch,hits) in enumerate(jobs):
    doc=snlp(ch)
    at={}
    for s in doc.sentences:
        for w in s.words:
            if w.parent.start_char is not None: at[w.parent.start_char]=w.upos
    for off,tok in hits: st[(pi,off)]=at.get(off,"<split>")
t_stanza=time.time()-t0

keys=[k for k in sp if k in st]
print(f"aligned {len(keys):,} occurrences")
print(f"speed: spaCy {t_spacy:.0f}s   stanza {t_stanza:.0f}s   ({t_stanza/max(t_spacy,.01):.1f}x slower)\n")

sp_prot=sum(1 for k in keys if sp[k][0]=="PROPN" or sp[k][1])
st_prot=sum(1 for k in keys if st[k]=="PROPN")
print(f"would be PROTECTED as a proper noun:")
print(f"  spaCy  (PROPN or entity) : {sp_prot:,} / {len(keys):,}  ({sp_prot/len(keys):5.1%})")
print(f"  stanza (PROPN)           : {st_prot:,} / {len(keys):,}  ({st_prot/len(keys):5.1%})")
gain=[k for k in keys if st[k]=="PROPN" and not (sp[k][0]=="PROPN" or sp[k][1])]
loss=[k for k in keys if (sp[k][0]=="PROPN" or sp[k][1]) and st[k]!="PROPN"]
print(f"  stanza catches that spaCy misses : {len(gain):,}")
print(f"  spaCy catches that stanza misses : {len(loss):,}")

off2tok={(pi,o):t for pi,(ch,h) in enumerate(jobs) for o,t in h}
print("\n  examples stanza would newly protect:")
for k in gain[:12]: print(f"    {off2tok[k]:20s} spaCy={sp[k][0]:6s} -> stanza=PROPN")
print("\n  examples stanza would newly expose:")
for k in loss[:8]: print(f"    {off2tok[k]:20s} spaCy={sp[k][0]}/{sp[k][1] or '-'} -> stanza={st[k]}")
