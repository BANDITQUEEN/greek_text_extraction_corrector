"""How much text do the two recovery transforms actually reach?"""
import re, sys, unicodedata
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0,".")
import lexicon_filter as LF

PAIRS=[("mac_roman","mac_greek"),("cp1252","iso8859_7")]
known=LF._known_surfaces(LF.LEXICON_DIR/"el.known.txt")
GREEKY=re.compile(r"^[\u0370-\u03ff\u1f00-\u1fff'\u2019]+$")
TOK=re.compile(r"\S+")

def recover(tok):
    for w,r in PAIRS:
        try: back=tok.encode(w,"strict").decode(r,"strict")
        except (UnicodeEncodeError,UnicodeDecodeError): continue
        if GREEKY.match(back): return back,f"{w}->{r}"
    return None,None

stat=Counter(); byfile=Counter(); ex=Counter()
for p in LF.INPUT_DIR.glob("*.txt"):
    for t in TOK.findall(p.read_text(encoding="utf-8")):
        core=t.strip(".,;:()[]«»\"'!?·-–—")
        if len(core)<3 or LF.GREEK_RE.search(core) or core.isascii(): continue
        back,pair=recover(core)
        if not back: continue
        stat["recovered"]+=1; byfile[p.name]+=1
        n=unicodedata.normalize("NFC",back)
        if n in known or n.lower() in known: stat["and is a dictionary word"]+=1
        else: ex[(core,back)]+=1
print(f"tokens the transforms turn into all-Greek strings : {stat['recovered']:,}")
print(f"  of those, confirmed in the dictionary           : {stat['and is a dictionary word']:,}")
print(f"  plausible Greek but not in the word list        : {stat['recovered']-stat['and is a dictionary word']:,}")
print(f"\naffected files: {len(byfile)}")
for f,n in byfile.most_common(8): print(f"   {n:>6,}  {f[:58]}")
print("\nrecovered but not in the dictionary -- sanity-check these read as Greek:")
for (a,b),n in ex.most_common(14): print(f"   {a:26s} -> {b:24s} x{n}")
