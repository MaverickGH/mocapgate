// MoCapGate Studio — десктоп-оболочка. Запускает локальный сервер Studio (apps/studio/server.py, Python на stdlib)
// со свежим токеном сессии, ждёт его строку «MOCAPGATE_STUDIO <url>» и показывает эту страницу в окне. Вся работа —
// распознавание позы, Blender, проверка — идёт в сервере, ровно как у `mocapgate.py studio`. Устроено как MeshGate Studio.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::collections::hash_map::RandomState;
use std::hash::{BuildHasher, Hasher};
use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;

use tauri::{AppHandle, Manager, RunEvent, Url};

struct Server(Mutex<Option<Child>>);
/// Порт и токен сервера — для вызова /api/shutdown при закрытии приложения.
struct Endpoint(Mutex<Option<(u16, String)>>);

/// Попросить сервер отменить задачи (и их дочерние процессы) и выйти; немного подождать.
fn shutdown_server(port: u16, token: &str, child: &mut Child) {
    use std::io::{Read, Write};
    use std::net::{SocketAddr, TcpStream};
    use std::time::{Duration, Instant};
    let addr = SocketAddr::from(([127, 0, 0, 1], port));
    if let Ok(mut s) = TcpStream::connect_timeout(&addr, Duration::from_millis(500)) {
        let _ = s.set_read_timeout(Some(Duration::from_secs(2)));
        let req = format!(
            "POST /api/shutdown HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nX-MoCapGate-Token: {token}\r\n\
             Content-Type: application/json\r\nContent-Length: 2\r\nConnection: close\r\n\r\n{{}}"
        );
        let _ = s.write_all(req.as_bytes());
        let mut buf = [0u8; 256];
        let _ = s.read(&mut buf);
    }
    let start = Instant::now();
    while start.elapsed() < Duration::from_secs(15) {
        if let Ok(Some(_)) = child.try_wait() {
            return;
        }
        std::thread::sleep(Duration::from_millis(100));
    }
}

/// 128-битный токен сессии из ключей хешера, засеянных ОС (без лишних крейтов).
fn token() -> String {
    (0..2)
        .map(|i| {
            let mut h = RandomState::new().build_hasher();
            h.write_u64((std::process::id() as u64) ^ ((i as u64) << 32));
            format!("{:016x}", h.finish())
        })
        .collect()
}

/// Файлы MoCapGate: MOCAPGATE_ROOT, ресурсы пакета приложения или репозиторий при dev-сборке.
fn mocapgate_root(app: &AppHandle) -> Option<PathBuf> {
    if let Ok(p) = std::env::var("MOCAPGATE_ROOT") {
        let p = PathBuf::from(p);
        if p.join("mocapgate.py").exists() {
            return Some(p);
        }
    }
    if let Ok(res) = app.path().resource_dir() {
        let p = res.join("mocapgate");
        if p.join("mocapgate.py").exists() {
            return Some(p);
        }
    }
    let dev = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../../..");
    if dev.join("mocapgate.py").exists() {
        return dev.canonicalize().ok();
    }
    None
}

/// Приложения из Finder/«Пуска» получают урезанный PATH, а uv, ffmpeg и Blender обычно в PATH оболочки
/// пользователя (Homebrew, ~/.local/bin). Спросим login-shell один раз и добавим привычные папки.
fn user_path() -> String {
    let mut parts: Vec<String> = Vec::new();
    #[cfg(windows)]
    if let Some(home) = std::env::var_os("USERPROFILE") {
        parts.push(PathBuf::from(home).join(".local/bin").to_string_lossy().into_owned());
    }
    #[cfg(not(windows))]
    {
        let shell = std::env::var("SHELL").unwrap_or_else(|_| "/bin/zsh".into());
        if let Ok(out) = Command::new(&shell).args(["-ilc", "printf '%s' \"$PATH\""]).stdin(Stdio::null()).output() {
            let p = String::from_utf8_lossy(&out.stdout).trim().to_string();
            if !p.is_empty() {
                parts.push(p);
            }
        }
        if let Ok(home) = std::env::var("HOME") {
            for d in [".local/bin", ".cargo/bin"] {
                parts.push(format!("{home}/{d}"));
            }
        }
        parts.extend(["/opt/homebrew/bin", "/usr/local/bin"].iter().map(|s| s.to_string()));
    }
    if let Ok(p) = std::env::var("PATH") {
        parts.push(p);
    }
    parts.join(if cfg!(windows) { ";" } else { ":" })
}

/// Python 3.9+ для сервера: MOCAPGATE_PYTHON, затем привычные имена и места.
fn find_python(root: &Path, path: &str) -> Option<Vec<String>> {
    if root.join("native-manifest.json").is_file() {
        let python = root.join(if cfg!(windows) { "python/python.exe" } else { "python/bin/python3.12" });
        let mut cmd = Command::new(&python);
        cmd.current_dir(root).args(["-B", "-c", "import sys; from native_loader import load; assert sys.version.split()[0] == '3.12.13'; load('cli')"]).env("PATH", path);
        hide_console(&mut cmd);
        return match cmd.output() {
            Ok(out) if out.status.success() => Some(vec![python.to_string_lossy().into_owned()]),
            _ => None,
        };
    }
    let mut candidates: Vec<Vec<String>> = Vec::new();
    if let Ok(p) = std::env::var("MOCAPGATE_PYTHON") {
        candidates.push(vec![p]);
    }
    #[cfg(windows)]
    if let Some(local) = std::env::var_os("LOCALAPPDATA") {
        candidates.push(vec![PathBuf::from(local).join("MoCapGate Runtime/Scripts/python.exe").to_string_lossy().into_owned()]);
    }
    #[cfg(not(windows))]
    if let Some(home) = std::env::var_os("HOME") {
        candidates.push(vec![PathBuf::from(home).join(".cache/mocapgate/studio-runtime/bin/python").to_string_lossy().into_owned()]);
    }
    let names: &[&[&str]] = if cfg!(windows) {
        &[&["py", "-3"], &["python"], &["python3"]]
    } else {
        &[&["python3"], &["/opt/homebrew/bin/python3"], &["/usr/local/bin/python3"], &["/usr/bin/python3"], &["python"]]
    };
    candidates.extend(names.iter().map(|c| c.iter().map(|s| s.to_string()).collect()));
    #[cfg(windows)]
    {
        // Python and uv can be installed per user without being added to PATH.
        let mut roots = Vec::new();
        if let Some(local) = std::env::var_os("LOCALAPPDATA") {
            roots.push(PathBuf::from(local).join("Programs/Python"));
        }
        if let Some(roaming) = std::env::var_os("APPDATA") {
            roots.push(PathBuf::from(roaming).join("uv/python"));
        }
        if let Some(custom) = std::env::var_os("UV_PYTHON_INSTALL_DIR") {
            roots.push(PathBuf::from(custom));
        }
        for root in roots {
            if let Ok(entries) = std::fs::read_dir(root) {
                let mut interpreters: Vec<_> = entries.flatten()
                    .map(|entry| entry.path().join("python.exe"))
                    .filter(|python| python.is_file())
                    .collect();
                interpreters.sort();
                for python in interpreters.into_iter().rev() {
                    candidates.push(vec![python.to_string_lossy().into_owned()]);
                }
            }
        }
    }
    for c in candidates {
        let mut cmd = Command::new(&c[0]);
        cmd.args(&c[1..]).args(["-c", "import sys; print(sys.version_info >= (3, 9))"]).env("PATH", path);
        hide_console(&mut cmd);
        if let Ok(out) = cmd.output() {
            if String::from_utf8_lossy(&out.stdout).trim() == "True" {
                return Some(c);
            }
        }
    }
    None
}

fn hide_console(_cmd: &mut Command) {
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        _cmd.creation_flags(0x0800_0000); // CREATE_NO_WINDOW
    }
}

fn show_error(app: &AppHandle, text: &str) {
    if let Some(w) = app.get_webview_window("main") {
        let js = format!("window.showError({})", serde_json::to_string(text).unwrap_or_default());
        let _ = w.eval(&js);
    }
}

fn start_server(app: AppHandle) {
    let Some(root) = mocapgate_root(&app) else {
        return show_error(&app, "Файлы MoCapGate не найдены рядом с приложением (задайте MOCAPGATE_ROOT).\nThe MoCapGate files were not found next to the app.");
    };
    let path = format!("{}{}{}", root.display(), if cfg!(windows) { ";" } else { ":" }, user_path());
    let Some(python) = find_python(&root, &path) else {
        if root.join("native-manifest.json").is_file() {
            return show_error(&app, "Встроенный Python или нативные библиотеки не подходят этой ОС/архитектуре. Переустановите соответствующий пакет.\nThe bundled runtime does not match this OS/architecture. Reinstall the matching package.");
        }
        let how = if cfg!(windows) {
            "Установите Python с python.org (отметьте «Add python.exe to PATH») и откройте MoCapGate Studio снова.\nInstall Python from python.org (tick \"Add python.exe to PATH\"), then open MoCapGate Studio again."
        } else {
            "Установите Python с python.org (или выполните xcode-select --install в Терминале) и откройте MoCapGate Studio снова.\nInstall Python from python.org (or run xcode-select --install), then open MoCapGate Studio again."
        };
        return show_error(&app, &format!("Не найден Python 3.9+ · Python 3.9+ was not found.\n\n{how}"));
    };
    let tok = token();
    let mut cmd = Command::new(&python[0]);
    cmd.args(&python[1..])
        .arg(root.join("mocapgate.py"))
        .args(["studio", "--port", "0", "--no-browser", "--desktop"])
        .current_dir(&root)
        .env("PATH", &path)
        .env("MOCAPGATE_STUDIO_TOKEN", &tok) // не в argv: командные строки видны другим процессам
        .env("PYTHONUNBUFFERED", "1")
        .env("PYTHONDONTWRITEBYTECODE", "1") // никаких .pyc внутри пакета приложения
        .env("PYTHONIOENCODING", "utf-8")
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    hide_console(&mut cmd);
    let mut child = match cmd.spawn() {
        Ok(c) => c,
        Err(e) => return show_error(&app, &format!("Не удалось запустить {}: {e}", python.join(" "))),
    };
    let stdout = child.stdout.take();
    let stderr = child.stderr.take();
    *app.state::<Server>().0.lock().unwrap() = Some(child);

    // всё, что печатает сервер, — ещё и в лог приложения (macOS ~/Library/Logs/dev.mocapgate.studio/studio.log,
    // Windows %LOCALAPPDATA%\dev.mocapgate.studio\logs\studio.log) — первое место, куда смотреть при сбое
    let log = app.path().app_log_dir().ok().and_then(|dir| {
        std::fs::create_dir_all(&dir).ok()?;
        std::fs::File::create(dir.join("studio.log")).ok()
    });
    let log = std::sync::Arc::new(Mutex::new(log));
    let write_log = {
        let log = log.clone();
        move |line: &str| {
            if let Some(f) = log.lock().unwrap().as_mut() {
                use std::io::Write;
                let _ = writeln!(f, "{line}");
            }
        }
    };
    let errors = std::sync::Arc::new(Mutex::new(String::new()));
    if let Some(err) = stderr {
        let errors = errors.clone();
        let write_log = write_log.clone();
        std::thread::spawn(move || {
            for line in BufReader::new(err).lines().map_while(Result::ok) {
                write_log(&line);
                let mut e = errors.lock().unwrap();
                e.push_str(&line);
                e.push('\n');
                if e.len() > 8000 {
                    let cut = e.len() - 8000;
                    e.drain(..cut);
                }
            }
        });
    }
    let Some(out) = stdout else { return };
    let mut opened = false;
    for line in BufReader::new(out).lines().map_while(Result::ok) {
        write_log(&line.replace(&tok, "<token>"));
        if let Some(url) = line.strip_prefix("MOCAPGATE_STUDIO ") {
            if let (Ok(url), Some(w)) = (Url::parse(url.trim()), app.get_webview_window("main")) {
                if let Some(port) = url.port() {
                    *app.state::<Endpoint>().0.lock().unwrap() = Some((port, tok.clone()));
                }
                let _ = w.navigate(url);
                opened = true;
            }
        }
    }
    if !opened {
        std::thread::sleep(std::time::Duration::from_millis(200));
        let e = errors.lock().unwrap().clone();
        show_error(&app, &format!("Сервер Studio остановился до готовности · The Studio server stopped before it was ready.\n\n{}", e.trim()));
    }
}

fn main() {
    let app = tauri::Builder::default()
        .manage(Server(Mutex::new(None)))
        .manage(Endpoint(Mutex::new(None)))
        .setup(|app| {
            let handle = app.handle().clone();
            std::thread::spawn(move || start_server(handle));
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("MoCapGate Studio: не удалось создать окно");
    app.run(|handle, event| {
        if let RunEvent::Exit = event {
            if let Some(mut child) = handle.state::<Server>().0.lock().unwrap().take() {
                if let Some((port, token)) = handle.state::<Endpoint>().0.lock().unwrap().clone() {
                    shutdown_server(port, &token, &mut child); // отменяет задачи — не остаётся висящих процессов
                }
                let _ = child.kill();
            }
        }
    });
}
