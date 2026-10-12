from pathlib import Path
import zipfile
from PIL import Image, ImageDraw
p=Path('tests/input')
p.mkdir(parents=True,exist_ok=True)
(p/'日本語.txt').write_text('日本語の全文確認\n'+'長い文章を省略せずに保持する。'*200,encoding='utf-8')
(p/'unknown.bin').write_bytes(bytes(range(256)))
im=Image.new('RGB',(1600,1000),'white'); d=ImageDraw.Draw(im); d.rectangle((10,10,1590,990),outline='blue',width=5); d.text((100,100),'IMAGE FULL BORDER',fill='black'); im.save(p/'image.png')
parts={
'[Content_Types].xml':'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
'_rels/.rels':'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
'xl/workbook.xml':'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Wide" sheetId="1" r:id="rId1"/><sheet name="Hidden" sheetId="2" state="hidden" r:id="rId2"/></sheets><definedNames><definedName name="_xlnm.Print_Area" localSheetId="0">Wide!$A$1:$A$1</definedName></definedNames></workbook>',
'xl/_rels/workbook.xml.rels':'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/></Relationships>',
'xl/worksheets/sheet1.xml':'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>'+('長文セルの情報保持。'*500)+'END_MARKER</t></is></c><c r="Z1" t="inlineStr"><is><t>FAR_RIGHT_MARKER</t></is></c></row><row r="2"><c r="A2"><v>12</v></c><c r="B2"><f>A2*2</f><v>24</v></c></row></sheetData></worksheet>',
'xl/worksheets/sheet2.xml':'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>HIDDEN_MARKER</t></is></c></row></sheetData></worksheet>'}
with zipfile.ZipFile(p/'wide.xlsx','w') as z:
 for name,body in parts.items(): z.writestr(name,body)
