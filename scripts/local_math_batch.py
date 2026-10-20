"""Local-only, resumable mathematical chapter OCR. No inference API."""
import argparse, json, os, time, socket, threading
from pathlib import Path

def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=lambda x: x.tolist() if hasattr(x,'tolist') else str(x)), encoding='utf-8')

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--config', required=True)
    ap.add_argument('--prepare', action='store_true')
    ap.add_argument('--book')
    ap.add_argument('--limit', type=int)
    ap.add_argument('--page-timeout', type=int, default=600)
    ap.add_argument('--max-new-tokens', type=int, default=1024)
    a=ap.parse_args(); cfg=json.loads(Path(a.config).read_text(encoding='utf-8-sig'))
    root=Path(cfg['model_root']); root.mkdir(parents=True,exist_ok=True)
    for k,v in {'HF_HOME':str(root/'hf'),'HF_HUB_DISABLE_TELEMETRY':'1','OMP_NUM_THREADS':str(cfg['threads']),'MKL_NUM_THREADS':str(cfg['threads']),'YOLO_OFFLINE':'true'}.items(): os.environ[k]=v
    if not a.prepare: os.environ['HF_HUB_OFFLINE']='1'
    import torch
    torch.set_num_threads(cfg['threads']); torch.set_num_interop_threads(1)
    import onnxruntime as ort
    so=ort.SessionOptions(); so.intra_op_num_threads=cfg['threads']; so.inter_op_num_threads=1
    from pix2text import Pix2Text
    # Avoid the package's slow mirror-first default; use the official Hub.
    from cnstd.hf_downloader import HuggingFaceDownloader as CDownloader
    from pix2text.hf_downloader import HuggingFaceDownloader as PDownloader
    for downloader in (CDownloader,PDownloader):
        downloader._normalize_mirror_urls=staticmethod(lambda _: ['https://huggingface.co'])
    def denied(*args,**kwargs): raise ConnectionError('Network disabled during inference; run --prepare first if models are missing')
    if not a.prepare:
        socket.socket.connect=denied; socket.create_connection=denied
    print('Initializing local models',flush=True)
    p=Pix2Text(total_configs={'layout':{'root':str(root/'layout')},'text_formula':{'languages':('en',),'mfd':{'root':str(root/'mfd')},'formula':{'root':str(root/'mfr'),'more_model_configs':{'session_options':so}},'text':{'rec_root':str(root/'text-rec'),'det_root':str(root/'text-det')}}}, enable_table=False,device='cpu')
    p.text_formula_ocr.spellchecker=None
    size=sum(f.stat().st_size for f in root.rglob('*') if f.is_file())
    if size>cfg['model_budget_bytes']: raise RuntimeError('Model budget exceeded')
    dump(root/'inventory.json',{'bytes':size,'files':[{'path':str(f.relative_to(root)),'bytes':f.stat().st_size} for f in root.rglob('*') if f.is_file()]})
    print('Models ready; bytes='+str(size),flush=True)
    if a.prepare: return
    import fitz
    from PIL import Image
    for book in cfg['books']:
        if a.book and book['id']!=a.book: continue
        out=Path(book['output']); doc=fitz.open(book['pdf'])
        for i,page in enumerate(doc):
            if a.limit and i>=a.limit: break
            dest=out/'raw'/'pix2text'/f'page{i+1:04d}'; dest.mkdir(parents=True,exist_ok=True)
            if (dest/'result.json').exists(): continue
            print(f"START {book['id']} {i+1}/{len(doc)}",flush=True); start=time.perf_counter()
            def timed_out():
                dump(dest/'error.json',{'status':'timeout','seconds':a.page_timeout,'review_status':'pending'})
                print('Page timeout; completed pages are preserved. Resume after investigating this page.',flush=True)
                os._exit(124)
            timer=threading.Timer(a.page_timeout,timed_out);timer.daemon=True;timer.start()
            pix=page.get_pixmap(dpi=cfg['dpi']); img=Image.frombytes('RGB',[pix.width,pix.height],pix.samples)
            img.save(dest/'source.jpg',quality=85)
            result=p.recognize_page(img,page_number=i,page_id=f'{book["id"]}-{i+1}',resized_shape=1024,mfr_batch_size=1,formula_rec_kwargs={'rec_config':{'max_new_tokens':a.max_new_tokens}})
            md=result.to_markdown(str(dest))
            blocks=[{'id':e.id,'type':e.type.name,'bbox_pixels':e.box,'text':e.text,'meta':e.meta,'score':e.score,'review_status':'pending'} for e in result.elements]
            dump(dest/'result.json',{'source_page':book['source_start']+i,'chapter_page':i+1,'dpi':cfg['dpi'],'engine':'pix2text-1.1.7','seconds':time.perf_counter()-start,'blocks':blocks,'native_text':page.get_text(),'review_status':'pending'})
            timer.cancel()
            print(f"DONE {book['id']} {i+1}: {time.perf_counter()-start:.1f}s {len(blocks)} blocks",flush=True)

if __name__=='__main__': main()
