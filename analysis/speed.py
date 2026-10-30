import sys, time
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0,".")
import stanza, spacy, lexicon_filter as LF
from stanza.models.common.doc import Document

files=sorted(LF.INPUT_DIR.glob("*.txt"))[:3]
_,flat,_,_=LF.collect_chunks(files)
pages=flat[:120]
chars=sum(len(p) for p in pages)
print(f"{len(pages)} pages, {chars:,} chars\n")

nlp=spacy.load("el_core_news_md")
t=time.time(); [None for _ in nlp.pipe(pages, batch_size=64)]; a=time.time()-t
print(f"spaCy  pipe(batch=64)      {a:6.1f}s   {len(pages)/a:5.1f} pages/s")

sn=stanza.Pipeline("el", processors="tokenize,mwt,pos", verbose=False, use_gpu=False)
t=time.time(); [sn(p) for p in pages]; b=time.time()-t
print(f"stanza one page at a time  {b:6.1f}s   {len(pages)/b:5.1f} pages/s   ({b/a:.1f}x spaCy)")

t=time.time(); sn.bulk_process([Document([], text=p) for p in pages]); c=time.time()-t
print(f"stanza bulk_process        {c:6.1f}s   {len(pages)/c:5.1f} pages/s   ({c/a:.1f}x spaCy)")

full=30731
print(f"\nprojected over {full:,} pages:")
for nm,r in [("spaCy",len(pages)/a),("stanza single",len(pages)/b),("stanza bulk",len(pages)/c)]:
    print(f"  {nm:16s} {full/r/60:6.0f} min")
