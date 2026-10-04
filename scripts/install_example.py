"""Install the redistributable Sports2D sample without overwriting user takes."""
import argparse
import shutil
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('app_root', type=Path)
    ap.add_argument('--library', type=Path)
    args = ap.parse_args()
    package = Path(__file__).resolve().parents[1]
    source = package / 'examples' / 'sports2d'
    sys.path.insert(0, str(args.app_root.resolve()))
    from core import settings
    library = args.library or settings.library()
    destination = library / 'sample-sports2d-two-people'
    if destination.exists():
        print('Example already present:', destination)
        return
    if not (source / 'take.json').is_file():
        raise SystemExit('Sample missing: extract the complete quickstart package first.')
    library.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)
    shutil.copy2(package / 'tests/fixtures/sports2d/two_people.mp4', destination / 'input.mp4')
    print('Example installed:', destination)


if __name__ == '__main__':
    main()
