"""Run from file_bundler: python tests/verify_result.py [output directory]."""
import json, sys, hashlib, zipfile
from pathlib import Path
import fitz
p=Path(sys.argv[1] if len(sys.argv)>1 else 'tests/result')
m=json.loads((p/'content.json').read_text(encoding='utf-8'))
assert m['archive_verified'] and m['file_count']==4
with zipfile.ZipFile(p/'originals.zip') as archive:
    for f in m['files']:
        assert hashlib.sha256(archive.read(f['path'])).hexdigest()==f['sha256']
x=next(f for f in m['files'] if f['path']=='wide.xlsx')
assert len(x['sheets'])==2 and x['sheets'][1]['state']=='hidden'
assert 'END_MARKER' in x['sheets'][0]['cells'][0]['value_or_cached_result']
assert x['sheets'][0]['cells'][3]['formula']['text']=='A2*2'
assert len(x.get('visuals',[]))>=2, x['warnings']
with fitz.open(p/'visuals.pdf') as doc:
    text=''.join(pg.get_text() for pg in doc)
    assert all(t in text for t in ['END_MARKER','FAR_RIGHT_MARKER','HIDDEN_MARKER'])
    assert len(doc)==m['pdf_page_count']
for v in x['visuals']:
    if v['tiles']:
        assert max(t['clip_points'][2] for t in v['tiles'])==v['size_points'][0]
        assert max(t['clip_points'][3] for t in v['tiles'])==v['size_points'][1]
assert m['archive_only_count']==1 and m['partial_count']==0
print('PASS: archive bytes, hidden sheet, formula, long text, far-right text, tile extents, page references and unsupported format')
