"""Export a person's capture JSON as experimental MetaHuman Maya GUI curves."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.metahuman import export_curves


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    parser.add_argument('--faceboard', type=Path, required=True)
    parser.add_argument('--mapping', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    inputs = {args.capture.resolve(), args.faceboard.resolve()}
    if args.mapping:
        inputs.add(args.mapping.resolve())
    if args.output.resolve() in inputs:
        parser.error('Output must not overwrite an input')
    capture = json.loads(args.capture.read_text(encoding='utf-8-sig'))
    board = json.loads(args.faceboard.read_text(encoding='utf-8-sig'))
    mapping = json.loads(args.mapping.read_text(encoding='utf-8-sig')) if args.mapping else None
    result = export_curves(capture, board, mapping)
    args.output.write_text(json.dumps(result, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    print(f"{len(result['frames'])} frames, {len(result['channels'])} controls; experimental mapping")
    print('Unmapped observed coefficients: ' + ', '.join(result['unmapped_observed']))


if __name__ == '__main__':
    main()
