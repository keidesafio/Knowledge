#!/usr/bin/env python3
"""Local, auditable three-file bundler. Python 3.10+. See README_JA.md."""
import argparse, hashlib, io, json, os, posixpath, shutil, subprocess, sys, tempfile, zipfile
from pathlib import Path
from datetime import datetime, timezone
import xml.etree.ElementTree as ET
import fitz
from PIL import Image, ImageSequence, ImageOps
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

OFFICE = {'.xlsx','.xlsm','.xls','.xlsb','.ods','.docx','.docm','.doc','.odt','.rtf','.pptx','.pptm','.ppt','.odp'}
SHEETS = {'.xlsx','.xlsm','.xls','.xlsb','.ods'}
PACKAGES = {'.xlsx','.xlsm','.docx','.docm','.pptx','.pptm','.ods','.odt','.odp'}
IMAGES = {'.png','.jpg','.jpeg','.tif','.tiff','.bmp','.gif','.webp'}
TEXT = {'.txt','.md','.csv','.tsv','.json','.jsonl','.xml','.yaml','.yml','.html','.htm','.log','.py','.js','.ts','.tsx','.jsx','.cs','.cpp','.c','.h','.sql','.ini','.cfg','.toml','.sh','.bat','.ps1','.css','.svg'}
NS = {'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
FONT = 'HeiseiKakuGo-W5'

def sha(stream):
    h = hashlib.sha256()
    for b in iter(lambda: stream.read(1024*1024), b''): h.update(b)
    return h.hexdigest()

def decode(b):
    encs = ['utf-8-sig','cp932']
    if b[:2] in (b'\xff\xfe',b'\xfe\xff'): encs.insert(0,'utf-16')
    for enc in encs:
        try: return b.decode(enc), enc
        except UnicodeError: pass
    raise ValueError('Cannot decode text without replacement; original retained')

def label_page(doc, text):
    return add_text(doc, [text], 'Source / 出典')

def add_text(doc, lines, heading):
    """Character-width wrapping, then page breaks; no per-cell truncation."""
    buf = io.BytesIO(); c = canvas.Canvas(buf, pagesize=(595,842))
    y = 790; page_no = 0
    def start():
        nonlocal y, page_no
        if page_no: c.showPage()
        page_no += 1; y = 790
        c.setFont(FONT,9); c.drawString(32,812,heading[:85])
        c.setFont('Helvetica',8); c.drawString(32,20,str(page_no))
        c.setFont(FONT,10)
    start()
    for text in lines:
        for raw in str(text).expandtabs(4).split('\n'):
            line = ''; width = 0
            for ch in raw:
                if ord(ch) < 32: ch = ' '
                w = pdfmetrics.stringWidth(ch,FONT,10)
                if width+w > 525 and line:
                    if y < 42: start()
                    c.drawString(32,y,line); y -= 15; line=''; width=0
                line += ch; width += w
            if y < 42: start()
            c.drawString(32,y,line); y -= 15
        y -= 4
    c.save()
    with fitz.open(stream=buf.getvalue(),filetype='pdf') as part:
        first = len(doc)+1; doc.insert_pdf(part); return [first,len(doc)]

def add_visual(doc, src, item, source_label, tile=False, ocr=False, lang='jpn+eng'):
    """Full overview + overlapping 1:1 clips of large sheets/images."""
    records=[]
    for i,p in enumerate(src):
        rec={'source':source_label,'source_page':i+1,'size_points':[p.rect.width,p.rect.height], 'text':p.get_text(), 'text_blocks':[list(b) for b in p.get_text('blocks')]}
        if ocr:
            try: rec['ocr_text']=p.get_text(textpage=p.get_textpage_ocr(language=lang,full=True))
            except Exception as exc: item['warnings'].append('OCR failed: '+str(exc))
        rec['overview_pdf_page']=len(doc)+1
        # Exact-sized page retains native text and graphics; no downsampling.
        doc.insert_pdf(src,from_page=i,to_page=i)
        rec['tiles']=[]
        if tile and (p.rect.width>535 or p.rect.height>750):
            y=0.; row=0
            while y < p.rect.height:
                x=0.; col=0
                while x < p.rect.width:
                    clip=fitz.Rect(x,y,min(x+535,p.rect.width),min(y+750,p.rect.height))
                    out=doc.new_page(width=595,height=842)
                    out.insert_text((30,22),f"{item['id']} source page {i+1} tile {row+1},{col+1}",fontsize=9)
                    target=fitz.Rect(30,40,30+clip.width,40+clip.height)
                    if p.get_contents(): out.show_pdf_page(target,src,i,clip=clip)
                    rec['tiles'].append({'pdf_page':len(doc),'clip_points':list(clip)})
                    if x+535 >= p.rect.width: break
                    x += 511; col += 1
                if y+750 >= p.rect.height: break
                y += 726; row += 1
        records.append(rec)
    item.setdefault('visuals',[]).extend(records)

def image_pdf(data):
    result=fitz.open()
    with Image.open(io.BytesIO(data)) as im:
        for frame in ImageSequence.Iterator(im):
            frame=ImageOps.exif_transpose(frame.copy()).convert('RGBA')
            b=io.BytesIO(); frame.save(b,format='PNG')
            # 96 dpi for placement only; retain full-resolution bitmap.
            page=result.new_page(width=max(1,frame.width*.75),height=max(1,frame.height*.75))
            page.insert_image(page.rect,stream=b.getvalue())
    return result

def package_extract(path, item, doc):
    with zipfile.ZipFile(path) as z:
        # Keep XML relationships, notes, chart data and formatting explicitly.
        item['xml_parts']={}
        for name in z.namelist():
            if name.endswith(('.xml','.rels')):
                raw=z.read(name)
                try:
                    root=ET.fromstring(raw)
                    item['xml_parts'][name]={'xml':ET.tostring(root,encoding='unicode'), 'text_nodes':list(root.itertext())}
                except ET.ParseError as exc: item['warnings'].append(f'XML parse failed {name}: {exc}')
        if path.suffix.lower() in {'.xlsx','.xlsm'}:
            shared=[]
            if 'xl/sharedStrings.xml' in z.namelist():
                for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',NS):
                    shared.append(''.join(t.text or '' for t in si.iter('{'+NS['s']+'}t')))
            rels={r.attrib['Id']:r.attrib['Target'] for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
            item['sheets']=[]
            for s in ET.fromstring(z.read('xl/workbook.xml')).findall('s:sheets/s:sheet',NS):
                target=rels[s.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']]
                part=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
                root=ET.fromstring(z.read(part))
                sheet={'name':s.attrib['name'],'state':s.get('state','visible'),'xml_part':part,'cells':[], 'merged_ranges':[m.get('ref') for m in root.findall('s:mergeCells/s:mergeCell',NS)]}
                for c in root.findall('s:sheetData/s:row/s:c',NS):
                    v=c.find('s:v',NS); f=c.find('s:f',NS)
                    value=v.text if v is not None else None
                    if c.get('t')=='s' and value is not None: value=shared[int(value)]
                    if c.get('t')=='inlineStr': value=''.join(t.text or '' for t in c.findall('.//s:t',NS))
                    sheet['cells'].append({'address':c.get('r'),'type':c.get('t','n'),'style_index':c.get('s'), 'value_or_cached_result':value, 'formula':None if f is None else {'text':f.text,'attributes':f.attrib}})
                lines=[f"Sheet: {sheet['name']} / original state: {sheet['state']}", 'Cell ledger / セル全文（表示書式適用前の値・保存済み計算結果）']
                for c in sheet['cells']:
                    if c['value_or_cached_result'] is not None or c['formula'] is not None:
                        lines.append(c['address']+' : '+str(c['value_or_cached_result']))
                        if c['formula'] is not None: lines.append('Formula: '+json.dumps(c['formula'],ensure_ascii=False))
                sheet['ledger_pdf_pages']=add_text(doc,lines,item['id']+' / '+sheet['name'])
                item['sheets'].append(sheet)
            item['warnings'].append('Sheet visuals require review: row/column hiding, cell overflow, fonts, chart fidelity and recalculation may differ. Ledger includes stored cells, including hidden cells. Raw values are not formatted display strings.')
        for name in z.namelist():
            if '/media/' in name and Path(name).suffix.lower() in IMAGES:
                try:
                    label_page(doc,item['path']+' / embedded image / '+name)
                    with image_pdf(z.read(name)) as images: add_visual(doc,images,item,name,tile=True)
                except Exception as exc: item['warnings'].append('Embedded image failed '+name+': '+str(exc))
        item['warnings'].append('Package XML retained for tables, notes, charts and relationships; not all elements have normalized semantic fields. Embedded objects/macros remain in originals.zip.')

def find_soffice(explicit):
    if explicit: return explicit
    for p in [shutil.which('soffice'),shutil.which('libreoffice'),r'C:\Program Files\LibreOffice\program\soffice.exe',r'C:\Program Files (x86)\LibreOffice\program\soffice.exe','/Applications/LibreOffice.app/Contents/MacOS/soffice']:
        if p and Path(p).is_file(): return str(p)
    return None

def office_pdf(path,work,exe,timeout):
    out=work/'converted'; out.mkdir()
    profile=work/'profile'; (profile/'user').mkdir(parents=True)
    # Highest macro security; refuse automatic link updates in Calc.
    (profile/'user'/'registrymodifications.xcu').write_text('''<?xml version="1.0" encoding="UTF-8"?><oor:items xmlns:oor="http://openoffice.org/2001/registry"><item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop></item><item oor:path="/org.openoffice.Office.Calc/Content/Update"><prop oor:name="Link" oor:op="fuse"><value>0</value></prop></item></oor:items>''',encoding='utf-8')
    ext=path.suffix.lower()
    filt='calc_pdf_Export' if ext in SHEETS else ('impress_pdf_Export' if ext in {'.ppt','.pptx','.pptm','.odp'} else 'writer_pdf_Export')
    opts={k:{'type':'boolean','value':'true'} for k in ['UseLosslessCompression','ExportNotes','ExportHiddenSlides','ExportNotesPages']}
    opts['ReduceImageResolution']={'type':'boolean','value':'false'}
    if ext in SHEETS: opts['SinglePageSheets']={'type':'boolean','value':'true'}
    proc=subprocess.run([exe,'-env:UserInstallation='+profile.as_uri(),'--headless','--nologo','--norestore','--convert-to','pdf:'+filt+':'+json.dumps(opts),'--outdir',str(out),str(path)],capture_output=True,timeout=timeout)
    result=out/(path.stem+'.pdf')
    if proc.returncode or not result.is_file(): raise RuntimeError('LibreOffice conversion failed: '+(proc.stdout+proc.stderr).decode(errors='replace'))
    return result

def inventory(root):
    files=[]; dirs=[]
    for base, ds, fs in os.walk(root,followlinks=False,onerror=lambda e: (_ for _ in ()).throw(e)):
        for name in ds+fs:
            p=Path(base)/name
            if p.is_symlink() or (hasattr(p,'is_junction') and p.is_junction()):
                raise RuntimeError('Links/junctions not supported; copy their real contents first: '+str(p))
        for name in ds: dirs.append(Path(base)/name)
        for name in fs:
            p=Path(base)/name
            if not p.is_file(): raise RuntimeError('Not a regular file: '+str(p))
            files.append(p)
    return sorted(files),sorted(dirs)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('input',type=Path); ap.add_argument('--out',required=True,type=Path)
    ap.add_argument('--soffice'); ap.add_argument('--allow-partial',action='store_true',help='Allow missing LibreOffice; explicitly record missing visuals')
    ap.add_argument('--ocr',action='store_true'); ap.add_argument('--ocr-lang',default='jpn+eng')
    ap.add_argument('--timeout',type=int,default=300)
    args=ap.parse_args(); root=args.input.resolve(); out=args.out.resolve()
    if not root.is_dir(): ap.error('Input must be a directory')
    if out==root or root in out.parents: ap.error('Output must be outside input')
    if out.exists(): ap.error('Output already exists; choose a new output folder')
    files,dirs=inventory(root)
    if not files: ap.error('Input folder has no files')
    exe=find_soffice(args.soffice)
    if any(p.suffix.lower() in OFFICE for p in files) and not exe and not args.allow_partial:
        ap.error('Install LibreOffice or pass --soffice PATH. --allow-partial explicitly permits missing Office visuals.')
    out.parent.mkdir(parents=True,exist_ok=True)
    manifest={'schema_version':'1.0','created_utc':datetime.now(timezone.utc).isoformat(), 'source_root':str(root), 'guarantee':'Original file bytes verified by SHA-256. Semantic extraction and rendering are best effort, not a completeness guarantee.', 'files':[], 'warnings':['External linked data is not collected. Filesystem ACLs/alternate data streams are not archived. Originals are never executed. Native rendering may differ across applications.','No OCR requested; image text remains visual only.' if not args.ocr else 'OCR is machine recognition and can contain errors.'], 'visual_review':'required_not_automatically_certified'}
    # Publish only after successful archive verification and PDF/JSON writing.
    with tempfile.TemporaryDirectory(prefix='bundle-',dir=out.parent) as temp:
        stage=Path(temp); products=stage/'products'; products.mkdir(); doc=fitz.open()
        with zipfile.ZipFile(products/'originals.zip','w',compression=zipfile.ZIP_DEFLATED,allowZip64=True) as archive:
            for d in dirs: archive.write(d,d.relative_to(root).as_posix()+'/')
            for idx,p in enumerate(files,1):
                item={'id':f'F{idx:06d}','path':p.relative_to(root).as_posix(),'warnings':[],'status':'processed_with_limitations'}
                print(f'[{idx}/{len(files)}] {item["path"]}',flush=True)
                work=stage/item['id']; work.mkdir(); snapshot=work/('source'+p.suffix.lower())
                before=p.stat(); shutil.copyfile(p,snapshot)
                with snapshot.open('rb') as f: item['sha256']=sha(f)
                with p.open('rb') as f: current=sha(f)
                after=p.stat()
                if current!=item['sha256'] or before.st_mtime_ns!=after.st_mtime_ns or before.st_size!=after.st_size: raise RuntimeError('Input changed during read: '+str(p))
                item['size_bytes']=snapshot.stat().st_size
                archive.write(snapshot,item['path'])
                item['pdf_start']=len(doc)+1; label_page(doc,item['id']+' / '+item['path'])
                ext=p.suffix.lower()
                try:
                    if ext in PACKAGES:
                        try: package_extract(snapshot,item,doc)
                        except Exception as exc:
                            item['status']='partial'; item['warnings'].append('Package extraction failed: '+str(exc))
                    if ext in OFFICE:
                        if exe:
                            converted=office_pdf(snapshot,work,exe,args.timeout)
                            with fitz.open(converted) as src: add_visual(doc,src,item,'LibreOffice rendering',tile=ext in SHEETS,ocr=args.ocr,lang=args.ocr_lang)
                            item['warnings'].append('LibreOffice rendering is not certified identical to Microsoft Office; recalculated values may differ from saved caches. Please review charts and fonts.')
                        else:
                            item['status']='partial'; item['warnings'].append('Office visual conversion skipped: LibreOffice missing')
                    elif ext=='.pdf':
                        with fitz.open(snapshot) as src:
                            if src.needs_pass: raise ValueError('Encrypted PDF requires a decrypted local copy')
                            item['pdf_metadata']=src.metadata
                            item['pdf_attachments']=src.embfile_names()
                            item['annotations']=[{'source_page':i+1,'annotations':[a.info for a in pg.annots()]} for i,pg in enumerate(src)]
                            add_visual(doc,src,item,'Original PDF',ocr=args.ocr,lang=args.ocr_lang)
                    elif ext in IMAGES:
                        with image_pdf(snapshot.read_bytes()) as src: add_visual(doc,src,item,'Image frames',tile=True,ocr=args.ocr,lang=args.ocr_lang)
                    elif ext in TEXT:
                        item['text'],item['encoding']=decode(snapshot.read_bytes())
                        item['text_pdf_pages']=add_text(doc,[item['text']],item['id'])
                    else:
                        item['status']='archive_only'; item['warnings'].append('Unsupported format: only original bytes preserved; archive contents are not recursively converted')
                except Exception as exc:
                    item['status']='partial'; item['warnings'].append(type(exc).__name__+': '+str(exc))
                if item['warnings']: add_text(doc,item['warnings'],item['id']+' / WARNINGS')
                item['pdf_end']=len(doc); manifest['files'].append(item)
                shutil.rmtree(work)
        with zipfile.ZipFile(products/'originals.zip') as archive:
            for item in manifest['files']:
                with archive.open(item['path']) as f:
                    if sha(f)!=item['sha256']: raise RuntimeError('Archive verification failed: '+item['path'])
        manifest['archive_verified']=True
        manifest['file_count']=len(files); manifest['pdf_page_count']=len(doc)
        manifest['archive_only_count']=sum(x['status']=='archive_only' for x in manifest['files'])
        manifest['partial_count']=sum(x['status']=='partial' for x in manifest['files'])
        doc.save(products/'visuals.pdf',deflate=True,garbage=3); doc.close()
        with fitz.open(products/'visuals.pdf') as checked:
            if len(checked)!=manifest['pdf_page_count']: raise RuntimeError('PDF page count mismatch')
        (products/'content.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
        # Atomic directory publication, refuses overwrites.
        products.rename(out)
    print('Saved:',out)
    print('Original bytes verified. Partial:',manifest['partial_count'],'Archive only:',manifest['archive_only_count'])
    print('Review content.json warnings and visuals.pdf. Full semantic completeness is NOT certified.')
    return 2 if manifest['partial_count'] or manifest['archive_only_count'] else 0

if __name__=='__main__':
    try: sys.exit(main())
    except KeyboardInterrupt: print('Cancelled; no final bundle published.',file=sys.stderr); sys.exit(130)
    except Exception as exc: print('FAILED: '+str(exc),file=sys.stderr); sys.exit(1)
