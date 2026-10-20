"""Install an isolated CPU runtime or fetch offline review assets."""
import argparse,io,platform,subprocess,sys,tarfile,urllib.request,venv
from pathlib import Path

def assets(dest):
    dest.mkdir(parents=True,exist_ok=True)
    for package,version in [('katex','0.16.22'),('markdown-it','14.1.0')]:
        url=f'https://registry.npmjs.org/{package}/-/{package}-{version}.tgz'
        with urllib.request.urlopen(url,timeout=60) as response:payload=response.read()
        with tarfile.open(fileobj=io.BytesIO(payload),mode='r:gz') as archive:
            for member in archive.getmembers():
                name=member.name;rel=None
                if package=='katex':
                    if name in ['package/dist/katex.min.js','package/dist/katex.min.css','package/dist/contrib/auto-render.min.js']:rel=Path(name).name
                    elif name.startswith('package/dist/fonts/') and name.endswith(('.woff','.woff2','.ttf')):rel='fonts/'+Path(name).name
                elif name=='package/dist/markdown-it.min.js':rel='markdown-it.min.js'
                if name=='package/LICENSE':rel=package+'-LICENSE.txt'
                if rel and member.isfile():
                    file=dest/rel;file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(archive.extractfile(member).read())
    print('Offline review assets:',dest)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--runtime',type=Path,default=Path(__file__).resolve().parents[1]/'.venv-math');ap.add_argument('--assets',type=Path);ap.add_argument('--assets-only',action='store_true');a=ap.parse_args()
    if a.assets_only and not a.assets:ap.error('--assets-only requires --assets PATH')
    if not a.assets_only:
        if sys.version_info[:2]!=(3,11):ap.error('Use Python 3.11 for this pinned runtime')
        venv.EnvBuilder(with_pip=True).create(a.runtime)
        python=a.runtime/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python')
        command=[str(python),'-m','pip','install','torch==2.5.1','torchvision==0.20.1']
        if sys.platform!='darwin':command+=['--index-url','https://download.pytorch.org/whl/cpu']
        subprocess.run(command,check=True)
        subprocess.run([str(python),'-m','pip','install','-r',str(Path(__file__).resolve().parents[1]/'requirements-local-math.txt')],check=True)
        subprocess.run([str(python),'-c','from pix2text import Pix2Text; import torch; print(torch.__version__, torch.ones(1))'],check=True)
        print('Runtime:',python,'Platform:',platform.platform())
    if a.assets:assets(a.assets)
if __name__=='__main__':main()
