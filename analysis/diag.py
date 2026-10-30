import csv, sys, unicodedata
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0,".")
import lexicon_filter as LF

C=list(csv.DictReader(open("lexicon_corrections.elpass.csv",encoding="utf-8-sig")))
idx={}
for r in C: idx.setdefault(r["original"],[]).append(r)

print("=== 1. the examples you flagged ===")
for w in ["Μελανίντ","Νεόφρων","Μπέρμπερ","Νοφαλιά","αφυπνιστή","περιποιητής",
          "χρονικό","πολυομματικής","αυτόχθονου","αγροτουριστικούς"]:
    rows=idx.get(w)
    if rows: print(f"  {w:20s} -> {rows[0]['replacement']:20s} x{len(rows):<5} sim={rows[0]['similarity']} runner={rows[0]['runner_up'] or '-'}")
    else:    print(f"  {w:20s} -- not corrected in this pass")

print("\n=== 2. are they in the dictionary at all? ===")
known=LF._known_surfaces(LF.LEXICON_DIR/"el.known.txt")
freq={}
for line in open("lexicons/el.txt",encoding="utf-8"):
    p=line.rstrip("\n").rsplit(" ",1)
    if len(p)==2 and p[1].isdigit(): freq[unicodedata.normalize("NFC",p[0])]=int(p[1])
for w in ["Μελανίντ","Νεόφρων","Μπέρμπερ","Νοφαλιά","αφυπνιστή","περιποιητής",
          "χρονικό","πολυομματικής","αυτόχθονου","αγροτουριστικούς",
          "Μελανίνη","Νεφρών","Μπάρμπερ","Νηφάλια","αυτόχθονο","αγροτουριστικού"]:
    n=unicodedata.normalize("NFC",w)
    print(f"  {w:20s} in gate={str(n in known or n.lower() in known):5s}  freq={freq.get(n,0):,}")
