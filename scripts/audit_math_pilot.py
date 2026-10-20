"""Mechanical checks only: completeness/provenance, not mathematical accuracy."""
import argparse,hashlib,json,re,subprocess,sys
from pathlib import Path

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--config',required=True);ap.add_argument('--verify-originals',action='store_true');a=ap.parse_args()
    cfg=json.loads(Path(a.config).read_text(encoding='utf-8-sig'));out=Path(cfg['output']);report={'review_status':'pending_user','hosted_ocr_api_calls':0,'accuracy':None,'books':[]}
    for b in cfg['books']:
        folder=Path(b['output']);d=json.loads((folder/'chapter.json').read_text(encoding='utf-8'));good=[p for p in d['pages'] if 'blocks' in p]
        formulas=[e for p in good for e in p['blocks'] if e['type']=='FORMULA']
        inline=[m for p in good for e in p['blocks'] for m in (e.get('meta') or []) if isinstance(m,dict) and m.get('type')=='embedding']
        md=(folder/'chapter.md').read_text(encoding='utf-8');missing_images=[p for p in re.findall(r'!\[[^\]]*\]\(([^)]+)\)',md) if not (folder/p).is_file()]
        row={'id':b['id'],'expected_pages':b['pages'],'processed_pages':len(good),'display_formula_blocks':len(formulas),'inline_formula_detections':len(inline),'page_processing_seconds':round(sum(p['seconds'] for p in good),2),'excerpt_sha256':sha(b['pdf']),'missing_image_references':missing_images,'empty_pages':[p['source_page'] for p in good if not p['blocks']]}
        if a.verify_originals:row['original_unchanged']=sha(b['source_path'])==b['source_sha256']
        comparison=folder/'raw'/'docling'/'run.json'
        if comparison.exists():row['docling_comparison']=json.loads(comparison.read_text(encoding='utf-8'))
        report['books'].append(row)
    model_root=Path(cfg['model_root']);models=[]
    for f in model_root.rglob('*'):
        if f.suffix in {'.onnx','.pt','.safetensors','.bin'} and f.is_file():models.append({'path':str(f.relative_to(model_root)),'bytes':f.stat().st_size,'sha256':sha(f)})
    report['model_weight_bytes']=sum(m['bytes'] for m in models);report['model_directory_bytes']=sum(f.stat().st_size for f in model_root.rglob('*') if f.is_file());report['within_model_budget']=report['model_directory_bytes']<=cfg['model_budget_bytes']
    samples=json.loads((out/'sample-equations.json').read_text(encoding='utf-8')) if (out/'sample-equations.json').exists() else []
    report['source_sample_slots']=len(samples)
    report['source_sample_matched_slots']=sum(bool(s['matched_blocks']) for s in samples)
    if (out/'human-review.json').exists():
        report['human_review']=json.loads((out/'human-review.json').read_text(encoding='utf-8'))
        report['review_status']='user_accepted_global_declaration'
    report['all_chapters_processed']=all(b['processed_pages']==b['expected_pages'] for b in report['books'])
    report['notes']=['Formula counts are detections, not a reference count or recall metric.','No automatic or human mathematical accuracy score has been assigned.','The coordinator consumes AI tokens; OCR inference is local.','CPU execution at 200 dpi; scanned source fidelity remains pending review.','Empty source pages and figures need human review; figure labels are not guaranteed transcribed.']
    if 'human_review' in report:
        report['notes'][3]='User globally accepted the delivered equations; no per-equation form or quantitative accuracy score was provided.'
    (out/'model-manifest.json').write_text(json.dumps(models,indent=2),encoding='utf-8')
    (out/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'environment-pix2text.txt').write_text(subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True))
if __name__=='__main__':main()
