import sys, re
mode = sys.argv[2] if len(sys.argv) > 2 else 'game'
data = open(sys.argv[1], 'rb').read()
seen = set()
out = []
for m in re.finditer(rb'[\x20-\x7e]{4,}', data):
    s = m.group().decode('ascii')
    if s in seen: continue
    seen.add(s)
    if mode == 'game':
        if not s.startswith('/Game/'): continue
        if any(k in s for k in ('Wwise','Sfx_','Play_','Stop_')): continue
    out.append(s)
print('\n'.join(sorted(out)))
