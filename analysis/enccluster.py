"""Is mis-encoding a property of whole pages, or of scattered tokens?"""
import re, sys, unicodedata
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0,".")
import lexicon_filter as LF

PAIRS=[("mac_roman","mac_greek"),("cp1252","iso8859_7")]
GREEKY=re.compile(r"^[\u0370-\u03ff\u1f00-\u1fff'\u2019]+$")
TOK=re.compile(r"\S+")

def try_recover(t):
    for w,r in PAIRS:
        try: back=t.encode(w,"strict").decode(r,"strict")
        except (UnicodeEncodeError,UnicodeDecodeError): continue
        if GREEKY.match(back) and len(back)>=4: return back
    return None

pages_stat=Counter(); dist=Counter(); worst=[]
for p in LF.INPUT_DIR.glob("*.txt"):
    for is_sep,chunk in LF.split_pages(p.read_text(encoding="utf-8")):
        if is_sep: continue
        toks=[t.strip(".,;:()[]«»\"'!?·-–—") for t in TOK.findall(chunk)]
        toks=[t for t in toks if len(t)>=4]
        if not toks: continue
        rec=sum(1 for t in toks if not LF.GREEK_RE.search(t) and try_recover(t))
        share=rec/len(toks)
        pages_stat["pages"]+=1
        if rec:
            pages_stat["pages with >=1"]+=1
            b=("90-100%" if share>=.9 else "50-90%" if share>=.5 else
               "10-50%" if share>=.1 else "under 10%")
            dist[b]+=1
            if share>=.5: worst.append((share,rec,len(toks),p.name))
print(f"pages scanned            : {pages_stat['pages']:,}")
print(f"pages with a recoverable token: {pages_stat['pages with >=1']:,}\n")
print("when a page has any, what share of its long tokens are mis-encoded?")
for k in ["90-100%","50-90%","10-50%","under 10%"]:
    print(f"   {k:10s} {dist[k]:>5,} pages")
worst.sort(reverse=True)
print(f"\npages that are >=50% mis-encoded: {len(worst)}")
for sh,rec,tot,n in worst[:10]:
    print(f"   {sh:5.0%}  {rec:>4}/{tot:<4}  {n[:52]}")
