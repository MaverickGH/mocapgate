"""Inspect a MetaHuman DNA using separately installed Epic OpenRigLogic bindings."""
import argparse
import json
from pathlib import Path
import sys


def inspect_dna(path, runtime):
    sys.path.insert(0, str(runtime.resolve()))
    import dna
    import riglogic

    stream = dna.FileStream(str(path.resolve()), dna.AccessMode_Read, dna.OpenMode_Binary)
    reader = dna.BinaryStreamReader(stream)
    reader.read()
    if not dna.Status.isOk():
        raise ValueError(dna.Status.get().message)
    meshes = [{'name': reader.getMeshName(i), 'vertices': reader.getVertexPositionCount(i)}
              for i in range(reader.getMeshCount())]
    # Verify evaluation too, rather than accepting a DNA signature alone.
    logic = riglogic.RigLogic(reader)
    instance = riglogic.RigInstance(logic)
    logic.calculate(instance)
    return {'name': reader.getName(), 'rig_definition': reader.getDBName(),
            'joints': reader.getJointCount(), 'meshes': meshes,
            'gui_controls': [reader.getGUIControlName(i) for i in range(reader.getGUIControlCount())],
            'raw_controls': [reader.getRawControlName(i) for i in range(reader.getRawControlCount())],
            'has_geometry': any(m['vertices'] > 0 for m in meshes),
            'joint_output_values': len(instance.getJointOutputs()),
            'blendshape_output_values': len(instance.getBlendShapeOutputs())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dna', type=Path)
    parser.add_argument('--runtime', type=Path, required=True, help='Folder containing dna.py and riglogic.py')
    parser.add_argument('--require-geometry', action='store_true')
    args = parser.parse_args()
    try:
        report = inspect_dna(args.dna, args.runtime)
    except (ImportError, OSError, ValueError) as error:
        parser.exit(1, str(error) + '\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.require_geometry and not report['has_geometry']:
        parser.exit(2, 'This DNA has no character geometry; supply a full head DNA/DCC export.\n')


if __name__ == '__main__':
    main()
