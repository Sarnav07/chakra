"""Generate a self-contained Kaggle notebook from the checked-in P1 scripts."""

from __future__ import annotations

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "CHAKRA_P1_Kaggle.ipynb"


def markdown(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": source.splitlines(keepends=True)}


def code(source: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source.splitlines(keepends=True),
    }


INTRO = """# CHAKRA P1: waste item classifier

Attach these two Kaggle datasets to this notebook before running it:

1. [Garbage Classification (12 classes) ENHANCED](https://www.kaggle.com/datasets/huberthamelin/garbage-classification-labels-corrections), using only its `garbage_classification_enhanced` folder.
2. [Garbage Classification](https://www.kaggle.com/datasets/asdasdasasdas/garbage-classification), the six-class clean-image source.

Set **Accelerator = GPU** and **Internet = On**. Kaggle may require phone verification to unlock those settings. The notebook downloads [RealWaste from UCI](https://archive.ics.uci.edu/dataset/908/realwaste) directly and holds all of it out for the domain-shift test. UCI currently lists RealWaste as **CC BY 4.0**; check licenses for all sources before commercial use.

The model has six internal outputs in the CHAKRA checkpoint order: battery, metal, organic, other, paper, plastic. Battery is a safety flag, never an "other" disposal item. The model files are saved to `/kaggle/working`.
"""


DISCOVER = r'''from pathlib import Path
import os

INPUT = Path('/kaggle/input')
WORK = Path('/kaggle/working')
print('CUDA:', __import__('torch').cuda.is_available())
if not __import__('torch').cuda.is_available():
    raise RuntimeError('Enable a GPU in Kaggle notebook settings before training.')

for root, dirs, files in os.walk(INPUT):
    depth = Path(root).relative_to(INPUT).parts
    if len(depth) > 3:
        dirs[:] = []
        continue
    print(root, len(files), 'files')

def folders_named(name):
    return sorted(p for p in INPUT.rglob('*') if p.is_dir() and p.name == name)

enhanced = folders_named('garbage_classification_enhanced')
if len(enhanced) != 1:
    raise RuntimeError(f'Expected one enhanced folder; found {enhanced}. Attach the 12-class Kaggle dataset.')
KAGGLE12_DIR = enhanced[0]

six_labels = {'cardboard', 'glass', 'metal', 'paper', 'plastic', 'trash'}
clean_roots = []
for folder in INPUT.rglob('*'):
    if not folder.is_dir() or KAGGLE12_DIR in folder.parents or folder == KAGGLE12_DIR:
        continue
    children = {p.name.lower().strip() for p in folder.iterdir() if p.is_dir()}
    if children == six_labels:
        clean_roots.append(folder)
if not clean_roots:
    raise RuntimeError('No six-class folder found. Attach the six-class Kaggle dataset.')
clean_roots.sort()
TRASHNET_DIR = clean_roots[0]
if len(clean_roots) > 1:
    print('Several six-class copies found; using one:', TRASHNET_DIR)
print('Enhanced:', KAGGLE12_DIR)
print('Six-class:', TRASHNET_DIR)
'''


REALWASTE = r'''from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile

UCI_ZIP_URL = 'https://archive.ics.uci.edu/static/public/908/realwaste.zip'
REALWASTE_DIR = WORK / 'realwaste-main' / 'RealWaste'
archive = WORK / 'realwaste.zip'
if not REALWASTE_DIR.is_dir():
    if not archive.exists():
        print('Downloading official UCI RealWaste archive (about 657 MB)...', flush=True)
        with urlopen(UCI_ZIP_URL, timeout=120) as response, archive.open('wb') as target:
            while block := response.read(1024 * 1024):
                target.write(block)
        print('Downloaded:', archive.stat().st_size, 'bytes')
    with ZipFile(archive) as zipped:
        for info in zipped.infolist():
            destination = (WORK / info.filename).resolve()
            if not destination.is_relative_to(WORK.resolve()):
                raise ValueError(f'Unsafe ZIP entry: {info.filename}')
        zipped.extractall(WORK)

expected = {
    'Cardboard': 461, 'Food Organics': 411, 'Glass': 420,
    'Metal': 790, 'Miscellaneous Trash': 495, 'Paper': 500,
    'Plastic': 921, 'Textile Trash': 318, 'Vegetation': 436,
}
actual = {name: len(list((REALWASTE_DIR / name).glob('*.jpg'))) for name in expected}
print('RealWaste:', REALWASTE_DIR, actual)
if actual != expected:
    raise ValueError(f'RealWaste does not match the UCI class counts: {actual}')
'''


TRAIN = r'''import subprocess
import sys

def run(*args):
    print('Running:', ' '.join(map(str, args)), flush=True)
    subprocess.run([sys.executable, *map(str, args)], check=True)

run(WORK / 'prepare_dataset.py',
    '--source', f'kaggle12={KAGGLE12_DIR}',
    '--source', f'trashnet={TRASHNET_DIR}',
    '--source', f'realwaste={REALWASTE_DIR}',
    '--out', WORK / 'manifest.csv')

run(WORK / 'train_classifier.py',
    '--manifest', WORK / 'manifest.csv',
    '--holdout-source', 'realwaste',
    '--epochs', '8', '--batch-size', '64', '--lr', '0.0003',
    '--out-dir', WORK, '--seed', '0', '--num-workers', '2')

run(WORK / 'eval_classifier.py',
    '--model', WORK / 'item_classifier.pt',
    '--manifest', WORK / 'manifest.csv',
    '--holdout-source', 'realwaste',
    '--out', WORK / 'classifier_report.json')
'''


REPORT = r'''import json

report = json.loads((WORK / 'classifier_report.json').read_text())
for name in ('random_test', 'shift_test'):
    result = report[name]
    print(name, 'images =', result['n_images'], 'accuracy =', round(result['accuracy'], 4))
    print('absent classes:', result['absent_classes'])
print('Classes:', report['classes'])
print('Download item_classifier.pt and classifier_report.json from /kaggle/working')
'''


def build() -> dict:
    cells = [markdown(INTRO), code(DISCOVER), code(REALWASTE)]
    for filename in ('prepare_dataset.py', 'train_classifier.py', 'eval_classifier.py'):
        source = (HERE / filename).read_text(encoding='utf-8')
        cells.append(code(f'%%writefile /kaggle/working/{filename}\n{source}'))
    cells.extend((code(TRAIN), code(REPORT)))
    for index, cell in enumerate(cells, start=1):
        cell['id'] = f'chakra-p1-{index:02d}'
    return {
        'cells': cells,
        'metadata': {
            'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
            'language_info': {'name': 'python'},
        },
        'nbformat': 4,
        'nbformat_minor': 5,
    }


if __name__ == '__main__':
    OUTPUT.write_text(json.dumps(build(), indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    print(OUTPUT)
