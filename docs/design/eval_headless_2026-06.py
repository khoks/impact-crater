# Historical (June 2026). Ad-hoc metric probe written during the E-2.10 quality pass and
# run by hand against a saved `headless_result.json`; promoted from the untracked .scratch/
# directory on 2026-10-24 (S-2.13.1) as the seed of the S-3.10.1 eval harness. Not tested,
# not wired into anything; `scripts/eval_plan.py` replaces it when E-3.10 opens.
import json, collections, datetime
d=json.load(open('headless_result.json'))
if 'arc_judgment' not in d:
    print("HTTP/ERROR:", json.dumps(d)[:600]); raise SystemExit
aj=d['arc_judgment']; cs=d['candidate_set']
items={ (c['content_hash'] + (f"#{c['scene_index']}" if c.get('scene_index') is not None else "")): c for c in cs['items'] }
sel=sorted(aj['selected_items'], key=lambda s:s['placement_position'])
print(f"media_count={d['media_count']}  candidates={d['candidate_count']}  selected={len(sel)}  confidence={aj.get('confidence')}")
nvid=sum(1 for s in sel if '#' in s['candidate_ref'])
print(f"VIDEO clips selected: {nvid}/{len(sel)} ({100*nvid//max(len(sel),1)}%)   [was 0/23]")
roles=collections.Counter(s.get('role') for s in sel)
print("roles:", dict(roles), f" peak%={100*roles.get('peak',0)//max(len(sel),1)}")
# chronology + per-item
print("\npos role        vid day        people? caption")
prev=None; backsteps=0
def ts(c): return (c.get('capture_timestamp') or '')
peoplec=0
for s in sel:
    c=items.get(s['candidate_ref'],{})
    t=ts(c); day=t[:10]; vid='VID' if '#' in s['candidate_ref'] else 'pho'
    ms=c.get('metadata_summary') or ''
    people = 'subjects=' in ms
    if people: peoplec+=1
    if prev and t and prev>t and s.get('role')!='callback': backsteps+=1
    if t: prev=t
    print(f"{s['placement_position']:2d}  {(s.get('role') or '')[:11]:11s} {vid} {day:10s} {'PPL' if people else '   '}     {(c.get('caption') or '')[:52]}")
print(f"\npeople-forward: {peoplec}/{len(sel)} ({100*peoplec//max(len(sel),1)}%)   chronology backsteps (non-callback): {backsteps}")
print("by day:", dict(collections.Counter((items.get(s['candidate_ref'],{}).get('capture_timestamp') or '')[:10] for s in sel)))
# consecutive-similarity: same day+role+vid run >2
def key(s):
    c=items.get(s['candidate_ref'],{})
    return ((c.get('capture_timestamp') or '')[:10], s.get('role'))
runs=1; maxrun=1
for i in range(1,len(sel)):
    if key(sel[i])==key(sel[i-1]): runs+=1; maxrun=max(maxrun,runs)
    else: runs=1
print("max consecutive same(day,role):", maxrun)
