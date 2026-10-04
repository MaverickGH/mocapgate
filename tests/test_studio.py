"""Studio: конвейер дублей (GVHMR из Colab с ожиданием и догрузкой) и сервер (токен, Host, Range, загрузка)."""
from __future__ import annotations
import http.client, json, math, os, random, shutil, subprocess, sys, tempfile, threading, time, unittest, zipfile
from urllib.parse import quote
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps" / "studio"))
TMP = Path(tempfile.mkdtemp(prefix="mocapgate-test-"))
os.environ["MOCAPGATE_HOME"] = str(TMP / "cfg")  # настройки теста не трогают настоящие

from core import pipeline, smpl  # noqa: E402
import server  # noqa: E402


def gvhmr_take(n=20) -> dict:
    """Синтетический результат GVHMR: человек в 4 м перед камерой, машет рукой."""
    rng = random.Random(5)
    glob, inc = {k: [] for k in ("global_orient", "body_pose", "transl", "betas")}, {k: [] for k in ("global_orient", "body_pose", "transl", "betas")}
    for f in range(n):
        body = [0.0] * 63
        body[45:48] = [0, 0, -1.2 + 0.4 * math.sin(f / 3)]
        for d, go, tr in ((glob, [0, 0, 0], [0.01 * f, 0.9, 0]), (inc, [math.pi, 0, 0], [0.0, 0.2, 4.0])):
            d["global_orient"].append(go)
            d["body_pose"].append(body)
            d["transl"].append(tr)
            d["betas"].append([0.0] * 10)
    return {"format": "mocapgate.take/1", "source": "gvhmr", "fps": 30.0, "video": {"width": 1280, "height": 720},
            "smpl_params_global": glob, "smpl_params_incam": inc,
            "K_fullimg": [[1000.0, 0, 640.0], [0, 1000.0, 360.0], [0, 0, 1]]}


def tiny_video(path: Path, seconds=1):
    ff = shutil.which("ffmpeg")
    if not ff:
        raise unittest.SkipTest("нужен ffmpeg")
    subprocess.run([ff, "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"testsrc=size=320x240:rate=30:duration={seconds}",
                    "-pix_fmt", "yuv420p", str(path)], check=True)


class Jobs(unittest.TestCase):
    def test_output_closed_after_completion(self):
        job = server.Job("pipe-test", [sys.executable, "-c", "print('finished')"], "test")
        deadline = time.monotonic() + 15
        while job.code is None and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertEqual(job.code, 0)
        self.assertTrue(job.proc.stdout.closed)
        self.assertEqual(job.lines, [{"message": "finished", "stage": "log"}])

    @unittest.skipUnless(os.name == "nt", "Windows process-tree cancellation")
    def test_cancel_stops_child_process(self):
        with tempfile.TemporaryDirectory(dir=TMP) as tmp:
            pidfile = Path(tmp) / "child.json"
            script = ("import subprocess,sys,json,time; from pathlib import Path; "
                      "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(120)']); "
                      "p=Path(sys.argv[1]); tmp=p.with_suffix('.tmp'); "
                      "tmp.write_text(json.dumps(child.pid)); tmp.replace(p); time.sleep(120)")
            job = server.Job("cancel-test", [sys.executable, "-c", script, str(pidfile)], "test")
            try:
                deadline = time.monotonic() + 15
                while not pidfile.exists() and time.monotonic() < deadline:
                    time.sleep(0.05)
                self.assertTrue(pidfile.exists())
                child = json.loads(pidfile.read_text())
                job.cancel()
                while job.code is None and time.monotonic() < deadline:
                    time.sleep(0.05)
                self.assertTrue(job.cancelled)
                self.assertIsNotNone(job.code)
                result = subprocess.run(["tasklist", "/FI", f"PID eq {child}", "/FO", "CSV", "/NH"],
                                        capture_output=True, text=True, check=True)
                self.assertNotIn(f'"{child}"', result.stdout)
            finally:
                if job.code is None:
                    job.cancel()


class Pipeline(unittest.TestCase):
    def setUp(self):
        self.lib = Path(tempfile.mkdtemp(prefix="lib-", dir=TMP))  # time_ns на Windows грубый — имена совпадали

    def test_gvhmr_file_take(self):
        src = TMP / "walk.mocapgate.json"
        src.write_text(json.dumps(gvhmr_take()), encoding="utf-8")
        take = pipeline.create_take(self.lib, "walk", [src], "mediapipe")
        meta = pipeline.read_meta(take)
        self.assertEqual(meta["backend"], "gvhmr-file")  # результат GVHMR — не MediaPipe, даже если выбран он
        code = pipeline.process(take)
        meta = pipeline.read_meta(take)
        self.assertEqual(code, 0, meta.get("error"))
        self.assertEqual(meta["frames"], 20)
        self.assertTrue((take / meta["bvh"]).is_file())
        ov = json.loads((take / "overlay.json").read_text())
        # таз в 4 м перед камерой по оси: проекция таза — центр кадра по X
        self.assertAlmostEqual(ov["skeleton"][0][0][0], 640.0 + 1000.0 * smpl.DEFAULT_REST[0][0] / 4.0, delta=30)
        rep = json.loads((take / "report.json").read_text())
        self.assertIn(rep["verdict"], ("good", "warn", "bad"))

    def test_colab_wait_then_attach(self):
        vid = TMP / "clip.mp4"
        tiny_video(vid)
        st = server.Studio(self.lib, "tok")
        up = st.uploads() / "0123456789abcdef.mp4"
        shutil.copy(vid, up)
        d = st.create({"files": [up.name], "name": "clip", "backend": "gvhmr-colab"})
        self.assertEqual(d["status"], "waiting-result")
        self.assertIsNone(d["job"])
        # результат из Colab приходит архивом
        zp = TMP / "clip_mocapgate.zip"
        with zipfile.ZipFile(zp, "w") as z:
            z.writestr("clip.mocapgate.json", json.dumps(gvhmr_take(30)))
            z.write(vid, "clip.mp4")
        up2 = st.uploads() / "fedcba9876543210.zip"
        shutil.copy(zp, up2)
        a = st.attach(d["id"], {"files": [up2.name]})
        job = st.jobs[a["job"]]
        for _ in range(300):
            if job.code is not None:
                break
            time.sleep(0.1)
        meta = pipeline.read_meta(self.lib / d["id"])
        self.assertEqual(job.code, 0, job.lines[-3:])
        self.assertEqual(meta["backend"], "gvhmr-file")
        self.assertEqual(meta["status"], "done")
        self.assertEqual(meta["frames"], 30)

    def test_startup_does_not_create_library(self):
        lib = Path(tempfile.mkdtemp(prefix="absent-", dir=TMP)) / "library"
        st = server.Studio(lib, "tok")
        st.status()
        self.assertEqual(pipeline.list_takes(st.library()), [])
        self.assertFalse(lib.exists())  # папка появится с первым дублем, а не при запуске

    def test_snap_fps(self):
        self.assertEqual(pipeline.snap_fps(29.83), 30.0)
        self.assertEqual(pipeline.snap_fps(59.94), 60.0)
        self.assertEqual(pipeline.snap_fps(15.0), 15.0)


class Server(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib = TMP / "srv-lib"
        cls.lib.mkdir(parents=True, exist_ok=True)
        cls.studio = server.Studio(cls.lib, "secret-token")
        port = [0]
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(cls.studio, port))
        port[0] = cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        src = TMP / "s.mocapgate.json"
        src.write_text(json.dumps(gvhmr_take()), encoding="utf-8")
        cls.take = pipeline.create_take(cls.lib, "srv", [src], "gvhmr-file")
        pipeline.process(cls.take)

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def req(self, method, path, body=None, headers=None, host=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        h = {"Host": host or f"127.0.0.1:{self.port}", **(headers or {})}
        c.request(method, path, body=body, headers=h)
        r = c.getresponse()
        data = r.read()
        c.close()
        return r.status, dict(r.getheaders()), data

    def test_token_required(self):
        self.assertEqual(self.req("GET", "/api/status")[0], 401)
        self.assertEqual(self.req("GET", "/api/status?t=wrong")[0], 401)
        self.assertEqual(self.req("GET", "/api/status", headers={"X-MoCapGate-Token": "secret-token"})[0], 200)

    def test_foreign_host_rejected(self):
        # DNS-rebinding: чужое имя хоста не проходит даже с токеном
        self.assertEqual(self.req("GET", "/api/status?t=secret-token", host="evil.example:80")[0], 403)

    def test_ui_without_token(self):
        self.assertEqual(self.req("GET", "/")[0], 200)

    def test_range_for_video_seeking(self):
        meta = pipeline.read_meta(self.take)
        st, h, data = self.req("GET", f"/files/{self.take.name}/{meta['bvh']}?t=secret-token", headers={"Range": "bytes=0-9"})
        self.assertEqual(st, 206)
        self.assertEqual(data, b"HIERARCHY\n")
        self.assertTrue(h["Content-Range"].startswith("bytes 0-9/"))

    def test_path_traversal(self):
        st, _, _ = self.req("GET", f"/files/{self.take.name}/..%2F..%2Fetc?t=secret-token")
        self.assertIn(st, (400, 404))
        st, _, _ = self.req("GET", "/files/../take.json?t=secret-token")
        self.assertIn(st, (400, 404))

    def test_upload_types(self):
        st, _, data = self.req("POST", "/api/upload?name=x.exe&t=secret-token", body=b"MZ")
        self.assertEqual(st, 400)
        st, _, data = self.req("POST", "/api/upload?name=a.json&t=secret-token", body=b"{}")
        self.assertEqual(st, 200)
        self.assertRegex(json.loads(data)["id"], r"^[0-9a-f]{16}\.json$")

    def test_open_url_whitelist(self):
        st, _, _ = self.req("POST", "/api/open-url?t=secret-token", body=json.dumps({"url": "https://evil.example/x"}),
                            headers={"Content-Type": "application/json"})
        self.assertEqual(st, 400)

    def test_json_only_posts(self):
        st, _, _ = self.req("POST", "/api/settings?t=secret-token", body="lang=ru",
                            headers={"Content-Type": "application/x-www-form-urlencoded"})
        self.assertEqual(st, 415)  # формы с чужих сайтов не проходят

    def test_take_list_and_info(self):
        st, _, data = self.req("GET", "/api/takes?t=secret-token")
        self.assertEqual(st, 200)
        self.assertTrue(any(t["id"] == self.take.name for t in json.loads(data)))
        st, _, data = self.req("GET", f"/api/takes/{self.take.name}?t=secret-token")
        self.assertEqual(json.loads(data)["status"], "done")

    def test_unicode_take_and_export_routes(self):
        source = TMP / 'unicode.mocapgate.json'
        source.write_text(json.dumps(gvhmr_take()), encoding='utf-8')
        take = pipeline.create_take(self.lib, 'Два человека', [source], 'gvhmr-file')
        self.assertEqual(pipeline.process(take), 0)
        route = '/api/takes/' + quote(take.name)
        status, _, body = self.req('GET', route+'?t=secret-token')
        self.assertEqual(status, 200)
        meta = json.loads(body)
        status, headers, body = self.req('GET', '/files/'+quote(take.name)+'/'+quote(meta['bvh'])+'?download=1&t=secret-token')
        self.assertEqual(status, 200)
        self.assertIn(b'Frames: 20', body)
        status, _, _ = self.req('POST', route+'/rename?t=secret-token', body=json.dumps({'name':'Новый дубль'}), headers={'Content-Type':'application/json'})
        self.assertEqual(status, 200)


if __name__ == "__main__":
    unittest.main()
