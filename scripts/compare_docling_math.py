"""Compare three source pages with local Docling formula enrichment."""
import argparse,json,os,time,socket
from pathlib import Path

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--config',required=True);ap.add_argument('--prepare',action='store_true');a=ap.parse_args()
    cfg=json.loads(Path(a.config).read_text(encoding='utf-8-sig'));root=Path(cfg['model_root']);art=root/'docling';art.mkdir(exist_ok=True)
    os.environ['HF_HOME']=str(root/'docling-hf');os.environ['HF_HUB_DISABLE_TELEMETRY']='1';os.environ['OMP_NUM_THREADS']='4'
    if a.prepare:
        from huggingface_hub import HfApi,snapshot_download
        manifest=[]
        for repo in ['docling-project/docling-layout-heron','docling-project/CodeFormulaV2']:
            info=HfApi().model_info(repo,files_metadata=True);size=sum(f.size or 0 for f in info.siblings)
            used=sum(f.stat().st_size for f in root.rglob('*') if f.is_file())
            if used+size>cfg['model_budget_bytes']:raise RuntimeError('Download would exceed approved budget')
            print(repo,info.sha,size,flush=True)
            snapshot_download(repo,revision=info.sha,local_dir=art/repo.replace('/','--'))
            manifest.append({'repo':repo,'revision':info.sha,'bytes':size})
        from docling.models.stages.ocr.rapid_ocr_model import RapidOcrModel
        RapidOcrModel.download_models('onnxruntime',local_dir=art/RapidOcrModel._model_repo_folder,lang='en',progress=True)
        (art/'downloads.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8');return
    os.environ['HF_HUB_OFFLINE']='1'
    import torch
    torch.set_num_threads(4);torch.set_num_interop_threads(1)
    from docling.document_converter import DocumentConverter,PdfFormatOption
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions,RapidOcrOptions
    from docling.datamodel.accelerator_options import AcceleratorOptions,AcceleratorDevice
    opt=PdfPipelineOptions(artifacts_path=art,do_formula_enrichment=True,do_table_structure=False,do_ocr=True,enable_remote_services=False,document_timeout=600)
    opt.ocr_options=RapidOcrOptions(lang=['en'],backend='onnxruntime',force_full_page_ocr=True)
    opt.accelerator_options=AcceleratorOptions(num_threads=4,device=AcceleratorDevice.CPU)
    conv=DocumentConverter(format_options={InputFormat.PDF:PdfFormatOption(pipeline_options=opt)})
    def denied(*args,**kwargs):raise ConnectionError('Network disabled during inference')
    socket.socket.connect=denied;socket.create_connection=denied
    # One math-rich page per book, also processed by the main pipeline.
    for book,index in zip(cfg['books'],[6,2,3]):
        dest=Path(book['output'])/'raw'/'docling';dest.mkdir(parents=True,exist_ok=True)
        print('START',book['id'],index,flush=True);start=time.perf_counter()
        result=conv.convert(book['pdf'],page_range=(index,index))
        (dest/'page.md').write_text(result.document.export_to_markdown(),encoding='utf-8')
        (dest/'page.json').write_text(json.dumps(result.document.export_to_dict(),ensure_ascii=False,indent=2),encoding='utf-8')
        (dest/'run.json').write_text(json.dumps({'chapter_page':index,'source_page':book['source_start']+index-1,'seconds':time.perf_counter()-start,'status':str(result.status),'review_status':'pending'},indent=2),encoding='utf-8')
        print('DONE',book['id'],time.perf_counter()-start,flush=True)
if __name__=='__main__':main()
