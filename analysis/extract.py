import gzip, pickle, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
import lexicon_filter as LF

# Write beside the real outputs under distinct names so the 19-Aug results,
# which are also the comparison baseline, are not clobbered by a partial run.
LF.CORRECTIONS_LOG = Path("lexicon_corrections.elpass.csv")
LF.UNRESOLVED_LOG  = Path("lexicon_unresolved.elpass.csv")

files = sorted(LF.INPUT_DIR.glob("*.txt"))
per_file_parts, flat, owner, sig = LF.collect_chunks(files)

with gzip.open("lexicon_filter_checkpoint.pkl.gz", "rb") as fh:
    ck = pickle.load(fh)

print("models in checkpoint :", ck["completed_models"])
print("signature matches    :", ck["input_signature"] == sig)
if ck["input_signature"] != sig:
    sys.exit("checkpoint does not match current inputs/constants; aborting")

n1 = LF.write_corrections_log(files, per_file_parts, owner, ck["replacements"])
n2 = LF.write_unresolved_log(files, per_file_parts, owner, ck["unresolved"])
print(f"corrections rows     : {n1:,} -> {LF.CORRECTIONS_LOG}")
print(f"unresolved rows      : {n2:,} -> {LF.UNRESOLVED_LOG}")
