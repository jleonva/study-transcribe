"""Portable project, source preservation and offline OCR integration smoke test."""
import argparse,hashlib,json,subprocess,sys,tempfile
from pathlib import Path
import pymupdf as fitz

ap=argparse.ArgumentParser();ap.add_argument('--model-root',required=True);a=ap.parse_args()
repo=Path(__file__).resolve().parents[1]
def run(script,*args):return subprocess.run([sys.executable,str(repo/'scripts'/script),*map(str,args)],check=True)
with tempfile.TemporaryDirectory(prefix='local-math-test-') as temp:
    root=Path(temp);pdf=root/'fixture.pdf';doc=fitz.open()
    doc.new_page().insert_text((72,100),'First page: excluded')
    p=doc.new_page();p.insert_text((72,100),'Test chapter',fontsize=22);p.insert_text((72,150),'A mathematical expression:',fontsize=16);p.insert_text((200,220),'x + y = 2',fontsize=20);doc.save(pdf)
    before=hashlib.sha256(pdf.read_bytes()).hexdigest();project=root/'project'
    run('new_math_project.py',pdf,'--pages','2-2','--output',project,'--id','custom_book','--model-root',a.model_root)
    cfg=project/'pilot.json';data=json.loads(cfg.read_text());assert data['books'][0]['source_start']==2
    repeat=subprocess.run([sys.executable,str(repo/'scripts/new_math_project.py'),str(pdf),'--pages','2-2','--output',str(project)],capture_output=True)
    assert repeat.returncode!=0,'must not overwrite an existing project'
    run('local_math_batch.py','--config',cfg)
    result=project/'custom_book/raw/pix2text/page0001/result.json';stamp=result.stat().st_mtime_ns
    assert json.loads(result.read_text(encoding='utf-8'))['blocks']
    run('local_math_batch.py','--config',cfg);assert result.stat().st_mtime_ns==stamp,'resume should skip completed page'
    run('build_math_review.py','--config',cfg);run('audit_math_pilot.py','--config',cfg,'--verify-originals')
    report=json.loads((project/'audit.json').read_text());assert report['all_chapters_processed'];assert report['source_sample_slots']==0
    page=(project/'review.html').read_text(encoding='utf-8');assert '<option value="custom_book">' in page;assert '<option value="detected" selected>' in page
    assert hashlib.sha256(pdf.read_bytes()).hexdigest()==before
print('PASS: custom project, range extraction, overwrite refusal, offline OCR, resume, generic review, source preservation')
