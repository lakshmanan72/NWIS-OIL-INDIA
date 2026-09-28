import urllib.request
import json

wells_to_test = [
    ("WELL-000001", "Baseline Well 1"),
    ("WELL-000050", "Prompt Well 50"),
    ("WELL-015108", "Baseline Well 15108"),
    ("WELL-012111", "JHIRNA-1 Canonical ID"),
    ("JHIRNA-1", "JHIRNA-1 Well Name"),
    ("438479b5_193d56910e1_4649", "JHIRNA-1 Source Hash"),
    ("wells_all_public.fid--438479b5_193d56910e1_4649", "JHIRNA-1 Legacy Feature ID"),
]

sub_routes = [
    "",
    "/geology",
    "/formations",
    "/drilling",
    "/mud-logging",
    "/events",
    "/completion",
    "/documents",
    "/risks",
    "/offset-intelligence?radius_km=25",
]

print("Verifying Well Intelligence API endpoints...")
all_passed = True

for wid, label in wells_to_test:
    encoded_wid = urllib.parse.quote(wid)
    print(f"\n--- Testing {label} ({wid}) ---")
    for sub in sub_routes:
        url = f"http://127.0.0.1:8000/api/wells/{encoded_wid}{sub}"
        try:
            r = urllib.request.urlopen(url)
            print(f"  GET {sub or '/'} -> HTTP {r.status}")
        except Exception as e:
            print(f"  GET {sub or '/'} -> FAILED: {e}")
            all_passed = False

if all_passed:
    print("\nALL WELL INTELLIGENCE ENDPOINTS PASSED WITH HTTP 200!")
else:
    print("\nSOME ENDPOINTS FAILED!")
