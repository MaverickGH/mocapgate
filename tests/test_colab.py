"""Colab-ноутбук собран из текущего ядра, его код компилируется, встроенное ядро даёт тот же BVH."""
from __future__ import annotations
import ast, importlib, json, random, re, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import build_colab  # noqa: E402

NB = ROOT / "colab" / "MoCapGate_GVHMR.ipynb"


class Colab(unittest.TestCase):
    def test_notebook_is_up_to_date(self):
        want = json.dumps(build_colab.build(), ensure_ascii=False, indent=1) + "\n"
        self.assertEqual(NB.read_text(encoding="utf-8"), want, "пересобери: python3 tools/build_colab.py")

    def test_cells_compile(self):
        nb = json.loads(NB.read_text(encoding="utf-8"))
        for i, c in enumerate(nb["cells"]):
            if c["cell_type"] != "code":
                continue
            src = "".join(c["source"])
            if src.startswith("%%writefile"):
                src = src.partition("\n")[2]  # пустой __init__.py — только заголовок
            src = "\n".join("pass" if re.match(r"\s*[!%]", l) else l for l in src.splitlines())
            ast.parse(src, f"cell {i}")
            for m in re.finditer(r"RUNNER_CODE = ('(?:[^'\\]|\\.)*')", src):  # код раннера GVHMR внутри строки
                ast.parse(ast.literal_eval(m.group(1)), "runner")

    def test_embedded_core_matches(self):
        nb = json.loads(NB.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as d:
            pkg = Path(d) / "mocapgate_core"
            pkg.mkdir()
            for c in nb["cells"]:
                src = "".join(c["source"])
                if src.startswith("%%writefile /content/mocapgate_core/"):
                    head, _, body = src.partition("\n")
                    (pkg / head.rsplit("/", 1)[1]).write_text(body, encoding="utf-8")
            sys.path.insert(0, d)
            try:
                nb_gv = importlib.import_module("mocapgate_core.gvhmr")
                nb_conv = importlib.import_module("mocapgate_core.smpl_bvh")
                nb_bvh = importlib.import_module("mocapgate_core.bvh")
            finally:
                sys.path.remove(d)
            from core import gvhmr, smpl_bvh, bvh
            rng = random.Random(9)
            n = 5
            take = {"format": "mocapgate.take/1", "fps": 30.0, "smpl_params_global": {
                "global_orient": [[rng.uniform(-1, 1) for _ in range(3)] for _ in range(n)],
                "body_pose": [[rng.uniform(-.5, .5) for _ in range(63)] for _ in range(n)],
                "transl": [[rng.uniform(-1, 1) for _ in range(3)] for _ in range(n)]}}
            p = Path(d) / "t.mocapgate.json"
            p.write_text(json.dumps(take), encoding="utf-8")
            a = nb_bvh.write(*nb_conv.convert(nb_gv.load(str(p))), 1 / 30)
            b = bvh.write(*smpl_bvh.convert(gvhmr.load(str(p))), 1 / 30)
            self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
