import urllib.request
import json

urls = [
    'http://127.0.0.1:8000/api/wells/WELL-000001',
    'http://127.0.0.1:8000/api/wells/WELL-000050',
    'http://127.0.0.1:8000/api/wells/WELL-015108',
    'http://127.0.0.1:8000/api/wells/WELL-012111',
    'http://127.0.0.1:8000/api/wells/wells_all_public.fid--438479b5_193d56910e1_4649',
    'http://127.0.0.1:8000/api/wells/438479b5_193d56910e1_4649',
    'http://127.0.0.1:8000/api/wells/JHIRNA-1'
]

for u in urls:
    try:
        r = urllib.request.urlopen(u)
        d = json.loads(r.read().decode())
        print(f"{u.split('/')[-1]} -> HTTP {r.status} | well_id={d.get('well_id')} | name={d.get('well_name')}")
    except Exception as e:
        print(f"{u.split('/')[-1]} -> ERROR: {e}")
