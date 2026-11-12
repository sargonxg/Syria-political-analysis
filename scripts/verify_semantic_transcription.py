#!/usr/bin/env python3
"""Verify the normalized semantic excerpt against the pinned primary PDF."""
from pathlib import Path
import argparse,hashlib,json,re,subprocess
parser=argparse.ArgumentParser()
parser.add_argument('--pdf',required=True,type=Path)
args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
model=json.loads((root/'data/semantic-documents/unsc-2254.json').read_text(encoding='utf-8'))
raw=args.pdf.read_bytes()
if hashlib.sha256(raw).hexdigest()!=model['document']['primary_pdf_sha256']:
 raise SystemExit('Primary PDF differs from the pinned source. No transcription accepted.')
result=subprocess.run(['pdftotext','-layout',str(args.pdf),'-'],check=True,capture_output=True)
text=result.stdout.decode('utf-8')
clean=re.sub(r'(?m)^.*(?:S/RES/2254 \(2015\)|15-22539|^[ \t]*[1-4]/4).*$','',text)
positions=list(re.finditer(r'(?m)^\s{5,}(\d{1,2})\.\s+',clean))
paragraphs={int(m.group(1)):re.sub(r'\s+',' ',clean[m.end():positions[i+1].start() if i+1<len(positions) else len(clean)]).strip() for i,m in enumerate(positions)}
retained='\n\n'.join(str(n)+'. '+paragraphs[n] for n in [2,4,5,8])
if retained!=model['document']['text']:
 raise SystemExit('Normalized transcription differs. Review the PDF/text-tool output; no automatic replacement.')
if hashlib.sha256(retained.encode()).hexdigest()!=model['document']['text_sha256']:
 raise SystemExit('Retained source text checksum differs.')
for span in model['spans']:
 actual=retained.encode('utf-16-le')[span['start']*2:span['end']*2].decode('utf-16-le')
 if actual!=span['quote']:
  raise SystemExit('Source span differs: '+span['id'])
print(json.dumps({'primary_pdf_sha256':model['document']['primary_pdf_sha256'],'normalized_text_sha256':model['document']['text_sha256'],'paragraphs':[2,4,5,8],'exact_span_checks':len(model['spans']),'result':'verified'}))

