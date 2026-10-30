import gzip, pickle, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0,".")
import lexicon_filter as LF

files=sorted(LF.INPUT_DIR.glob("*.txt"))[:6]
per,flat,owner,sig=LF.collect_chunks(files)
ck=pickle.load(gzip.open("lexicon_filter_checkpoint.pkl.gz","rb"))
rep=ck["replacements"]

# 1. with no replacements at all the text must come back byte-identical
assert all(LF.filter_chunk(c, []) == c for c in flat)
print("PASS  no replacements -> output is byte-identical to input")

# 2. the length delta must be exactly accounted for by the replacements
predicted = sum(len(r[2]) - (r[1]-r[0]) for pg in rep for r in pg)
actual = sum(len(LF.filter_chunk(flat[i], rep[i])) - len(flat[i]) for i in range(len(flat)))
print(f"PASS  delta explained: predicted {predicted:+,}  actual {actual:+,}" if predicted==actual
      else f"FAIL  predicted {predicted:+,} != actual {actual:+,}")

# 3. every character outside a replacement span survives untouched
bad=0
for i,c in enumerate(flat):
    out=LF.filter_chunk(c, rep[i]); cur=0; oc=0
    for s0,e0,r in (x[:3] for x in rep[i]):
        if out[oc:oc+(s0-cur)] != c[cur:s0]: bad+=1; break
        oc+=s0-cur; oc+=len(r); cur=e0
    else:
        if out[oc:] != c[cur:]: bad+=1
print(f"PASS  all {len(flat)} pages preserve text outside replacements" if bad==0
      else f"FAIL  {bad} pages differ outside replacement spans")

# 4. no word tokens lost
import re
TOK=re.compile(r"\S+"); LET=re.compile(r"[^\W\d_]+")
bi=bo=0
for i,c in enumerate(flat):
    out=LF.filter_chunk(c, rep[i])
    bi+=sum(1 for t in TOK.findall(c) if LET.search(t))
    bo+=sum(1 for t in TOK.findall(out) if LET.search(t))
print(f"word tokens in={bi:,} out={bo:,}  delta={bo-bi:+,}")
print("PASS  no tokens deleted" if bo>=bi else "FAIL  tokens lost")
