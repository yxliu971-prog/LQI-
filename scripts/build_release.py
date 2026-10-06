"""Build a new timestamped Windows release, preserving earlier runtime data."""
import argparse
from datetime import datetime
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run',action='store_true',help='Print the build command without modifying files.')
    args=parser.parse_args()
    stamp=datetime.now().strftime('%Y%m%d-%H%M%S')
    target=ROOT/'releases'/stamp
    command=[sys.executable,'-m','PyInstaller','--noconfirm','--windowed','--onedir','--name','LQI',
             '--workpath',str(ROOT/'build/pyinstaller'),'--specpath',str(ROOT/'build/spec'),
             '--distpath',str(target),'--add-data',f'{ROOT / "data"};data',
             '--collect-all','shap','--collect-all','lightgbm','--collect-binaries','xgboost',
             '--collect-data','xgboost','--collect-data','rdkit','--exclude-module','xgboost.testing',
             '--exclude-module','tkinter','--exclude-module','IPython','--exclude-module','pytest',str(ROOT/'main.py')]
    if args.dry_run:
        print(subprocess.list2cmdline(command))
        return 0
    if sys.platform!='win32':
        parser.error('The portable release must be built on Windows x64.')
    if importlib.util.find_spec('PyInstaller') is None:
        parser.error('Install requirements-dev.txt first.')
    if not target.resolve().is_relative_to(ROOT.resolve()) or target.exists():
        raise RuntimeError('Release target must be a new directory within this project.')
    (ROOT/'build/spec').mkdir(parents=True,exist_ok=True)
    target.mkdir(parents=True)
    environment=os.environ.copy()
    # Keep packaging caches and temporary files inside this project.
    for variable, folder in [('PYINSTALLER_CONFIG_DIR','build/cache'),('TEMP','build/temp'),('TMP','build/temp')]:
        directory=ROOT/folder
        directory.mkdir(parents=True,exist_ok=True)
        environment[variable]=str(directory)
    windows=Path(environment.get('SystemRoot','C:/Windows'))
    environment['PATH']=os.pathsep.join([str(windows/'System32'),str(windows),str(Path(sys.executable).parent)])
    subprocess.run(command,cwd=ROOT,env=environment,check=True)
    release=target/'LQI'
    shutil.copy2(ROOT/'README.md',release/'README.md')
    shutil.copy2(ROOT/'data/quickstart.html',release/'使用说明.html')
    shutil.copytree(ROOT/'docs',release/'docs')
    shutil.copytree(ROOT/'examples',release/'examples')
    shutil.copytree(ROOT/'导入模板',release/'导入模板')
    print(f'Portable application: {release / "LQI.exe"}')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
