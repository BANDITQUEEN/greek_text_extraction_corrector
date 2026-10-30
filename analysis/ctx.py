import csv, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0,".")
import spacy, lexicon_filter as LF

C=list(csv.DictReader(open("lexicon_corrections.elpass.csv",encoding="utf-8-sig")))
want={"Νοφαλιά","Νεόφρων","Μελανίντ","Μπέρμπερ","αυτόχθονου","αγροτουριστικούς"}
hits={}
for r in C:
    if r["original"] in want and r["original"] not in hits: hits[r["original"]]=r

files={p.name:p for p in LF.INPUT_DIR.glob("*.txt")}
nlp=spacy.load("el_core_news_md")

for w,r in hits.items():
    raw=files[r["filename"]].read_text(encoding="utf-8")
    parts=LF.split_pages(raw)
    # find the page chunk containing this offset
    chunk=None
    for is_sep,part in parts:
        if is_sep: continue
        s,e=int(r["page_char_start"]),int(r["page_char_end"])
        if len(part)>e and part[s:e]==w: chunk=part; break
    print(f"\n=== {w}  ({r['filename'][:40]} p.{r['page']}) -> {r['replacement']}")
    if chunk is None:
        print("   (page not located)"); continue
    s=int(r["page_char_start"])
    print("   context:", repr(chunk[max(0,s-70):s+len(w)+40].replace("\n"," ")))
    doc=nlp(chunk)
    for t in doc:
        if t.idx==s and t.text==w:
            print(f"   spaCy in context: pos={t.pos_}  ent={t.ent_type_ or '-'}  "
                  f"-> would protect = {bool(t.ent_type_ or t.pos_=='PROPN')}")
            break
    else:
        print("   token not found at that offset in this doc")
