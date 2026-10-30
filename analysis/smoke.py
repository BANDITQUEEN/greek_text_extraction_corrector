import re, sys, time
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0,".")
import lexicon_filter as LF

LF.apply_run_name("smoke")   # never touch the real run's checkpoint/outputs
files=sorted(LF.INPUT_DIR.glob("*.txt"))[:6]
print("smoke test on:", [f.name[:34] for f in files])
per,flat,owner,sig=LF.collect_chunks(files)
print(f"pages: {len(flat)}   models: {LF.all_model_names()}")

routings=[LF.build_page_routing(c) for c in flat]
rc={"el":0,"grc":0}
for r in routings:
    for l in r.lines:
        if l.greek in rc: rc[l.greek]+=1
print("greek lines:", rc)

anc,n=LF.score_ancient_files(len(files),flat,owner)
print(f"ancient files: {n}/{len(files)}")

lex=LF.make_correction_lexicon(LF.ROUTE)

t=time.time()
rep,unr=LF.compute_protected(flat,routings,anc,lex,sig)
print(f"pass took {time.time()-t:.0f}s")
R=[x for pg in rep for x in pg]; U=[x for pg in unr for x in pg]
print(f"corrections {len(R):,}   unresolved {len(U):,}")

# The guarantee is that no word token disappears -- not that the character
# count never falls. A one-edit repair may legitimately delete a character:
# "ταγγελία" -> "αγγελία", "Ααπασχόλησης" -> "Απασχόλησης".
TOK=re.compile(r"\S+"); LET=re.compile(r"[^\W\d_]+")
def words(t): return sum(1 for x in TOK.findall(t) if LET.search(x))
before=after=0
for pi in range(len(flat)):
    before+=words(flat[pi]); after+=words(LF.filter_chunk(flat[pi],rep[pi]))
print(f"word tokens in={before:,} out={after:,}  delta={after-before:+,}")
assert after>=before, "WORD TOKENS LOST -- deletion still happening"
print("PASS: no word tokens deleted")
for x in R[:6]:
    print(f"   {x[3]} -> {x[2]}")
