import sys, re
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0,".")
import spacy, lexicon_filter as LF
nlp=spacy.load("el_core_news_md")
targets={"Νοφαλιά":"10795_1202_1202_02_DROMOI_&_POLITIS._sel_1.txt",
         "Νεόφρων":"10795_1013_1013.txt","Μελανίντ":"10795_1013_1013.txt",
         "Μπέρμπερ":"10795_1029_1029.txt","αυτόχθονου":"10795_1012_1012.txt",
         "αγροτουριστικούς":"10795_1032_1032.txt"}
for w,fn in targets.items():
    p=LF.INPUT_DIR/fn
    if not p.exists(): print(f"{w}: file missing {fn}"); continue
    raw=p.read_text(encoding="utf-8")
    chunks=[c for is_sep,c in LF.split_pages(raw) if not is_sep and w in c]
    if not chunks: print(f"\n=== {w}: not found in {fn}"); continue
    ch=chunks[0]; i=ch.find(w)
    print(f"\n=== {w}  ({fn[:34]})   {len(chunks)} page(s) contain it")
    print("   ...", ch[max(0,i-75):i+len(w)+45].replace("\n"," "), "...")
    doc=nlp(ch); found=False
    for t in doc:
        if t.text==w:
            prot=bool(t.ent_type_ or t.pos_=="PROPN")
            print(f"   spaCy: pos={t.pos_:6s} ent={t.ent_type_ or '-':8s} -> protected={prot}")
            found=True; break
    if not found: print("   (spaCy split it into sub-tokens)")
