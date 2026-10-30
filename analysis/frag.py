import csv, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0,".")
import lexicon_filter as LF
S=[r for r in csv.DictReader(open("lexicon_corrections__s30.csv",encoding="utf-8-sig"))]
for target in ["περίπτως","κατάςτας","είδου"]:
    hits=[r for r in S if r["original"]==target][:3]
    print(f"\n=== {target} -> {hits[0]['replacement'] if hits else '?'}  ({len(  [r for r in S if r['original']==target])} occurrences)")
    for r in hits:
        p=LF.INPUT_DIR/r["filename"]
        for is_sep,ch in LF.split_pages(p.read_text(encoding="utf-8")):
            if is_sep: continue
            i=ch.find(target)
            if i<0: continue
            print("   ...", repr(ch[max(0,i-60):i+len(target)+60]))
            break
