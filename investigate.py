import urllib.request, urllib.parse, http.cookiejar, re, ssl, gzip

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(
    urllib.request.HTTPSHandler(context=ctx),
    urllib.request.HTTPCookieProcessor(jar)
)
opener.addheaders = [
    ('User-Agent','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120'),
    ('Accept','text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'),
    ('Accept-Language','ar,en-US;q=0.7,en;q=0.3'),
    ('Connection','keep-alive'),
]

BASE_URL = 'https://subp.mutah.edu.jo/'

def decode_resp(r):
    raw = r.read()
    if r.headers.get('Content-Encoding','') == 'gzip':
        raw = gzip.decompress(raw)
    return raw.decode('utf-8', errors='replace')

print('='*60)
print('STEP 1: Initial GET')
print('='*60)
resp = opener.open(BASE_URL, timeout=25)
html = decode_resp(resp)
print('Status:', resp.status)
print('Content-Type:', resp.headers.get('Content-Type',''))
print('HTML size:', len(html), 'bytes')
print()
print('--- WAF/Session Cookies ---')
for c in jar:
    print(f'  Name: {c.name}')
    print(f'  Domain: {c.domain}')
    print(f'  Value[:80]: {c.value[:80]}')
    print()

print('--- Response Headers ---')
for h,v in resp.headers.items():
    print(f'  {h}: {v}')
print()

# Extract ASP.NET state fields using single-quote pattern
vs_match = re.search(r"id='__VIEWSTATE' value='([^']+)'", html)
if not vs_match:
    vs_match = re.search(r'__VIEWSTATE[^>]+value="([^"]+)"', html)

vsg_match = re.search(r"id='__VIEWSTATEGENERATOR' value='([^']+)'", html)
if not vsg_match:
    vsg_match = re.search(r'__VIEWSTATEGENERATOR[^>]+value="([^"]+)"', html)

ev_match = re.search(r"id='__EVENTVALIDATION' value='([^']+)'", html)
if not ev_match:
    ev_match = re.search(r'__EVENTVALIDATION[^>]+value="([^"]+)"', html)

# Try with escaped quotes too
if not vs_match:
    vs_match = re.search(r'name="__VIEWSTATE"[^/]*/?\s*id="__VIEWSTATE"\s*value="([^"]{10,})"', html)

print('--- ASP.NET Hidden Fields ---')
viewstate = vs_match.group(1) if vs_match else None
viewstate_gen = vsg_match.group(1) if vsg_match else None
eventvalidation = ev_match.group(1) if ev_match else None
print('  __VIEWSTATE found:', bool(viewstate), '| length:', len(viewstate) if viewstate else 0)
print('  __VIEWSTATEGENERATOR:', viewstate_gen)
print('  __EVENTVALIDATION found:', bool(eventvalidation), '| length:', len(eventvalidation) if eventvalidation else 0)
print()

# Show raw hidden field area for debugging
hidden_area = re.search(r'type="hidden".*?__VIEWSTATE.*?value="([^"]{20,50})', html, re.DOTALL)
if hidden_area:
    print('  Raw area sample:', hidden_area.group(0)[:150])
else:
    # Find all hidden fields
    hiddens = re.findall(r'type="hidden"[^>]+name="([^"]+)"[^>]+value="([^"]{0,30})"', html)
    print('  All hidden fields found:', hiddens)
print()

courses = re.findall(r'<td>(\d{7})</td>', html)
print(f'Course rows on page 1: {len(courses)}')
print(f'Sample courses: {courses[:5]}')
print()

js_files = re.findall(r'src="([^"]+\.js[^"]*)"', html)
print('JavaScript files:')
for j in js_files:
    print(f'  {j}')
print()

api_hints = re.findall(r"(fetch\(|axios\.|XMLHttpRequest|\.ajax\(|/api/|apiUrl|baseURL)[^\\n]{0,80}", html)
print('API/Fetch hints in HTML:', len(api_hints))
for a in api_hints[:5]:
    print(f'  {a[:100]}')
print()

print('='*60)
print('STEP 2: Test POST with filter (course 0209100)')
print('='*60)

if viewstate:
    post_fields = {
        '__VIEWSTATE': viewstate,
        '__VIEWSTATEGENERATOR': viewstate_gen or '',
        '__EVENTVALIDATION': eventvalidation or '',
        'lstSearchCol': '0',
        'txtSearchSubID': '0209100',
        'txtSearchSubName': '',
        'txtSearchSection': '',
        'txtSearchTeacher': '',
        'ImageButton1.x': '10',
        'ImageButton1.y': '10',
    }
    post_body = urllib.parse.urlencode(post_fields).encode('utf-8')
    print(f'POST to: {BASE_URL}')
    print(f'Body size: {len(post_body)} bytes')
    print(f'Fields: lstSearchCol=0, txtSearchSubID=0209100')
    print()
    req2 = urllib.request.Request(BASE_URL, data=post_body)
    req2.add_header('Content-Type', 'application/x-www-form-urlencoded')
    req2.add_header('Referer', BASE_URL)
    req2.add_header('Origin', 'https://subp.mutah.edu.jo')
    try:
        resp2 = opener.open(req2, timeout=25)
        html2 = decode_resp(resp2)
        print('POST Status:', resp2.status)
        print('POST CT:', resp2.headers.get('Content-Type',''))
        print('POST HTML size:', len(html2))
        is_json = html2.strip()[:1] in ('{','[')
        print('Is JSON:', is_json)
        print('Is HTML:', '<html' in html2.lower())
        print()
        c2 = re.findall(r'<td>(\d{7})</td>', html2)
        print('Courses in filtered response:', c2)
        print('0209100 present:', '0209100' in html2)
        if '0209100' in html2:
            print('SUCCESS - filtering works via POST!')
            row = re.search(r'<td>[^<]+</td><td>0209100</td><td>([^<]+)</td><td>(\d+)</td><td>([^<]+)</td><td>(\d+)</td><td>(\d+)</td>', html2)
            if row:
                print(f'  Name: {row.group(1)}')
                print(f'  Section: {row.group(2)}')
                print(f'  Teacher: {row.group(3)}')
                print(f'  Capacity: {row.group(4)}')
                print(f'  Enrolled: {row.group(5)}')
    except Exception as e2:
        import traceback; traceback.print_exc()
else:
    print('Cannot test POST - ViewState not extracted')
    print('Trying POST without ViewState...')
    post_fields_min = {
        'lstSearchCol': '0',
        'txtSearchSubID': '0209100',
        'txtSearchSubName': '',
        'txtSearchSection': '',
        'txtSearchTeacher': '',
        'ImageButton1.x': '10',
        'ImageButton1.y': '10',
    }
    post_body_min = urllib.parse.urlencode(post_fields_min).encode('utf-8')
    req_min = urllib.request.Request(BASE_URL, data=post_body_min)
    req_min.add_header('Content-Type', 'application/x-www-form-urlencoded')
    req_min.add_header('Referer', BASE_URL)
    try:
        r_min = opener.open(req_min, timeout=20)
        h_min = decode_resp(r_min)
        print('POST (no VS) Status:', r_min.status)
        c_min = re.findall(r'<td>(\d{7})</td>', h_min)
        print('Courses in response:', c_min[:10])
        print('0209100 in response:', '0209100' in h_min)
    except Exception as em:
        print('Error (no VS):', em)

print()
print('='*60)
print('STEP 3: Direct GET with URL params (no state)')
print('='*60)
test_url = BASE_URL + '?txtSearchSubID=0209100'
resp3 = opener.open(test_url, timeout=15)
html3 = decode_resp(resp3)
c3 = re.findall(r'<td>(\d{7})</td>', html3)
print('GET ?txtSearchSubID=0209100 status:', resp3.status)
print('Courses:', c3[:5])
print('0209100 in response:', '0209100' in html3)

print()
print('='*60)
print('STEP 4: Check for any hidden JSON/API endpoints')
print('='*60)
for test_path in ['/api/courses', '/api/sections', '/courses.json', '/data', '/search', '/api']:
    try:
        ru = opener.open('https://subp.mutah.edu.jo' + test_path, timeout=8)
        print(f'{test_path}: {ru.status} | CT: {ru.headers.get("Content-Type","")}')
    except Exception as ep:
        print(f'{test_path}: {type(ep).__name__} - {str(ep)[:60]}')
