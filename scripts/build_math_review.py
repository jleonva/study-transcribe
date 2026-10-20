"""Assemble uncorrected local OCR and an offline human-review panel."""
import base64, html, json, re
from pathlib import Path
import argparse

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--config',required=True); a=ap.parse_args()
    cfg=json.loads(Path(a.config).read_text(encoding='utf-8-sig')); root=Path(cfg['output']); cards=[]; summary=[]; chapters=[]
    human=json.loads((root/'human-review.json').read_text(encoding='utf-8')) if (root/'human-review.json').exists() else None
    for b in cfg['books']:
        out=Path(b['output']); pages=[]; md=['# '+b['title'],'\n> OCR local sin corrección. '+('Ecuaciones aceptadas por declaración global del usuario; sin evaluación individual registrada.' if human else 'Pendiente de revisión humana.')+'\n']
        for i in range(1,b['pages']+1):
            d=out/'raw'/'pix2text'/f'page{i:04d}'
            if not (d/'result.json').exists():
                pages.append({'chapter_page':i,'source_page':b['source_start']+i-1,'status':'missing'}); continue
            p=json.loads((d/'result.json').read_text(encoding='utf-8')); pages.append(p)
            text=(d/'output.md').read_text(encoding='utf-8') if (d/'output.md').exists() else ''
            text=text.replace('figures/',f'raw/pix2text/page{i:04d}/figures/')
            text=text.replace('figures\\',f'raw/pix2text/page{i:04d}/figures/')
            md.extend([f'\n<!-- source PDF page {p["source_page"]} -->\n',text])
            for j,e in enumerate(p['blocks']):
                if e['type']=='FORMULA':
                    from PIL import Image
                    import io
                    im=Image.open(d/'source.jpg'); x0,y0,x1,y1=e['bbox_pixels']; im=im.crop((max(0,x0-15),max(0,y0-15),min(im.width,x1+15),min(im.height,y1+15)))
                    buf=io.BytesIO(); im.save(buf,format='JPEG',quality=88)
                    cards.append({'id':f'{b["id"]}-{i}-{j}','book':b['id'],'page':p['source_page'],'latex':e['text'],'image':base64.b64encode(buf.getvalue()).decode(),'status':'pending'})
        complete=sum('blocks' in p for p in pages)
        data={'book':b,'engine':'pix2text-1.1.7','review_status':'pending','completed_pages':complete,'expected_pages':b['pages'],'pages':pages}
        if human:
            data['human_review']=human
            data['review_status']='user_accepted_global_declaration'
        (out/'chapter.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        (out/'chapter.md').write_text('\n'.join(md),encoding='utf-8')
        chapter='\n'.join(md)
        def inline_image(m):
            path=out/m.group(1)
            return '![](data:image/jpeg;base64,'+base64.b64encode(path.read_bytes()).decode()+')' if path.is_file() else m.group(0)
        chapter=re.sub(r'!\[[^\]]*\]\(([^)]+)\)',inline_image,chapter)
        chapters.append({'title':b['id']+' — '+b['title'],'markdown':chapter})
        comp=out/'raw'/'docling'/'page.md'
        if comp.exists():chapters.append({'title':b['id']+' — página de comparación Docling','markdown':comp.read_text(encoding='utf-8')})
        summary.append(f'{b["id"]}: {complete}/{b["pages"]} páginas')
    sample_file=root/'sample-source.json'
    if sample_file.exists():
        import fitz, io
        from PIL import Image
        samples=[]
        for spec in json.loads(sample_file.read_text(encoding='utf-8')):
            b=next(b for b in cfg['books'] if b['id']==spec['book']); i=spec['page']-b['source_start']+1
            d=Path(b['output'])/'raw'/'pix2text'/f'page{i:04d}'
            page=fitz.open(b['pdf'])[i-1]; y=spec['y_points']; radius=spec.get('radius',20)
            pix=page.get_pixmap(dpi=200,clip=fitz.Rect(30,y-radius,page.rect.width-8,y+radius))
            buf=io.BytesIO(); Image.frombytes('RGB',[pix.width,pix.height],pix.samples).save(buf,format='JPEG',quality=90)
            found=[]
            if (d/'result.json').exists():
                p=json.loads((d/'result.json').read_text(encoding='utf-8'))
                for e in p['blocks']:
                    box=e['bbox_pixels']; ey0,ey1=box[1]*72/p['dpi'],box[3]*72/p['dpi']
                    if e['type']=='FORMULA' and ey0-9<=y<=ey1+9: found.append(e)
                if len(found)>1:
                    found=[min(found,key=lambda e:abs((e['bbox_pixels'][1]+e['bbox_pixels'][3])*36/p['dpi']-y))]
            samples.append({'id':'source-'+spec['label'],'book':spec['book'],'page':spec['page'],'latex':'\n'.join(e['text'] for e in found) or '[Sin fórmula aislada asociada: revisar omisión o clasificación]','image':base64.b64encode(buf.getvalue()).decode(),'status':'pending','source_label':spec['label'],'source_selected':True,'matched_blocks':[e['id'] for e in found]})
            comp=Path(b['output'])/'raw'/'docling'
            if (comp/'run.json').exists() and json.loads((comp/'run.json').read_text(encoding='utf-8'))['source_page']==spec['page']:
                doc=json.loads((comp/'page.json').read_text(encoding='utf-8'));candidates=[]
                for e in doc.get('texts',[]):
                    if e.get('label')!='formula':continue
                    for prov in e.get('prov',[]):
                        box=prov['bbox'];cy=(box['t']+box['b'])/2
                        if box.get('coord_origin')=='BOTTOMLEFT':cy=page.rect.height-cy
                        if abs(cy-y)<30:candidates.append((abs(cy-y),e.get('text','')))
                samples[-1]['docling_latex']=min(candidates)[1] if candidates else '[Sin fórmula asociada en Docling]'
        (root/'sample-equations.json').write_text(json.dumps(samples,ensure_ascii=False,indent=2),encoding='utf-8')
        cards=samples+cards
    payload=json.dumps(cards,ensure_ascii=False).replace('<','\\u003c')
    template='''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Revisión del OCR matemático</title>
<style>body{font:17px system-ui;background:#f3f4f8;color:#182332;max-width:1100px;margin:auto;padding:25px}button,select,input,textarea{font:inherit;padding:8px;margin:5px}article{background:white;padding:20px;margin:20px 0;border-radius:12px}img{max-width:100%;height:auto}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#eef1f5;padding:15px}textarea{width:90%}.render{overflow:auto;padding:14px}header{position:sticky;top:0;background:#f3f4f8;padding:10px;z-index:1}</style>
<h1>Revisión del OCR matemático</h1><p>__SUMMARY__</p><p>Salida automática sin corregir. La precisión todavía no está evaluada. Esta lista incluye las fórmulas aisladas detectadas, en orden de página; puede haber ecuaciones omitidas. Para revisar omisiones, consulta también los PDF originales y los capítulos completos.</p>
<p>__LINKS__</p><header><label>Libro <select id="book"><option value="">Todos</option><option>shreve</option><option>boyd</option><option>williams</option></select></label><label>Estado <select id="filter"><option value="">Todos</option><option value="pending">Pendiente</option><option value="correct">Correcta</option><option value="symbol_error">Error de símbolos</option><option value="incomplete">Incompleta</option><option value="missing">Omitida</option></select></label><input id="search" aria-label="Buscar LaTeX" placeholder="Buscar LaTeX"><button id="export">Exportar evaluación JSON</button><p id="progress"></p></header><main id="cards"></main>
<script>const data=__DATA__;const key='math-pilot-review-v1';let reviews={};try{reviews=JSON.parse(localStorage.getItem(key)||'{}')}catch{}const $=id=>document.getElementById(id);const labels={pending:'Pendiente',correct:'Correcta',symbol_error:'Error de símbolos',incomplete:'Incompleta',missing:'Omitida'};
function save(){try{localStorage.setItem(key,JSON.stringify(reviews))}catch{}updateProgress()}
function updateProgress(){const n=data.filter(x=>(reviews[x.id]?.status||'pending')!=='pending').length;$('progress').textContent=`${n} / ${data.length} fórmulas detectadas revisadas. Precisión: pendiente de tu evaluación.`}
function draw(){$('cards').replaceChildren();for(const x of data){const r=reviews[x.id]||{status:'pending',notes:''};if($('book').value&&x.book!==$('book').value||$('filter').value&&r.status!==$('filter').value||!x.latex.toLowerCase().includes($('search').value.toLowerCase()))continue;const a=document.createElement('article');const h=document.createElement('h2');h.textContent=`${x.book} · página PDF ${x.page} · ${x.id}`;a.append(h);const img=new Image();img.src='data:image/jpeg;base64,'+x.image;img.alt='Recorte del PDF original';a.append(img);const render=document.createElement('div');render.className='render';if(window.katex){try{katex.render(x.latex.replace(/^\\$\\$|\\$\\$$/g,''),render,{throwOnError:false,displayMode:true})}catch{render.textContent='No se pudo representar esta fórmula'}}else render.textContent='LaTeX sin representación visual';a.append(render);const pre=document.createElement('pre');pre.textContent=x.latex;a.append(pre);const s=document.createElement('select');s.setAttribute('aria-label','Evaluación '+x.id);for(const [v,t] of Object.entries(labels)){const o=new Option(t,v);s.add(o)}s.value=r.status;s.onchange=()=>{reviews[x.id]={status:s.value,notes:n.value};save()};const n=document.createElement('textarea');n.placeholder='Notas de revisión';n.setAttribute('aria-label','Notas '+x.id);n.value=r.notes;n.oninput=()=>{reviews[x.id]={status:s.value,notes:n.value};save()};a.append(s,n);$('cards').append(a)}updateProgress()}
for(const id of ['book','filter','search'])$(id).addEventListener('input',draw);$('export').onclick=()=>{const blob=new Blob([JSON.stringify({schema:1,exported_at:new Date().toISOString(),reviews},null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='math-pilot-review.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};draw();</script></html>'''
    links=' | '.join(f'<a href="{b["id"]}/chapter.md">{b["id"]} Markdown</a> · <a href="{b["id"]}/chapter.json">JSON</a> · <a href="{b["id"]}/source-chapter.pdf">PDF</a>' for b in cfg['books'])
    template=template.replace('__SUMMARY__',html.escape(' · '.join(summary))).replace('__LINKS__',links).replace('__DATA__',payload)
    template=template.replace('<header><label>Libro', '<header><label>Muestra <select id="scope"><option value="sample">15 ecuaciones consecutivas del original</option><option value="detected">Todas las fórmulas detectadas</option></select></label><label>Libro')
    template=template.replace("const r=reviews[x.id]||{status:'pending',notes:''};", "const r=reviews[x.id]||{status:'pending',notes:''};if(($('scope').value==='sample')!==!!x.source_selected)continue;")
    template=template.replace("['book','filter','search']", "['book','filter','search','scope']")
    template=template.replace('${x.book} · página PDF ${x.page} · ${x.id}', '${x.source_label ? "Ecuación "+x.source_label+" · " : ""}${x.book} · página PDF ${x.page} · ${x.id}')
    template=template.replace('Esta lista incluye las fórmulas aisladas detectadas, en orden de página; puede haber ecuaciones omitidas.', 'La vista inicial muestra 15 ecuaciones consecutivas elegidas en el original, antes de evaluar el OCR. Una asociación ausente queda visible. La vista alternativa contiene todas las fórmulas aisladas detectadas; puede haber omisiones. Algunas fórmulas vecinas pueden compartir un bloque OCR.')
    template=template.replace('fórmulas detectadas revisadas', 'entradas revisadas (muestra y detecciones)')
    template=template.replace("a.append(pre);const s=", "a.append(pre);if(x.docling_latex!==undefined){const h3=document.createElement('h3');h3.textContent='Comparación: Docling (revisión de esta salida en notas)';const r2=document.createElement('div');r2.className='render';if(window.katex)katex.render(x.docling_latex,r2,{throwOnError:false,displayMode:true});const p2=document.createElement('pre');p2.textContent=x.docling_latex;a.append(h3,r2,p2)}const s=")
    template=template.replace('Salida automática sin corregir.', 'Motor principal: Pix2Text 1.1.7. Salida automática sin corregir.')
    book_options='<option value="">Todos</option>'+''.join('<option value="'+html.escape(b['id'],quote=True)+'">'+html.escape(b['id'])+'</option>' for b in cfg['books'])
    template=re.sub(r'(<select id="book">).*?(</select>)',lambda m:m[1]+book_options+m[2],template)
    count=sum(bool(c.get('source_selected')) for c in cards)
    template=template.replace('15 ecuaciones consecutivas',str(count)+' ecuaciones seleccionadas del original')
    if not count:template=template.replace('<option value="detected">','<option value="detected" selected>')
    if human:
        notice='<aside><strong>Validación del usuario: ecuaciones aceptadas.</strong><p>'+html.escape(human['statement'])+'</p><p>'+html.escape(human['date'])+' · Declaración global en conversación; formulario individual sin rellenar. No es una medición estadística ni una garantía para futuras extracciones.</p></aside>'
        template=template.replace('<header>',notice+'<header>',1)
        template=template.replace('La precisión todavía no está evaluada.','El usuario ha aceptado globalmente las ecuaciones del piloto.')
        template=template.replace('Precisión: pendiente de tu evaluación.','Validación global recibida; formulario individual opcional.')
        template=template.replace('Precisión matemática pendiente de tu revisión.','Ecuaciones aceptadas por declaración global del usuario; sin puntuación estadística.')
    audit_file=root/'audit.json'
    if audit_file.exists():
        audit=json.loads(audit_file.read_text(encoding='utf-8'))
        rows=''.join('<tr><td>'+html.escape(b['id'])+'</td><td>'+str(b['processed_pages'])+'/'+str(b['expected_pages'])+'</td><td>'+str(b['display_formula_blocks'])+'</td><td>'+str(round(b['page_processing_seconds']/60,1))+'</td></tr>' for b in audit['books'])
        info='<details><summary>Resultados técnicos y límites</summary><p>Inferencia OCR local en CPU. Modelos: '+str(round(audit['model_directory_bytes']/1e9,2))+' GB. Los recuentos son detecciones, no una medida de exactitud.</p><table><tr><th>Libro</th><th>Páginas</th><th>Bloques de fórmulas</th><th>Minutos OCR</th></tr>'+rows+'</table><p><a href="audit.json">Informe de comprobaciones JSON</a></p></details>'
        template=template.replace('<header>',info+'<header>',1)
    vendor=root/'vendor'
    if (vendor/'katex.min.js').exists():
        css=(vendor/'katex.min.css').read_text(encoding='utf-8')
        for font in (vendor/'fonts').glob('*'):
            css=css.replace('fonts/'+font.name,'data:font/'+font.suffix.lstrip('.')+';base64,'+base64.b64encode(font.read_bytes()).decode())
        template=template.replace('<h1>','<style>'+css+'</style><script>'+(vendor/'katex.min.js').read_text(encoding='utf-8')+'</script><h1>',1)
    if (vendor/'markdown-it.min.js').exists():
        scripts=''.join('<script>'+ (vendor/f).read_text(encoding='utf-8')+'</script>' for f in ['markdown-it.min.js','auto-render.min.js'])
        reader='<section id="chapters"><h2>Leer los capítulos completos</h2><p>Texto y fórmulas tal como los produjo el OCR. Abre un capítulo para leerlo.</p></section>'
        reader+='<script>const chapters='+json.dumps(chapters,ensure_ascii=False).replace('<','\\u003c')+';for(const c of chapters){const detail=document.createElement("details");const title=document.createElement("summary");title.textContent=c.title;detail.append(title);let loaded=false;detail.addEventListener("toggle",()=>{if(loaded||!detail.open)return;loaded=true;const content=document.createElement("div");const math=[];const safe=c.markdown.replace(/\\$\\$[\\s\\S]*?\\$\\$|\\$[^\\n$]+?\\$/g,m=>{math.push(m);return "MATHPLACEHOLDER"+(math.length-1)+"END"});content.innerHTML=markdownit({html:false}).render(safe).replace(/MATHPLACEHOLDER(\\d+)END/g,(_,n)=>math[n].replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"));detail.append(content);renderMathInElement(content,{delimiters:[{left:"$$",right:"$$",display:true},{left:"$",right:"$",display:false}],throwOnError:false});});document.getElementById("chapters").append(detail);}</script>'
        template=template.replace('</html>',scripts+reader+'</html>')
    (root/'review.html').write_text(template,encoding='utf-8')
    print(json.dumps({'summary':summary,'review_entries':len(cards),'detected_formula_blocks':sum(not c.get('source_selected') for c in cards),'html':str(root/'review.html')}))
if __name__=='__main__':main()
