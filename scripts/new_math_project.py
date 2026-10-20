"""Create an isolated OCR project from inclusive one-based PDF pages."""
import argparse, hashlib, json
from pathlib import Path
import pymupdf as fitz

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('pdf',type=Path);ap.add_argument('--pages',required=True)
    ap.add_argument('--output',type=Path,required=True);ap.add_argument('--id',default='book')
    ap.add_argument('--title',default='');ap.add_argument('--model-root',type=Path,default=Path.home()/'.cache'/'study-transcribe')
    a=ap.parse_args()
    if not a.id.replace('-','').replace('_','').isalnum():ap.error('Invalid book ID')
    parts=a.pages.split('-');start=int(parts[0]);end=int(parts[-1]);src=a.pdf.resolve();out=a.output.resolve()
    doc=fitz.open(src)
    if not 1<=start<=end<=len(doc):ap.error('Invalid page range')
    if (out/'pilot.json').exists() or (out/a.id).exists():ap.error('Project exists; resume it instead of overwriting')
    target=out/a.id;target.mkdir(parents=True)
    sub=fitz.open();sub.insert_pdf(doc,from_page=start-1,to_page=end-1);sub.save(target/'source-chapter.pdf')
    with src.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
    book={'id':a.id,'title':a.title or src.stem,'source_path':str(src),'source_sha256':digest,'pdf':str(target/'source-chapter.pdf'),'source_start':start,'source_end':end,'pages':end-start+1,'output':str(target),'source_type':'unclassified'}
    config={'output':str(out),'model_root':str(a.model_root.resolve()),'model_budget_bytes':5_000_000_000,'threads':6,'dpi':200,'books':[book]}
    (target/'source-manifest.json').write_text(json.dumps(book,indent=2),encoding='utf-8')
    (out/'pilot.json').write_text(json.dumps(config,indent=2),encoding='utf-8');print(out/'pilot.json')
if __name__=='__main__':main()
