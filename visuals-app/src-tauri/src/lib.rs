use chrono::Utc;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::{
    collections::{HashMap, HashSet},
    collections::hash_map::DefaultHasher,
    env,
    hash::{Hash, Hasher},
    fs,
    io::{Read, Seek, SeekFrom, Write},
    net::TcpListener,
    path::{Path, PathBuf},
    process::{Command, Stdio, Output},
    sync::{Arc, Mutex, OnceLock, RwLock},
    thread,
    time::{Duration, Instant},
};
#[cfg(unix)]
use std::os::unix::fs::PermissionsExt;

static CANCELLED_JOBS: OnceLock<Mutex<HashSet<String>>> = OnceLock::new();

fn get_cancelled_jobs() -> &'static Mutex<HashSet<String>> {
    CANCELLED_JOBS.get_or_init(|| Mutex::new(HashSet::new()))
}

fn is_job_cancelled(job_id: Option<&str>) -> bool {
    if let Some(id) = job_id {
        get_cancelled_jobs().lock().map(|s| s.contains(id)).unwrap_or(false)
    } else {
        false
    }
}

fn run_cmd_with_timeout(
    mut cmd: Command,
    timeout_secs: u64,
    job_id: Option<&str>,
) -> Result<Output, String> {
    cmd.stdout(Stdio::piped());
    cmd.stderr(Stdio::piped());
    let mut child = cmd.spawn().map_err(|e| format!("Failed to spawn process: {e}"))?;
    let start = Instant::now();
    let timeout = Duration::from_secs(timeout_secs);

    let mut stdout_handle = child.stdout.take();
    let mut stderr_handle = child.stderr.take();

    let stdout_join = std::thread::spawn(move || {
        let mut buf = Vec::new();
        if let Some(r) = stdout_handle.as_mut() {
            let _ = r.read_to_end(&mut buf);
        }
        buf
    });

    let stderr_join = std::thread::spawn(move || {
        let mut buf = Vec::new();
        if let Some(r) = stderr_handle.as_mut() {
            let _ = r.read_to_end(&mut buf);
        }
        buf
    });

    loop {
        if is_job_cancelled(job_id) {
            let _ = child.kill();
            let _ = child.wait();
            let _ = stdout_join.join();
            let _ = stderr_join.join();
            return Err("Operation cancelled by user".into());
        }

        match child.try_wait() {
            Ok(Some(status)) => {
                let stdout = stdout_join.join().unwrap_or_default();
                let stderr = stderr_join.join().unwrap_or_default();
                return Ok(Output {
                    status,
                    stdout,
                    stderr,
                });
            }
            Ok(None) => {
                if start.elapsed() >= timeout {
                    let _ = child.kill();
                    let _ = child.wait();
                    let _ = stdout_join.join();
                    let _ = stderr_join.join();
                    return Err(format!("MEDIA_PROBE_TIMEOUT: Process timed out after {timeout_secs}s and was terminated"));
                }
                thread::sleep(Duration::from_millis(20));
            }
            Err(e) => {
                let _ = child.kill();
                let _ = child.wait();
                let _ = stdout_join.join();
                let _ = stderr_join.join();
                return Err(format!("Error waiting for process: {e}"));
            }
        }
    }
}

fn get_workstation_config() -> Value {
    let home = dirs::home_dir().unwrap_or_else(|| PathBuf::from("/home/ebmarah"));
    let config_path = home.join(".config/allthings140radio/visuals.json");
    #[cfg(unix)]
    if config_path.exists() {
        let _ = fs::set_permissions(&config_path, fs::Permissions::from_mode(0o600));
    }
    if let Ok(content) = fs::read_to_string(&config_path) {
        if let Ok(val) = serde_json::from_str::<Value>(&content) {
            return val;
        }
    }
    json!({})
}

fn get_admin_token() -> String {
    let cfg = get_workstation_config();
    cfg["adminToken"].as_str().map(|s| s.to_string())
        .or_else(|| env::var("ADMIN_TOKEN").ok())
        .unwrap_or_default()
}

const APPROVED_STAGING_ORIGINS: &[&str] = &[
    "https://allthings140-visuals-green.pages.dev",
    "https://visuals-media-staging.allthings140radio.online",
    "https://visuals-realtime-staging.allthings140radio.online",
    "https://allthings140radio.online",
    "https://status.ebeinc.online",
];

#[tauri::command]
fn open_staging_url(url: String) -> Result<(), String> {
    validate_staging_url(&url)?;
    Command::new("xdg-open")
        .arg(url)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map(|_| ())
        .map_err(|e| format!("Could not open staging browser: {e}"))
}

fn validate_staging_url(url: &str) -> Result<(), String> {
    let parsed = url::Url::parse(url).map_err(|_| "Invalid staging URL".to_string())?;
    let origin = format!("{}://{}", parsed.scheme(), parsed.host_str().unwrap_or_default());
    if parsed.scheme() != "https" || !APPROVED_STAGING_ORIGINS.iter().any(|allowed| *allowed == origin) {
        return Err("Blocked external URL: only approved HTTPS staging origins are allowed".to_string());
    }
    Ok(())
}

#[tauri::command]
fn get_visual_routing() -> Result<Value, String> {
    let output = Command::new("curl")
        .args(["-fsS", "-m", "5", "-A", "ALLTHINGS140-Workstation/0.1.42", "https://allthings140radio.online/api/visual-routing"])
        .output();
    if let Ok(out) = output {
        if out.status.success() {
            if let Ok(v) = serde_json::from_slice::<Value>(&out.stdout) {
                return Ok(v);
            }
        }
    }
    Ok(json!({ "chat": "legacy", "visuals": "legacy", "source": "fallback" }))
}

#[tauri::command]
fn set_visual_routing(chat: Option<String>, visuals: Option<String>, reason: Option<String>) -> Result<Value, String> {
    let token = get_admin_token();
    let payload = json!({
        "chat": chat,
        "visuals": visuals,
        "reason": reason,
        "action": "workstation_mode_set"
    });
    let payload_str = payload.to_string();
    // Keep the routing credential out of the curl process command line. The
    // workstation's realtime publisher uses the same 0600 header-file pattern.
    let publish_dir = data_dir()?.join("publish-tmp");
    fs::create_dir_all(&publish_dir).map_err(|e| format!("Could not create routing temp dir: {e}"))?;
    let header_path = publish_dir.join(format!("routing-headers-{}.txt", Utc::now().timestamp_millis()));
    fs::write(
        &header_path,
        format!("Authorization: Bearer {token}\nContent-Type: application/json\n").as_bytes(),
    ).map_err(|e| format!("Could not stage routing auth header: {e}"))?;
    #[cfg(unix)]
    let _ = fs::set_permissions(&header_path, fs::Permissions::from_mode(0o600));

    let mut cmd = Command::new("curl");
    cmd.args([
        "-fsS",
        "-m", "8",
        "-A", "ALLTHINGS140-Workstation/0.1.42",
        "-X", "POST",
        "-H", &format!("@{}", header_path.display()),
        "--data-binary", "@-",
        "https://allthings140radio.online/api/visual-routing"
    ])
    .stdin(Stdio::piped())
    .stdout(Stdio::piped())
    .stderr(Stdio::piped());

    let spawn_result = cmd.spawn();
    if spawn_result.is_err() {
        let _ = fs::remove_file(&header_path);
    }
    let mut child = spawn_result.map_err(|e| format!("Failed to spawn curl: {e}"))?;
    if let Some(mut stdin) = child.stdin.take() {
        use std::io::Write;
        if let Err(err) = stdin.write_all(payload_str.as_bytes()) {
            let _ = fs::remove_file(&header_path);
            return Err(format!("Failed writing payload: {err}"));
        }
    }
    let output = child.wait_with_output().map_err(|e| {
        let _ = fs::remove_file(&header_path);
        format!("curl error: {e}")
    })?;
    let _ = fs::remove_file(&header_path);
    if !output.status.success() {
        let err_msg = String::from_utf8_lossy(&output.stderr);
        return Err(format!("Visual routing update failed (HTTP/curl): {err_msg}"));
    }
    let res_val: Value = serde_json::from_slice(&output.stdout)
        .map_err(|e| format!("Visual routing returned invalid JSON: {e}"))?;
    if res_val.get("ok").and_then(|v| v.as_bool()) != Some(true) {
        return Err(format!("Visual routing did not confirm persistence: {}", res_val));
    }
    if let Some(expected_chat) = payload.get("chat").and_then(|v| v.as_str()) {
        let actual = res_val.get("state").and_then(|v| v.get("chat")).and_then(|v| v.as_str()).unwrap_or("");
        if actual != expected_chat {
            return Err(format!("Visual routing confirmation mismatch: requested chat={expected_chat}, got chat={actual}"));
        }
    }
    if let Some(expected_visuals) = payload.get("visuals").and_then(|v| v.as_str()) {
        let actual = res_val.get("state").and_then(|v| v.get("visuals")).and_then(|v| v.as_str()).unwrap_or("");
        if actual != expected_visuals {
            return Err(format!("Visual routing confirmation mismatch: requested visuals={expected_visuals}, got visuals={actual}"));
        }
    }
    Ok(res_val)
}

#[tauri::command]
fn get_visual_health() -> Result<Value, String> {
    // Edge health is useful for routing/KV visibility, but renderer truth lives on
    // the realtime service. Always query renderer-state directly so a missing
    // Worker KV mirror cannot falsely report the live Green Room as offline.
    let edge_health = Command::new("curl")
        .args(["-fsS", "-m", "5", "https://allthings140radio.online/api/visual-health"])
        .output()
        .ok()
        .filter(|o| o.status.success())
        .and_then(|o| serde_json::from_slice::<Value>(&o.stdout).ok())
        .unwrap_or(json!({}));

    let rt_health = Command::new("curl")
        .args(["-fsS", "-m", "4", "https://visuals-realtime-staging.allthings140radio.online/health"])
        .output();
    let rt_ok = rt_health.as_ref().map(|o| o.status.success()).unwrap_or(false);

    let rt_ack = Command::new("curl")
        .args(["-fsS", "-m", "4", "https://visuals-realtime-staging.allthings140radio.online/renderer-state?environment=live-chat"])
        .output();
    let ack_val: Value = rt_ack
        .ok()
        .filter(|o| o.status.success())
        .and_then(|o| serde_json::from_slice(&o.stdout).ok())
        .unwrap_or(json!({}));

    let renderer_online = ack_val
        .get("rendererConnected")
        .and_then(|b| b.as_bool())
        .unwrap_or(false);

    let routing = edge_health
        .get("routing")
        .cloned()
        .unwrap_or(json!({ "status": "unknown" }));

    Ok(json!({
        "ok": rt_ok,
        "vm2": { "status": if rt_ok { "ok" } else { "offline" } },
        "realtime": { "status": if rt_ok { "ok" } else { "offline" } },
        "renderer": {
            "status": if renderer_online { "online" } else { "offline" },
            "ack": ack_val.clone(),
            "environments": ack_val.get("environments").cloned().unwrap_or(json!({}))
        },
        "routing": routing,
        "edge": edge_health
    }))
}

#[tauri::command]
fn append_app_log(level: String, message: String) -> Result<(), String> {
    let dir = data_dir()?.join("logs");
    fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    let path = dir.join("workstation.log");
    if let Ok(meta) = fs::metadata(&path) {
        if meta.len() > 1_000_000 {
            let rotated = dir.join("workstation.log.1");
            let _ = fs::rename(&path, rotated);
        }
    }
    let safe_level = level.chars().filter(|c| c.is_ascii_alphanumeric()).collect::<String>();
    let line = format!("{} [{}] {}\n", Utc::now().to_rfc3339(), safe_level, message.replace('\n', " "));
    let mut file = fs::OpenOptions::new().create(true).append(true).open(path).map_err(|e| e.to_string())?;
    file.write_all(line.as_bytes()).map_err(|e| e.to_string())
}

fn copy_pages_tree(source: &Path, dest: &Path) -> Result<(), String> {
    fs::create_dir_all(dest).map_err(|e| e.to_string())?;
    for entry in fs::read_dir(source).map_err(|e| e.to_string())? {
        let entry = entry.map_err(|e| e.to_string())?;
        let path = entry.path();
        let name = entry.file_name();
        if name == "media" || name == "node_modules" || name == "dist" {
            continue;
        }
        let target = dest.join(&name);
        if path.is_dir() {
            copy_pages_tree(&path, &target)?;
        } else if path.is_file() {
            fs::copy(&path, &target).map_err(|e| e.to_string())?;
        }
    }
    Ok(())
}

fn pages_artifact_stats(root: &Path) -> Result<(u64, u64, String, u64), String> {
    fn walk(path: &Path, count: &mut u64, largest: &mut (u64, String), over: &mut u64) -> Result<(), String> {
        for entry in fs::read_dir(path).map_err(|e| e.to_string())? {
            let entry = entry.map_err(|e| e.to_string())?;
            let p = entry.path();
            if p.is_dir() { walk(&p, count, largest, over)?; continue; }
            if !p.is_file() { continue; }
            let size = fs::metadata(&p).map_err(|e| e.to_string())?.len();
            *count += 1;
            if size > largest.0 { *largest = (size, p.display().to_string()); }
            if size > 24 * 1024 * 1024 { *over += 1; }
        }
        Ok(())
    }
    let mut count = 0; let mut largest = (0, String::new()); let mut over = 0;
    walk(root, &mut count, &mut largest, &mut over)?;
    Ok((count, largest.0, largest.1, over))
}

fn sha256_bytes(bytes: &[u8]) -> Result<String, String> {
    let mut hasher = Sha256::new();
    hasher.update(bytes);
    let result = hasher.finalize();
    Ok(format!("{:064x}", result))
}

fn default_frame_for_kind(kind: &str, role: &str) -> Value {
    if role == "visual" {
        json!({"x":0.0,"y":0.0,"width":100.0,"height":100.0,"scale":1.0,"opacity":1.0,"fit":"cover","visible":true,"flipX":false,"flipY":false})
    } else if role == "stage" {
        json!({"x":0.0,"y":0.0,"width":100.0,"height":100.0,"scale":1.0,"opacity":1.0,"fit":"cover","visible":true,"flipX":false,"flipY":false})
    } else {
        match kind {
            "logo" => json!({"x":10.5,"y":77.0,"width":8.5,"height":9.0,"scale":1.0,"opacity":1.0,"fit":"contain","visible":true,"flipX":false,"flipY":false}),
            "alert" => json!({"x":31.0,"y":82.0,"width":38.0,"height":12.0,"scale":1.0,"opacity":1.0,"fit":"contain","visible":true,"flipX":false,"flipY":false}),
            "presence" => json!({"x":4.0,"y":86.0,"width":28.0,"height":8.0,"scale":1.0,"opacity":1.0,"fit":"contain","visible":true,"flipX":false,"flipY":false}),
            "reactions" => json!({"x":79.0,"y":88.0,"width":17.0,"height":8.0,"scale":1.0,"opacity":1.0,"fit":"contain","visible":true,"flipX":false,"flipY":false}),
            "energy" => json!({"x":83.0,"y":7.0,"width":13.0,"height":10.0,"scale":1.0,"opacity":1.0,"fit":"contain","visible":true,"flipX":false,"flipY":false}),
            _ => json!({"x":0.0,"y":0.0,"width":100.0,"height":100.0,"scale":1.0,"opacity":1.0,"fit":"cover","visible":true,"flipX":false,"flipY":false}),
        }
    }
}

fn frame_for_layer(preset: &Value, layer: &Value) -> Value {
    let id = layer["id"].as_str().unwrap_or_default();
    let kind = layer["kind"].as_str().unwrap_or_default();
    let role = layer["role"].as_str().unwrap_or_default();

    // 1. Directly attached frame object
    if let Some(f) = layer.get("frame").filter(|v| v.is_object()) {
        return f.clone();
    }
    // 2. Direct geometry properties on layer object
    if layer.get("x").is_some() && layer.get("y").is_some() && layer.get("width").is_some() && layer.get("height").is_some() {
        return json!({
            "x": layer["x"].as_f64().unwrap_or(0.0),
            "y": layer["y"].as_f64().unwrap_or(0.0),
            "width": layer["width"].as_f64().unwrap_or(100.0),
            "height": layer["height"].as_f64().unwrap_or(100.0),
            "scale": layer["scale"].as_f64().unwrap_or(1.0),
            "opacity": layer["opacity"].as_f64().unwrap_or(1.0),
            "fit": layer["fit"].as_str().unwrap_or(if kind == "media" { "cover" } else { "contain" }),
            "visible": layer["visible"].as_bool().unwrap_or(true),
            "flipX": layer["flipX"].as_bool().unwrap_or(false),
            "flipY": layer["flipY"].as_bool().unwrap_or(false)
        });
    }
    // 3. Preset layerFrames
    if let Some(f) = preset["layerFrames"].get(id).filter(|v| v.is_object()) {
        return f.clone();
    }
    // 4. Legacy preset keys
    if role == "visual" {
        if let Some(c) = preset["content"].as_object() {
            return Value::Object(c.clone());
        }
    } else if role == "stage" {
        if let Some(s) = preset["stage"].as_object() {
            return Value::Object(s.clone());
        }
    }
    // 5. Default
    default_frame_for_kind(kind, role)
}

static MEDIA_SERVER_URL: OnceLock<String> = OnceLock::new();
static MEDIA_ROUTES: OnceLock<Arc<RwLock<HashMap<String, PathBuf>>>> = OnceLock::new();
static PROBE_CACHE: OnceLock<Arc<RwLock<HashMap<String, (u64, u64, Value)>>>> = OnceLock::new();

fn media_routes() -> Arc<RwLock<HashMap<String, PathBuf>>> {
    MEDIA_ROUTES
        .get_or_init(|| Arc::new(RwLock::new(HashMap::new())))
        .clone()
}

fn probe_cache() -> Arc<RwLock<HashMap<String, (u64, u64, Value)>>> {
    PROBE_CACHE
        .get_or_init(|| Arc::new(RwLock::new(HashMap::new())))
        .clone()
}

fn probe_media_cached(path: &Path) -> Value {
    let key = path.to_string_lossy().to_string();
    let meta = match fs::metadata(path) {
        Ok(m) => m,
        Err(_) => return json!({}),
    };
    let modified = meta
        .modified()
        .ok()
        .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
        .map(|d| d.as_millis() as u64)
        .unwrap_or(0);
    let size = meta.len();
    if let Ok(cache) = probe_cache().read() {
        if let Some((cached_modified, cached_size, value)) = cache.get(&key) {
            if *cached_modified == modified && *cached_size == size {
                return value.clone();
            }
        }
    }
    if let Ok(dir) = data_dir() {
        let index_path = dir.join("media-index.json");
        if let Ok(raw) = fs::read_to_string(&index_path) {
            if let Ok(index) = serde_json::from_str::<Value>(&raw) {
                if let Some(item) = index.get(&key) {
                    let item_mod = item["modified"].as_u64().unwrap_or(0);
                    let item_size = item["size"].as_u64().unwrap_or(0);
                    // Match either millisecond or legacy nanosecond timestamp
                    let mod_matches = item_mod == modified || (item_mod / 1_000_000) == modified;
                    if mod_matches && item_size == size && item.get("value").is_some() {
                        let value = item["value"].clone();
                        if let Ok(mut cache) = probe_cache().write() {
                            cache.insert(key.clone(), (modified, size, value.clone()));
                        }
                        return value;
                    }
                }
            }
        }
    }
    let value = probe_media_blocking(key.clone()).unwrap_or_else(|_| json!({}));
    if let Ok(mut cache) = probe_cache().write() {
        cache.insert(key.clone(), (modified, size, value.clone()));
    }
    if let Ok(dir) = data_dir() {
        let index_path = dir.join("media-index.json");
        let mut index = fs::read_to_string(&index_path)
            .ok()
            .and_then(|raw| serde_json::from_str::<Value>(&raw).ok())
            .filter(Value::is_object)
            .unwrap_or_else(|| json!({}));
        index[&key] = json!({"modified":modified,"size":size,"value":value});
        if let Ok(raw) = serde_json::to_vec(&index) { let _ = fs::write(index_path, raw); }
    }
    value
}

fn mime(path: &Path) -> &'static str {
    match path
        .extension()
        .and_then(|x| x.to_str())
        .unwrap_or("")
        .to_ascii_lowercase()
        .as_str()
    {
        "webm" => "video/webm",
        "mov" => "video/quicktime",
        "m4v" => "video/x-m4v",
        "gif" => "image/gif",
        _ => "video/mp4",
    }
}

fn start_server() -> Result<String, String> {
    if let Some(url) = MEDIA_SERVER_URL.get() {
        return Ok(url.clone());
    }

    let routes = media_routes();
    let listener = TcpListener::bind("127.0.0.1:0").map_err(|e| e.to_string())?;
    let port = listener.local_addr().map_err(|e| e.to_string())?.port();

    thread::spawn(move || {
        for stream in listener.incoming().flatten() {
            let routes = routes.clone();
            thread::spawn(move || {
                let mut stream = stream;
                let mut buf = [0u8; 16384];
                let n = stream.read(&mut buf).unwrap_or(0);
                let req = String::from_utf8_lossy(&buf[..n]);
                let mut lines = req.lines();
                let request_line = lines.next().unwrap_or("");
                let mut parts = request_line.split_whitespace();
                let method = parts.next().unwrap_or("");
                let target = parts.next().unwrap_or("");
                let id = target
                    .split('?')
                    .next()
                    .unwrap_or("")
                    .trim_start_matches('/')
                    .strip_prefix("media/")
                    .unwrap_or("");

                let file = routes.read().ok().and_then(|m| m.get(id).cloned());
                let Some(file) = file else {
                    let _ = stream.write_all(
                        b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n",
                    );
                    return;
                };

                let Ok(meta) = fs::metadata(&file) else {
                    let _ = stream.write_all(
                        b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n",
                    );
                    return;
                };
                let len = meta.len();
                if len == 0 {
                    let _ = stream.write_all(
                        b"HTTP/1.1 416 Range Not Satisfiable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n",
                    );
                    return;
                }

                let range = req.lines().find_map(|h| {
                    let (k, v) = h.split_once(':')?;
                    if k.eq_ignore_ascii_case("range") {
                        Some(v.trim().strip_prefix("bytes=")?.to_string())
                    } else {
                        None
                    }
                });

                let mut start = 0u64;
                let mut end = len.saturating_sub(1);
                let mut status = "200 OK";
                if let Some(spec) = range {
                    if let Some((a, b)) = spec.split_once('-') {
                        if let Ok(x) = a.parse::<u64>() {
                            start = x.min(end);
                            if !b.is_empty() {
                                if let Ok(y) = b.parse::<u64>() {
                                    end = y.min(end);
                                }
                            }
                            status = "206 Partial Content";
                        }
                    }
                }

                if start > end {
                    let _ = stream.write_all(
                        format!(
                            "HTTP/1.1 416 Range Not Satisfiable\r\nContent-Range: bytes */{len}\r\nConnection: close\r\n\r\n"
                        )
                        .as_bytes(),
                    );
                    return;
                }

                let count = end - start + 1;
                let content_type = mime(&file);
                let headers = if status == "206 Partial Content" {
                    format!(
                        "HTTP/1.1 {status}\r\nContent-Type: {content_type}\r\nContent-Length: {count}\r\nContent-Range: bytes {start}-{end}/{len}\r\nAccept-Ranges: bytes\r\nConnection: close\r\n\r\n"
                    )
                } else {
                    format!(
                        "HTTP/1.1 {status}\r\nContent-Type: {content_type}\r\nContent-Length: {len}\r\nAccept-Ranges: bytes\r\nConnection: close\r\n\r\n"
                    )
                };
                let _ = stream.write_all(headers.as_bytes());

                if method == "GET" {
                    if let Ok(mut f) = fs::File::open(file) {
                        let _ = f.seek(SeekFrom::Start(start));
                        let mut take = f.take(count);
                        let _ = std::io::copy(&mut take, &mut stream);
                    }
                }
            });
        }
    });

    let url = format!("http://127.0.0.1:{port}");
    let _ = MEDIA_SERVER_URL.set(url.clone());
    Ok(url)
}

#[tauri::command]
fn start_media_server() -> Result<String, String> {
    start_server()
}

fn data_dir() -> Result<PathBuf, String> {
    let p = dirs::data_dir()
        .ok_or("No data directory")?
        .join("allthings140radio-visuals");
    fs::create_dir_all(&p).map_err(|e| e.to_string())?;
    Ok(p)
}

fn state_path() -> Result<PathBuf, String> {
    Ok(data_dir()?.join("workstation.json"))
}

fn prune_version_backups(dir: &Path, keep: usize) {
    let Ok(entries) = fs::read_dir(dir) else { return; };
    let mut files: Vec<PathBuf> = entries
        .filter_map(Result::ok)
        .map(|e| e.path())
        .filter(|p| p.is_file() && p.file_name().and_then(|x| x.to_str()).is_some_and(|n| n.starts_with("workstation-") && n.ends_with(".json")))
        .collect();
    files.sort();
    if files.len() <= keep { return; }
    let remove_count = files.len() - keep;
    for path in files.into_iter().take(remove_count) {
        let _ = fs::remove_file(path);
    }
}

fn newest_valid_state_backup(dir: &Path) -> Option<Value> {
    let entries = fs::read_dir(dir).ok()?;
    let mut files: Vec<PathBuf> = entries
        .filter_map(Result::ok)
        .map(|e| e.path())
        .filter(|p| p.is_file() && p.file_name().and_then(|x| x.to_str()).is_some_and(|n| n.starts_with("workstation-") && n.ends_with(".json")))
        .collect();
    files.sort_by(|a, b| b.cmp(a));
    for path in files {
        let Ok(raw) = fs::read(&path) else { continue; };
        if let Ok(mut value) = serde_json::from_slice::<Value>(&raw) {
            value["recoveredFromBackup"] = Value::String(path.display().to_string());
            return Some(value);
        }
    }
    None
}

fn default_state() -> Value {
    json!({
        "schema": 3,
        "layoutVersion": 1,
        "environment": "staging",
        "canonicalComposition": {"width":1920,"height":1080,"aspectRatio":"16:9"},
        "activePreset": "Known Good Default",
        "presets": [{
            "name":"Known Good Default",
            "version":1,
            "viewport":"desktop-16-9",
            "content":{"x":0,"y":0,"width":100,"height":100,"scale":1,"opacity":1,"fit":"cover","visible":true,"flipX":false,"flipY":false},
            "stage":{"x":0,"y":0,"width":100,"height":100,"scale":1,"opacity":1,"fit":"cover","visible":true,"flipX":false,"flipY":false},
            "safeArea":false,
            "screenOpening":{"x":23.0,"y":33.5,"width":53.6,"height":48.5,"rx":1.5,"enabled":true},
            "layerFrames":{
                "visual-content":{"x":0.0,"y":0.0,"width":100.0,"height":100.0,"scale":1.0,"opacity":1.0,"fit":"cover","visible":true,"flipX":false,"flipY":false},
                "stage-content":{"x":0.0,"y":0.0,"width":100.0,"height":100.0,"scale":1.0,"opacity":1.0,"fit":"cover","visible":true,"flipX":false,"flipY":false},
                "station-logo":{"x":10.5,"y":77.0,"width":8.5,"height":9.0,"scale":1.0,"opacity":1.0,"fit":"contain","visible":true,"flipX":false,"flipY":false},
                "now-playing":{"x":31.0,"y":82.0,"width":38.0,"height":12.0,"scale":1.0,"opacity":1.0,"fit":"contain","visible":true,"flipX":false,"flipY":false},
                "presence-bubbles":{"x":4.0,"y":86.0,"width":28.0,"height":8.0,"scale":1.0,"opacity":1.0,"fit":"contain","visible":true,"flipX":false,"flipY":false},
                "reactions":{"x":79.0,"y":88.0,"width":17.0,"height":8.0,"scale":1.0,"opacity":1.0,"fit":"contain","visible":true,"flipX":false,"flipY":false},
                "room-energy":{"x":83.0,"y":7.0,"width":13.0,"height":10.0,"scale":1.0,"opacity":1.0,"fit":"contain","visible":true,"flipX":false,"flipY":false}
            }
        }],
        "playlist":[],
        "takeovers":[],
        "activity":[],
        "publishedVersion":0
    })
}

#[tauri::command]
fn load_state() -> Result<Value, String> {
    let p = state_path()?;
    if !p.exists() {
        let v = default_state();
        fs::write(&p, serde_json::to_vec_pretty(&v).unwrap()).map_err(|e| e.to_string())?;
        return Ok(v);
    }
    let raw = fs::read(&p).map_err(|e| e.to_string())?;
    match serde_json::from_slice::<Value>(&raw) {
        Ok(v) => Ok(v),
        Err(primary_err) => {
            let versions = data_dir()?.join("versions");
            if let Some(v) = newest_valid_state_backup(&versions) {
                return Ok(v);
            }
            Err(format!("Workstation state is invalid JSON and no valid backup could be recovered: {primary_err}"))
        }
    }
}

#[tauri::command]
fn save_state(state: Value) -> Result<Value, String> {
    let p = state_path()?;
    let versions = data_dir()?.join("versions");
    fs::create_dir_all(&versions).map_err(|e| e.to_string())?;
    if p.exists() {
        fs::copy(
            &p,
            versions.join(format!(
                "workstation-{}.json",
                Utc::now().format("%Y%m%dT%H%M%S%3fZ")
            )),
        )
        .map_err(|e| e.to_string())?;
    }
    let tmp = p.with_extension("tmp");
    fs::write(
        &tmp,
        serde_json::to_vec_pretty(&state).map_err(|e| e.to_string())?,
    )
    .map_err(|e| e.to_string())?;
    fs::rename(tmp, p).map_err(|e| e.to_string())?;
    prune_version_backups(&versions, 120);
    Ok(json!({"ok":true,"savedAt":Utc::now().to_rfc3339()}))
}

fn probe_media_blocking(path: String) -> Result<Value, String> {
    let meta = fs::metadata(&path).map_err(|e| format!("File unavailable: {e}"))?;
    if meta.len() == 0 {
        return Ok(json!({"status":"PROBLEM","reason":"Zero-byte file","path":path}));
    }
    let mut cmd = Command::new("ffprobe");
    cmd.args([
        "-v",
        "error",
        "-show_entries",
        "format=duration,format_name,size:stream=index,codec_name,codec_type,width,height,r_frame_rate",
        "-of",
        "json",
        &path,
    ]);
    let out = run_cmd_with_timeout(cmd, 5, None)?;
    if !out.status.success() {
        return Ok(json!({
            "status":"PROBLEM",
            "reason":String::from_utf8_lossy(&out.stderr),
            "path":path
        }));
    }
    let mut v: Value = serde_json::from_slice(&out.stdout).map_err(|e| e.to_string())?;
    let codec = v["streams"]
        .as_array()
        .and_then(|a| a.iter().find(|s| s["codec_type"] == "video"))
        .and_then(|s| s["codec_name"].as_str())
        .unwrap_or("");
    let compatible = matches!(codec, "h264" | "vp8" | "vp9" | "av1");
    v["status"] = json!(if compatible { "READY" } else { "PROBLEM" });
    v["reason"] = json!(if compatible {
        "Browser-compatible video"
    } else {
        "Unsupported browser codec; runtime conversion required"
    });
    v["path"] = json!(path);
    Ok(v)
}

#[tauri::command]
async fn probe_media(path: String) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || probe_media_blocking(path))
        .await
        .map_err(|e| format!("Probe worker failed: {e}"))?
}

#[tauri::command]
fn optimize_media(source: String, destination: String) -> Result<Value, String> {
    if Path::new(&source) == Path::new(&destination) {
        return Err("Destination must not overwrite source".into());
    }
    let mut cmd = Command::new("ffmpeg");
    cmd.args([
        "-y",
        "-i",
        &source,
        "-map",
        "0:v:0",
        "-an",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-crf",
        "21",
        "-preset",
        "medium",
        &destination,
    ]);
    let out = run_cmd_with_timeout(cmd, 120, None)?;
    if !out.status.success() {
        return Err(format!("ffmpeg optimization failed: {}", String::from_utf8_lossy(&out.stderr)));
    }
    probe_media_blocking(destination)
}

fn source_fingerprint(path: &Path) -> Result<String, String> {
    let canonical = fs::canonicalize(path).map_err(|e| e.to_string())?;
    let meta = fs::metadata(&canonical).map_err(|e| e.to_string())?;
    let modified = meta
        .modified()
        .ok()
        .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
        .map(|d| d.as_nanos())
        .unwrap_or(0);
    let mut hasher = DefaultHasher::new();
    canonical.to_string_lossy().hash(&mut hasher);
    meta.len().hash(&mut hasher);
    modified.hash(&mut hasher);
    Ok(format!("{:016x}", hasher.finish()))
}

fn valid_video(path: &Path) -> bool {
    path.is_file()
        && path
            .extension()
            .and_then(|x| x.to_str())
            .is_some_and(|x| matches!(x.to_ascii_lowercase().as_str(), "mp4" | "mov" | "webm" | "mkv" | "m4v" | "gif"))
}

fn needs_runtime_conversion(path: &Path, probe: &Value) -> bool {
    let codec = probe["streams"]
        .as_array()
        .and_then(|a| a.iter().find(|s| s["codec_type"] == "video"))
        .and_then(|s| s["codec_name"].as_str())
        .unwrap_or("");
    let ext = path
        .extension()
        .and_then(|x| x.to_str())
        .unwrap_or("")
        .to_ascii_lowercase();
    !(codec == "h264" && matches!(ext.as_str(), "mp4" | "m4v"))
        && !(matches!(codec, "vp8" | "vp9" | "av1") && ext == "webm")
}

fn scan_layer_media_blocking(layer_id: String, folder: String) -> Result<Value, String> {
    let folder_path = fs::canonicalize(&folder).map_err(|e| format!("Media folder unavailable: {e}"))?;
    if !folder_path.is_dir() {
        return Err("Selected media path is not a folder".into());
    }

    let mut files: Vec<PathBuf> = fs::read_dir(&folder_path)
        .map_err(|e| e.to_string())?
        .filter_map(Result::ok)
        .map(|e| e.path())
        .filter(|p| valid_video(p))
        .collect();
    files.sort();

    let routes = media_routes();
    let cache_dir = data_dir()?.join("media-cache").join("by-source");
    fs::create_dir_all(&cache_dir).map_err(|e| e.to_string())?;

    let mut items = Vec::new();
    for source in files.iter() {
        let source_probe = probe_media_cached(source);
        let source_video = source_probe["streams"]
            .as_array()
            .and_then(|a| a.iter().find(|s| s["codec_type"] == "video"));

        let fingerprint = source_fingerprint(source)?;
        let route_id = format!("source-{fingerprint}");
        let mut runtime = source.clone();
        let converted = needs_runtime_conversion(source, &source_probe);
        if converted {
            runtime = cache_dir.join(format!("{fingerprint}.mp4"));
            let refresh = if !runtime.exists() {
                true
            } else {
                let sm = fs::metadata(source).and_then(|m| m.modified()).ok();
                let rm = fs::metadata(&runtime).and_then(|m| m.modified()).ok();
                matches!((sm, rm), (Some(a), Some(b)) if a > b)
            };
            if refresh {
                let mut ffmpeg = Command::new("ffmpeg");
                ffmpeg.args([
                    "-y",
                    "-i",
                    source.to_str().ok_or("Invalid media source path")?,
                    "-map",
                    "0:v:0",
                    "-an",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-movflags",
                    "+faststart",
                    "-crf",
                    "21",
                    "-preset",
                    "veryfast",
                    runtime.to_str().ok_or("Invalid runtime media path")?,
                ]);
                let out = run_cmd_with_timeout(ffmpeg, 180, None)?;
                if !out.status.success() {
                    return Err(format!(
                        "Media runtime conversion failed for {}: {}",
                        source.display(),
                        String::from_utf8_lossy(&out.stderr)
                    ));
                }
            }
        }

        let runtime_probe = probe_media_cached(&runtime);
        let runtime_video = runtime_probe["streams"]
            .as_array()
            .and_then(|a| a.iter().find(|s| s["codec_type"] == "video"));
        if let Ok(mut map) = routes.write() {
            map.insert(route_id.clone(), runtime.clone());
        }
        let name = source.file_name().and_then(|x| x.to_str()).unwrap_or("media");
        items.push(json!({
            "routeId": route_id,
            "name": name,
            "source": name,
            "sourcePath": source,
            "runtimePath": runtime,
            "converted": converted,
            "duration": runtime_probe["format"]["duration"],
            "width": source_video.and_then(|v|v["width"].as_u64()).unwrap_or(0),
            "height": source_video.and_then(|v|v["height"].as_u64()).unwrap_or(0),
            "runtimeWidth": runtime_video.and_then(|v|v["width"].as_u64()).unwrap_or(0),
            "runtimeHeight": runtime_video.and_then(|v|v["height"].as_u64()).unwrap_or(0),
            "codec": runtime_video.and_then(|v|v["codec_name"].as_str()).unwrap_or("unknown"),
            "sourceCodec": source_video.and_then(|v|v["codec_name"].as_str()).unwrap_or("unknown"),
            "status": if runtime.exists() {"READY"} else {"PROBLEM"}
        }));
    }

    Ok(json!({
        "layerId": layer_id,
        "folder": folder_path,
        "count": items.len(),
        "items": items
    }))
}

#[tauri::command]
async fn scan_layer_media(layer_id: String, folder: String) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || scan_layer_media_blocking(layer_id, folder))
        .await
        .map_err(|e| format!("Media scan worker failed: {e}"))?
}

fn import_default_media_blocking() -> Result<Value, String> {
    let visual_source = PathBuf::from("/home/ebmarah/Videos/at140radio/desktop visuals/visuals");
    let project = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(Path::parent)
        .ok_or("Project root unavailable")?
        .to_path_buf();
    let optimized = project.join("visuals-green/media/playlist");
    let mut originals: Vec<PathBuf> = fs::read_dir(&visual_source)
        .map_err(|e| e.to_string())?
        .filter_map(Result::ok)
        .map(|e| e.path())
        .filter(|p| p.extension().and_then(|x| x.to_str()).is_some_and(|x| x.eq_ignore_ascii_case("mp4")))
        .collect();
    originals.sort();

    let mut items = Vec::new();
    for (i, path) in originals.iter().enumerate() {
        let probe = probe_media_cached(path);
        let video = probe["streams"]
            .as_array()
            .and_then(|a| a.iter().find(|s| s["codec_type"] == "video"));
        let id = format!("visual-{:03}", i + 1);
        let local = optimized.join(format!("{id}.mp4"));
        items.push(json!({
            "mediaType":"visual",
            "id":id,
            "name":path.file_name().and_then(|x| x.to_str()).unwrap_or("visual"),
            "sourcePath":path,
            "runtimePath":if local.exists() { local.clone() } else { path.clone() },
            "publicUrl":format!("/media/playlist/{id}.mp4"),
            "status":if local.exists() || path.exists() {"READY"} else {"PROBLEM"},
            "duration":probe["format"]["duration"],
            "width":video.and_then(|v|v["width"].as_u64()).unwrap_or(0),
            "height":video.and_then(|v|v["height"].as_u64()).unwrap_or(0),
            "codec":video.and_then(|v|v["codec_name"].as_str()).unwrap_or("unknown")
        }));
    }

    Ok(json!({
        "count": items.len(),
        "source": visual_source,
        "items": items
    }))
}

#[tauri::command]
async fn import_default_media() -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(import_default_media_blocking)
        .await
        .map_err(|e| format!("Import default media worker failed: {e}"))?
}

#[tauri::command]
fn export_report() -> Result<Value, String> {
    let now = Utc::now();
    let dir = dirs::document_dir()
        .or_else(dirs::home_dir)
        .ok_or("No user documents folder")?
        .join("ALLTHINGS140Radio Reports");
    fs::create_dir_all(&dir).map_err(|e| e.to_string())?;

    let filename = format!("visuals-report-{}.json", now.format("%Y%m%dT%H%M%SZ"));
    let path = dir.join(filename);

    let state = load_state().unwrap_or_else(|_| json!({}));
    let payload = json!({
        "generatedAt": now.to_rfc3339(),
        "app": "ALLTHINGS140Radio Visuals",
        "version": env!("CARGO_PKG_VERSION"),
        "state": state
    });

    fs::write(
        &path,
        serde_json::to_vec_pretty(&payload).map_err(|e| e.to_string())?,
    )
    .map_err(|e| e.to_string())?;

    Ok(json!({
        "ok": true,
        "path": path
    }))
}

fn publish_staging_blocking(state: Value) -> Result<Value, String> {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(Path::parent)
        .ok_or("Project root unavailable")?
        .to_path_buf();
    let green = root.join("visuals-green");
    if !green.join("robots.txt").exists() {
        return Err("Refusing publish: green staging directory not found".into());
    }
    let pages_dist = root.join("visuals-green-pages-dist");
    if pages_dist.canonicalize().ok() == green.canonicalize().ok() {
        return Err("Unsafe Pages deployment path: the source GREEN tree contains large media. Use visuals-green-pages-dist.".into());
    }
    let media_origin = env::var("VISUALS_MEDIA_ORIGIN")
        .unwrap_or_else(|_| "https://visuals-media-staging.allthings140radio.online".to_string())
        .trim_end_matches('/').to_string();
    let media_target = env::var("VISUALS_MEDIA_SSH_TARGET")
        .unwrap_or_else(|_| "opc@100.74.121.38".to_string());
    let remote_root = env::var("VISUALS_MEDIA_REMOTE_ROOT")
        .unwrap_or_else(|_| "/srv/allthings140-visuals/media".to_string());
    let stage_media = green.join("media/stage");
    let visual_media = green.join("media/playlist");
    let mut phases = json!({"mediaSync":"PENDING","pagesArtifact":"PENDING","pagesDeploy":"PENDING","greenHealth":"PENDING"});

    let sync_stage = Command::new("rsync")
        .args(["-az", "--partial", "--checksum", "--omit-dir-times", "--no-perms", &format!("{}/", stage_media.display()), &format!("{}:{}/stage/", media_target, remote_root)])
        .output().map_err(|e| format!("Media sync failed to start: {e}"))?;
    if !sync_stage.status.success() { return Err(format!("Stage media sync failed: {}", String::from_utf8_lossy(&sync_stage.stderr))); }
    let sync_visuals = Command::new("rsync")
        .args(["-az", "--partial", "--checksum", "--omit-dir-times", "--no-perms", &format!("{}/", visual_media.display()), &format!("{}:{}/visuals/", media_target, remote_root)])
        .output().map_err(|e| format!("Media sync failed to start: {e}"))?;
    if !sync_visuals.status.success() { return Err(format!("Visual media sync failed: {}", String::from_utf8_lossy(&sync_visuals.stderr))); }
    phases["mediaSync"] = Value::String("PASS".into());

    let stage_probe = stage_media.join("stage-0001.mp4");
    if stage_probe.exists() {
        let local_bytes = fs::read(&stage_probe).map_err(|e| e.to_string())?;
        let expected = sha256_bytes(&local_bytes)?;
        let remote_path = format!("{remote_root}/stage/stage-0001.mp4");
        let remote_hash = Command::new("ssh").args([&media_target, "sha256sum", &remote_path]).output().map_err(|e| e.to_string())?;
        let actual = String::from_utf8_lossy(&remote_hash.stdout).split_whitespace().next().unwrap_or("").to_string();
        if !remote_hash.status.success() || expected.is_empty() || expected != actual { return Err(format!("Remote stage-0001 hash mismatch (local={expected}, remote={actual})")); }
        let remote_url = format!("{media_origin}/stage/stage-0001.mp4");
        let head = Command::new("curl").args(["-fsSI", &remote_url]).output().map_err(|e| e.to_string())?;
        if !head.status.success() { return Err(format!("Remote stage-0001 HEAD failed: {}", String::from_utf8_lossy(&head.stderr))); }
        let range = Command::new("curl").args(["-fsS", "-H", "Range: bytes=0-1048575", "-o", "/tmp/at140-stage-range-test.bin", "-D", "/tmp/at140-stage-range-test.headers", &remote_url]).output().map_err(|e| e.to_string())?;
        if !range.status.success() { return Err(format!("Remote stage-0001 Range failed: {}", String::from_utf8_lossy(&range.stderr))); }
        let headers = fs::read_to_string("/tmp/at140-stage-range-test.headers").unwrap_or_default();
        if !headers.contains("206") || !headers.to_ascii_lowercase().contains("accept-ranges") { return Err("Remote stage-0001 did not return a valid 206 Range response".into()); }
    }

    if pages_dist.exists() { fs::remove_dir_all(&pages_dist).map_err(|e| e.to_string())?; }
    copy_pages_tree(&green, &pages_dist)?;

    let preset = state["presets"]
        .as_array()
        .and_then(|p| p.iter().find(|x| x["name"] == state["activePreset"]))
        .ok_or("Active preset missing")?;

    let rewrite_media_url = |url: &str| -> String {
        if url.starts_with("/media/stage/") { format!("{}/stage/{}", media_origin, url.trim_start_matches("/media/stage/")) }
        else if url.starts_with("/media/playlist/") { format!("{}/visuals/{}", media_origin, url.trim_start_matches("/media/playlist/")) }
        else { url.to_string() }
    };

    let revision = Utc::now().format("%Y%m%dT%H%M%S%3fZ").to_string();
    let screen_opening = state.get("screenOpening")
        .cloned()
        .or_else(|| preset.get("screenOpening").cloned())
        .unwrap_or_else(|| json!({"x":23.0,"y":33.5,"width":53.6,"height":48.5,"rx":1.5,"enabled":true}));

    let mut layers = Vec::new();
    for layer in state["workspaceLayers"].as_array().ok_or("workspaceLayers missing")? {
        let frame = frame_for_layer(preset, layer);
        let mut published = json!({
            "id":layer["id"], "name":layer["name"], "kind":layer["kind"], "role":layer["role"], "z":layer["z"],
            "x":frame["x"], "y":frame["y"], "width":frame["width"], "height":frame["height"], "scale":frame["scale"],
            "fit":frame["fit"], "opacity":frame["opacity"], "visible":frame["visible"], "flipX":frame["flipX"], "flipY":frame["flipY"]
        });
        if layer["kind"] == "media" {
            let selected = if layer["selectedMedia"].is_object() { layer["selectedMedia"].clone() } else {
                if layer["role"] == "stage" { state["activeStage"].clone() } else {
                    let idx = layer["mediaIndex"].as_u64().unwrap_or(0) as usize;
                    state["playlist"].as_array().and_then(|p| p.get(idx)).cloned().unwrap_or_else(|| json!({}))
                }
            };
            let raw_url = selected["publicUrl"].as_str().unwrap_or_default();
            published["media"] = json!({
                "id":selected["id"].as_str().or_else(|| selected["name"].as_str()).unwrap_or(layer["id"].as_str().unwrap_or("media")),
                "name":selected["name"],
                "sourcePath":selected["sourcePath"],
                "runtimePath":selected["runtimePath"],
                "fingerprint":selected["fingerprint"],
                "url":rewrite_media_url(raw_url)
            });
        }
        layers.push(published);
    }

    let canonical = json!({
        "schemaVersion":2,
        "revision":revision,
        "layoutId":format!("layout-{revision}"),
        "publishedAt":Utc::now().to_rfc3339(),
        "composition":{"width":1920,"height":1080,"aspectRatio":"16:9"},
        "screenOpening":screen_opening,
        "layers":layers,
        "mediaBaseUrl":media_origin,
        "playlist":state.get("playlist").cloned().unwrap_or_else(|| json!([])),
        "fallback":{"id":"known-good-fallback","url":"https://allthings140radio.online/assets/visuals-phone.mp4?v=1.1.0","fit":"cover"},
        "productionLocked":true
    });

    let canonical_bytes = serde_json::to_vec(&canonical).map_err(|e| e.to_string())?;
    let layout_hash = sha256_bytes(&canonical_bytes)?;
    let mut published = canonical;
    published["layoutHash"] = Value::String(layout_hash.clone());
    published["layoutRevision"] = Value::String(revision.clone());
    published["previewMode"] = state["previewMode"].clone();
    if state["previewVisual"].is_object() {
        let mut pv = state["previewVisual"].clone();
        if let Some(url) = pv["url"].as_str() { pv["url"] = Value::String(rewrite_media_url(url)); }
        published["previewVisual"] = pv;
    }
    published["version"] = state["layoutVersion"].clone();
    published["legacyPreset"] = preset.clone();

    fs::write(pages_dist.join("layout.json"), serde_json::to_vec_pretty(&published).unwrap())
        .map_err(|e| e.to_string())?;

    let (file_count, largest_size, largest_path, over_limit) = pages_artifact_stats(&pages_dist)?;
    if over_limit > 0 {
        return Err(format!("Pages artifact rejected locally: {over_limit} files exceed 24 MiB; largest={largest_path} ({largest_size} bytes)"));
    }
    phases["pagesArtifact"] = Value::String("PASS".into());

    let out = Command::new("npx")
        .current_dir(&root)
        .args([
            "wrangler",
            "pages",
            "deploy",
            "visuals-green-pages-dist",
            "--project-name",
            "allthings140-visuals-green",
            "--branch",
            "staging",
            "--commit-dirty=true",
        ])
        .output()
        .map_err(|e| e.to_string())?;
    if !out.status.success() {
        return Err(format!(
            "Staging deploy failed: {}",
            String::from_utf8_lossy(&out.stderr)
        ));
    }
    phases["pagesDeploy"] = Value::String("PASS".into());

    let deploy_output = String::from_utf8_lossy(&out.stdout).to_string();
    let deployment_url = deploy_output
        .split_whitespace()
        .map(|s| s.trim_matches(|c: char| c == '(' || c == ')' || c == ','))
        .find(|s| s.starts_with("https://") && s.contains(".pages.dev"))
        .unwrap_or("https://allthings140-visuals-green.pages.dev")
        .trim_end_matches('/')
        .to_string();
    let green_health_url = "https://allthings140-visuals-green.pages.dev/?approval=1";
    let green_health = Command::new("curl")
        .args(["-fsSI", green_health_url])
        .output()
        .map_err(|e| format!("GREEN health check failed to start: {e}"))?;
    if !green_health.status.success() {
        return Err(format!("GREEN health check failed: {}", String::from_utf8_lossy(&green_health.stderr)));
    }

    let manifest_url = format!("{deployment_url}/layout.json?verify={revision}");
    let remote_manifest = Command::new("curl")
        .args(["-fsS", &manifest_url])
        .output()
        .map_err(|e| format!("Remote manifest check failed to start: {e}"))?;
    if !remote_manifest.status.success() { return Err(format!("Remote manifest check failed: {}", String::from_utf8_lossy(&remote_manifest.stderr))); }
    let remote_json: Value = serde_json::from_slice(&remote_manifest.stdout).map_err(|e| format!("Remote manifest JSON invalid: {e}"))?;
    if remote_json["layoutRevision"] != published["layoutRevision"] || remote_json["layoutHash"] != published["layoutHash"] {
        return Err(format!("Remote manifest mismatch (expected revision/hash {}/{}, got {}/{})", published["layoutRevision"], published["layoutHash"], remote_json["layoutRevision"], remote_json["layoutHash"]));
    }
    phases["greenHealth"] = Value::String("PASS".into());

    Ok(json!({
        "ok":true,
        "version":state["layoutVersion"],
        "output":String::from_utf8_lossy(&out.stdout),
        "productionTouched":false,
        "pagesDeployDirectory":pages_dist.display().to_string(),
        "pagesFileCount":file_count,
        "pagesLargestFile":largest_path,
        "pagesLargestBytes":largest_size,
        "mediaOrigin":media_origin,
        "phases":phases,
        "greenHealthUrl":green_health_url,
        "deploymentUrl":deployment_url,
        "manifestUrl":manifest_url,
        "layoutRevision":published["layoutRevision"],
        "layoutHash":published["layoutHash"],
        "remoteManifest":"PASS"
    }))
}

fn compute_fingerprint(path: &Path) -> Result<String, String> {
    source_fingerprint(path)
}

fn validate_single_media_blocking(payload: Value) -> Result<Value, String> {
    let job_id = payload["jobId"].as_str().map(|s| s.to_string());
    let role = payload["role"].as_str().unwrap_or("media");
    let path_str = payload["sourcePath"].as_str()
        .or_else(|| payload["path"].as_str())
        .or_else(|| payload["runtimePath"].as_str())
        .unwrap_or_default();

    if path_str.is_empty() {
        return Ok(json!({
            "status": "EMPTY",
            "role": role,
            "error": format!("No {role} media path configured"),
            "valid": false
        }));
    }

    if is_job_cancelled(job_id.as_deref()) {
        return Err("Validation cancelled by user".into());
    }

    let t0 = Instant::now();
    let path = PathBuf::from(path_str);
    let meta = match fs::metadata(&path) {
        Ok(m) => m,
        Err(e) => {
            return Ok(json!({
                "status": "NOT_FOUND",
                "role": role,
                "path": path_str,
                "error": format!("File unavailable on disk: {e}"),
                "valid": false
            }));
        }
    };
    let stat_ms = t0.elapsed().as_secs_f64() * 1000.0;

    let size = meta.len();
    if size == 0 {
        return Ok(json!({
            "status": "PROBLEM",
            "role": role,
            "path": path_str,
            "error": "File is 0 bytes",
            "valid": false
        }));
    }

    let t1 = Instant::now();
    let probe = probe_media_cached(&path);
    let probe_ms = t1.elapsed().as_secs_f64() * 1000.0;

    if is_job_cancelled(job_id.as_deref()) {
        return Err("Validation cancelled by user".into());
    }

    let video = probe["streams"].as_array().and_then(|a| a.iter().find(|s| s["codec_type"] == "video"));
    let codec = video.and_then(|v| v["codec_name"].as_str()).unwrap_or("unknown");
    let width = video.and_then(|v| v["width"].as_u64()).unwrap_or(0);
    let height = video.and_then(|v| v["height"].as_u64()).unwrap_or(0);
    let duration = probe["format"]["duration"].as_str().unwrap_or("0");
    let status = probe["status"].as_str().unwrap_or(if width > 0 && height > 0 { "READY" } else { "PROBLEM" });
    let reason = probe["reason"].as_str().unwrap_or("");
    let fingerprint = source_fingerprint(&path).unwrap_or_else(|_| "media-fp".into());

    let mut final_status = status.to_string();
    let mut final_reason = reason.to_string();

    let runtime_path_str = payload["runtimePath"].as_str().unwrap_or(path_str);
    let runtime_path = PathBuf::from(runtime_path_str);
    let runtime_exists = runtime_path.exists();

    if final_status != "READY" && runtime_exists && runtime_path != path {
        let r_probe = probe_media_cached(&runtime_path);
        if r_probe["status"] == "READY" {
            final_status = "READY".to_string();
            final_reason = "Browser-compatible runtime copy ready".to_string();
        }
    }

    let total_ms = t0.elapsed().as_secs_f64() * 1000.0;

    Ok(json!({
        "status": final_status,
        "role": role,
        "name": payload["name"].as_str().or_else(|| path.file_name().and_then(|x| x.to_str())).unwrap_or(role),
        "sourcePath": path_str,
        "runtimePath": runtime_path_str,
        "runtimeExists": runtime_exists,
        "codec": codec,
        "width": width,
        "height": height,
        "duration": duration,
        "size": size,
        "fingerprint": fingerprint,
        "reason": final_reason,
        "valid": width > 0 && height > 0,
        "timings": {
            "statMs": stat_ms,
            "probeMs": probe_ms,
            "totalMs": total_ms
        }
    }))
}

fn validate_selected_media_blocking(payload: Value) -> Result<Value, String> {
    let job_id = payload["jobId"].as_str().map(|s| s.to_string());
    
    if is_job_cancelled(job_id.as_deref()) {
        return Err("Validation cancelled by user".into());
    }

    let t0 = Instant::now();
    let (stage_val, visual_val) = if payload["stage"].is_object() && payload["visual"].is_object() {
        (payload["stage"].clone(), payload["visual"].clone())
    } else {
        let layers = payload["workspaceLayers"].as_array();
        // Strict canonical ID matching — never fall back to name/role/position
        let stage_l = layers.and_then(|a| a.iter().find(|x| x["id"] == "stage-content"));
        let visual_l = layers.and_then(|a| a.iter().find(|x| x["id"] == "visual-content"));
        let s_obj = stage_l.and_then(|l| if l["selectedMedia"].is_object() { Some(l["selectedMedia"].clone()) } else { payload.get("activeStage").cloned() }).unwrap_or_else(|| json!({}));
        let v_obj = visual_l.and_then(|l| if l["selectedMedia"].is_object() { Some(l["selectedMedia"].clone()) } else {
            let idx = l["mediaIndex"].as_u64().unwrap_or(0) as usize;
            payload["playlist"].as_array().and_then(|p| p.get(idx)).cloned()
        }).unwrap_or_else(|| json!({}));
        (s_obj, v_obj)
    };

    let mut stage_payload = stage_val;
    if let Some(jid) = &job_id { stage_payload["jobId"] = json!(jid); }
    stage_payload["role"] = json!("stage");
    let stage_info = validate_single_media_blocking(stage_payload)?;

    if is_job_cancelled(job_id.as_deref()) {
        return Err("Validation cancelled by user".into());
    }

    let mut visual_payload = visual_val;
    if let Some(jid) = &job_id { visual_payload["jobId"] = json!(jid); }
    visual_payload["role"] = json!("visual");
    let visual_info = validate_single_media_blocking(visual_payload)?;

    let total_ms = t0.elapsed().as_secs_f64() * 1000.0;

    Ok(json!({
        "ok": true,
        "stage": stage_info,
        "visual": visual_info,
        "totalMs": total_ms
    }))
}

fn runtime_media_extension(path: &Path) -> &'static str {
    match path.extension().and_then(|x| x.to_str()).unwrap_or("").to_ascii_lowercase().as_str() {
        "webm" => "webm",
        "mp4" | "m4v" => "mp4",
        // Runtime conversion should normally prevent these from reaching staging, but keep
        // a conservative fallback rather than lying about the file type.
        _ => "mp4",
    }
}

fn playlist_local_path(item: &Value) -> Option<PathBuf> {
    for key in ["runtimePath", "sourcePath", "path"] {
        if let Some(raw) = item.get(key).and_then(|v| v.as_str()).filter(|s| !s.is_empty()) {
            let candidate = PathBuf::from(raw);
            if candidate.exists() { return Some(candidate); }
        }
    }
    None
}

fn safe_playlist_asset_id(item: &Value, local_path: Option<&Path>) -> Result<String, String> {
    let raw = item.get("assetId").and_then(|v| v.as_str())
        .or_else(|| item.get("routeId").and_then(|v| v.as_str()))
        .or_else(|| item.get("id").and_then(|v| v.as_str()))
        .or_else(|| item.get("fingerprint").and_then(|v| v.as_str()))
        .unwrap_or("");
    let cleaned: String = raw.chars()
        .filter(|c| c.is_ascii_alphanumeric() || *c == '-' || *c == '_')
        .take(96)
        .collect();
    if !cleaned.is_empty() { return Ok(cleaned); }
    if let Some(path) = local_path {
        return Ok(format!("source-{}", compute_fingerprint(path)?));
    }
    Err(format!("Enabled playlist item '{}' has no stable asset ID or local media path", item.get("name").and_then(|v| v.as_str()).unwrap_or("visual")))
}

fn compact_playlist_for_green(state: &Value, media_origin: &str) -> Result<Value, String> {
    let Some(items) = state.get("playlist").and_then(|v| v.as_array()) else { return Ok(json!([])); };
    let mut out = Vec::new();
    for item in items {
        if item.get("enabled").and_then(|v| v.as_bool()) == Some(false) { continue; }
        let explicit_url = item.get("publicUrl").and_then(|v| v.as_str())
            .or_else(|| item.get("url").and_then(|v| v.as_str()))
            .filter(|u| u.starts_with("https://"));
        let local_path = playlist_local_path(item);
        let id = safe_playlist_asset_id(item, local_path.as_deref())?;
        // A local runtime/source file is authoritative for workstation-managed
        // playlist entries. Prefer its content-addressed staging URL over any
        // stale persisted publicUrl from an earlier publish.
        let url = if let Some(path) = local_path.as_deref() {
            let ext = runtime_media_extension(path);
            format!("{}/visuals/{}.{}", media_origin.trim_end_matches('/'), id, ext)
        } else if let Some(u) = explicit_url {
            u.to_string()
        } else {
            return Err(format!("Enabled playlist item '{}' has neither a verified HTTPS URL nor a local runtime/source file", item.get("name").and_then(|v| v.as_str()).unwrap_or(&id)));
        };
        out.push(json!({
            "id": id,
            "name": item.get("name").and_then(|v| v.as_str()).unwrap_or("visual"),
            "url": url,
            "fit": item.get("fit").and_then(|v| v.as_str()).unwrap_or("cover"),
            "duration": item.get("duration").cloned().unwrap_or(Value::Null),
            "enabled": true
        }));
    }
    Ok(Value::Array(out))
}

fn publish_layout_fast_blocking(payload: Value) -> Result<Value, String> {
    let state = if payload["state"].is_object() { &payload["state"] } else { &payload };
    let job_id = payload["jobId"].as_str().or_else(|| state["jobId"].as_str()).map(|s| s.to_string());

    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(Path::parent)
        .ok_or("Project root unavailable")?
        .to_path_buf();
    let green = root.join("visuals-green");

    let config = get_workstation_config();
    let media_origin = config["mediaOrigin"].as_str()
        .map(|s| s.to_string())
        .or_else(|| env::var("VISUALS_MEDIA_ORIGIN").ok())
        .unwrap_or_else(|| "https://visuals-media-staging.allthings140radio.online".to_string())
        .trim_end_matches('/').to_string();
    let media_target = config["sshTarget"].as_str()
        .map(|s| s.to_string())
        .or_else(|| env::var("VISUALS_MEDIA_SSH_TARGET").ok())
        .unwrap_or_else(|| "opc@100.74.121.38".to_string());
    let remote_root = config["remoteRoot"].as_str()
        .map(|s| s.to_string())
        .or_else(|| env::var("VISUALS_MEDIA_REMOTE_ROOT").ok())
        .unwrap_or_else(|| "/srv/allthings140-visuals/media".to_string());
    let admin_token = get_admin_token();

    if admin_token.is_empty() {
        return Err("REALTIME AUTH NOT CONFIGURED: No admin token found in workstation config or env".into());
    }

    let preset = state["presets"]
        .as_array()
        .and_then(|p| p.iter().find(|x| x["name"] == state["activePreset"]))
        .ok_or("Active preset missing")?;

    let revision = Utc::now().format("%Y%m%dT%H%M%S%3fZ").to_string();
    let screen_opening = state.get("screenOpening")
        .cloned()
        .or_else(|| preset.get("screenOpening").cloned())
        .unwrap_or_else(|| json!({"x":23.0,"y":33.5,"width":53.6,"height":48.5,"rx":1.5,"enabled":true}));

    let mut layers = Vec::new();
    let mut media_to_sync: Vec<(PathBuf, String, String, String)> = Vec::new();
    let mut preview_visual_obj: Option<Value> = None;
    let mut stage_asset_id: Option<String> = None;
    let mut visual_asset_id: Option<String> = None;
    let is_preview = state["previewMode"].as_bool().unwrap_or(true);

    // 3A/3B: Resolve canonical stage and visual layer IDs strictly
    let _canonical_stage = state["workspaceLayers"].as_array()
        .and_then(|a| a.iter().find(|x| x["id"] == "stage-content"));
    let _canonical_visual = state["workspaceLayers"].as_array()
        .and_then(|a| a.iter().find(|x| x["id"] == "visual-content"));

    for layer in state["workspaceLayers"].as_array().ok_or("workspaceLayers missing")? {
        let frame = frame_for_layer(preset, layer);
        let mut published = json!({
            "id":layer["id"], "name":layer["name"], "kind":layer["kind"], "role":layer["role"], "z":layer["z"],
            "x":frame["x"], "y":frame["y"], "width":frame["width"], "height":frame["height"], "scale":frame["scale"],
            "fit":frame["fit"], "opacity":frame["opacity"], "visible":frame["visible"], "flipX":frame["flipX"], "flipY":frame["flipY"]
        });
        if layer["kind"] == "media" {
            // Strict canonical resolution: only selectedMedia from the canonical layer
            let selected = if layer["selectedMedia"].is_object() { layer["selectedMedia"].clone() } else {
                if layer["id"] == "stage-content" { state["activeStage"].clone() } else {
                    let idx = layer["mediaIndex"].as_u64().unwrap_or(0) as usize;
                    state["playlist"].as_array().and_then(|p| p.get(idx)).cloned().unwrap_or_else(|| json!({}))
                }
            };

            let local_path_str = selected["runtimePath"].as_str()
                .or_else(|| selected["sourcePath"].as_str())
                .or_else(|| selected["path"].as_str())
                .unwrap_or_default();
            
            let local_path = PathBuf::from(local_path_str);
            let fingerprint = if let Some(fp) = selected["fingerprint"].as_str() {
                fp.to_string()
            } else if local_path.exists() {
                compute_fingerprint(&local_path).unwrap_or_else(|_| "media".into())
            } else {
                "media".into()
            };

            let sub = if layer["id"] == "stage-content" { "stage" } else { "visuals" };
            let ext = runtime_media_extension(&local_path);
            let asset_filename = format!("{fingerprint}.{ext}");
            let manifest_url = format!("{media_origin}/{sub}/{asset_filename}");

            // Never leak workstation-local paths into the Green/realtime data contract.
            published["media"] = json!({
                "id": fingerprint,
                "assetId": fingerprint,
                "name": selected["name"].as_str().unwrap_or(layer["id"].as_str().unwrap_or("media")),
                "fingerprint": fingerprint,
                "url": manifest_url,
                "contentType": if ext == "webm" { "video/webm" } else { "video/mp4" }
            });

            if layer["id"] == "stage-content" {
                stage_asset_id = Some(fingerprint.clone());
            }
            if layer["id"] == "visual-content" {
                visual_asset_id = Some(fingerprint.clone());
            }

            if local_path.exists() {
                media_to_sync.push((local_path, sub.to_string(), fingerprint.clone(), asset_filename.clone()));
            }

            if layer["id"] == "visual-content" {
                preview_visual_obj = Some(json!({
                    "assetId": fingerprint,
                    "url": manifest_url,
                    "fit": frame["fit"].as_str().unwrap_or("cover"),
                    "fingerprint": fingerprint
                }));
            }
        }
        layers.push(published);
    }

    // A non-preview publish is the 24/7 contract, so every enabled local playlist
    // item must be present on the media origin before we advertise its URL. Preview
    // tests intentionally sync only the selected Stage + Visual for speed.
    if !is_preview {
        if let Some(items) = state.get("playlist").and_then(|v| v.as_array()) {
            for item in items {
                if item.get("enabled").and_then(|v| v.as_bool()) == Some(false) { continue; }
                let external_https = item.get("publicUrl").and_then(|v| v.as_str())
                    .or_else(|| item.get("url").and_then(|v| v.as_str()))
                    .filter(|u| u.starts_with("https://"));
                if let Some(local_path) = playlist_local_path(item) {
                    let asset_id = safe_playlist_asset_id(item, Some(&local_path))?;
                    let ext = runtime_media_extension(&local_path);
                    let asset_filename = format!("{asset_id}.{ext}");
                    let duplicate = media_to_sync.iter().any(|(_, sub, _, file)| sub == "visuals" && file == &asset_filename);
                    if !duplicate {
                        media_to_sync.push((local_path, "visuals".to_string(), asset_id, asset_filename));
                    }
                } else if external_https.is_none() {
                    return Err(format!("24/7 PRE-FLIGHT FAILED: enabled playlist item '{}' has neither a local source/runtime path nor an HTTPS URL", item.get("name").and_then(|v| v.as_str()).unwrap_or("visual")));
                }
            }
        }
    }

    // 3C-3F: Check if assets already exist on staging media origin before rsync
    let mut uploaded = 0u32;
    let mut cached = 0u32;
    for (src, sub, asset_id, asset_filename) in &media_to_sync {
        if is_job_cancelled(job_id.as_deref()) {
            return Err("Publish cancelled by user".into());
        }

        let check_url = format!("{media_origin}/{sub}/{asset_filename}");
        // 3C/3D: HEAD check — skip rsync if asset already exists
        let mut head = Command::new("curl");
        head.args(["-fsSI", "-m", "5", &check_url]);
        let head_result = run_cmd_with_timeout(head, 6, job_id.as_deref());

        match head_result {
            Ok(ref head_out) if head_out.status.success() => {
                // Asset already exists on remote — skip upload
                cached += 1;
                continue;
            }
            _ => {
                // 3E: Asset missing — rsync upload
                let dest = format!("{}:{}/{}/{}", media_target, remote_root, sub, asset_filename);
                let mut rsync = Command::new("rsync");
                rsync.args(["-az", "--partial", "--timeout=10", src.to_str().unwrap(), &dest]);
                // Preview publishes must remain snappy; a full 24/7 rollout may need to
                // pre-stage a large uncached asset, so give rsync more wall-clock time.
                let upload_timeout_secs = if is_preview { 15 } else { 90 };
                let out = run_cmd_with_timeout(rsync, upload_timeout_secs, job_id.as_deref())?;
                if !out.status.success() {
                    return Err(format!("Media sync failed for {asset_id}: {}", String::from_utf8_lossy(&out.stderr)));
                }
                uploaded += 1;

                // 3F: Verify upload via HEAD
                let mut head2 = Command::new("curl");
                head2.args(["-fsSI", "-m", "5", &check_url]);
                let head2_out = run_cmd_with_timeout(head2, 6, job_id.as_deref())?;
                if !head2_out.status.success() {
                    return Err(format!("Remote media URL {check_url} failed HEAD check after upload: {}", String::from_utf8_lossy(&head2_out.stderr)));
                }
            }
        }
    }

    let playlist_contract = if is_preview { json!([]) } else { compact_playlist_for_green(state, &media_origin)? };
    let mut canonical = json!({
        "schemaVersion": 2,
        "revision": revision,
        "layoutId": format!("layout-{revision}"),
        "publishedAt": Utc::now().to_rfc3339(),
        "composition": { "width": 1920, "height": 1080, "aspectRatio": "16:9" },
        "screenOpening": screen_opening,
        "layers": layers,
        "mediaBaseUrl": media_origin,
        "playlist": playlist_contract,
        "fallback": { "id": "known-good-fallback", "url": "https://allthings140radio.online/assets/visuals-phone.mp4?v=1.1.0", "fit": "cover" },
        "previewMode": is_preview,
        "safePlaybackMode": state.get("safePlaybackMode").and_then(|v| v.as_bool()).unwrap_or(false),
        "productionLocked": true
    });

    if is_preview && preview_visual_obj.is_some() {
        canonical["previewVisual"] = preview_visual_obj.clone().unwrap();
    }

    let canonical_bytes = serde_json::to_vec(&canonical).map_err(|e| e.to_string())?;
    let layout_hash = sha256_bytes(&canonical_bytes)?;
    canonical["layoutHash"] = Value::String(layout_hash.clone());
    canonical["layoutRevision"] = Value::String(revision.clone());

    if green.exists() {
        let _ = fs::write(green.join("layout.json"), serde_json::to_vec_pretty(&canonical).unwrap());
    }

    // 3I-3L: Realtime gateway publish. Keep the realtime payload compact and send
    // it from a file rather than as a command-line argument (avoids ARG_MAX and shell/log exposure).
    let payload_str = serde_json::to_string(&canonical).map_err(|e| e.to_string())?;
    let payload_bytes = payload_str.as_bytes().len();
    const MAX_LAYOUT_BYTES: usize = 128 * 1024;
    if payload_bytes > MAX_LAYOUT_BYTES {
        return Err(format!("REALTIME_PAYLOAD_TOO_LARGE: canonical layout is {payload_bytes} bytes (limit {MAX_LAYOUT_BYTES}); preview/test layouts must not include workstation state or binary media"));
    }
    let publish_dir = data_dir()?.join("publish-tmp");
    fs::create_dir_all(&publish_dir).map_err(|e| e.to_string())?;
    let file_tag = job_id.as_deref().unwrap_or("publish")
        .chars()
        .filter(|c| c.is_ascii_alphanumeric() || *c == '-' || *c == '_')
        .take(80)
        .collect::<String>();
    let payload_path = publish_dir.join(format!("layout-{file_tag}.json"));
    let header_path = publish_dir.join(format!("headers-{file_tag}.txt"));
    let response_path = publish_dir.join(format!("response-{file_tag}.json"));
    fs::write(&payload_path, payload_str.as_bytes()).map_err(|e| format!("Could not stage realtime payload: {e}"))?;
    fs::write(
        &header_path,
        format!("Content-Type: application/json\nAuthorization: Bearer {admin_token}\n").as_bytes(),
    ).map_err(|e| format!("Could not stage realtime auth header: {e}"))?;
    #[cfg(unix)]
    let _ = fs::set_permissions(&header_path, fs::Permissions::from_mode(0o600));

    let realtime_url = "https://visuals-realtime-staging.allthings140radio.online/admin/layout";
    let mut post_cmd = Command::new("curl");
    post_cmd.args([
        "-sS",
        "-m", "10",
        "-o", response_path.to_str().ok_or("Invalid realtime response path")?,
        "-w", "%{http_code}",
        "-X", "POST",
        "-H", &format!("@{}", header_path.display()),
        "--data-binary", &format!("@{}", payload_path.display()),
        realtime_url
    ]);
    let post_result = run_cmd_with_timeout(post_cmd, 12, job_id.as_deref());
    let _ = fs::remove_file(&payload_path);
    let _ = fs::remove_file(&header_path);
    let post_res = match post_result {
        Ok(value) => value,
        Err(err) => {
            let _ = fs::remove_file(&response_path);
            return Err(err);
        }
    };
    let status_text = String::from_utf8_lossy(&post_res.stdout).trim().to_string();
    let http_status = status_text.parse::<u16>().unwrap_or(0);
    let response_body = fs::read_to_string(&response_path).unwrap_or_default();
    let _ = fs::remove_file(&response_path);
    if !post_res.status.success() || !(200..300).contains(&http_status) {
        return Err(format!("REALTIME_HTTP_{http_status}: realtime layout broadcast failed (payload={payload_bytes} bytes): {}", response_body.chars().take(300).collect::<String>()));
    }

    Ok(json!({
        "ok": true,
        "version": state["layoutVersion"],
        "layoutRevision": canonical["layoutRevision"],
        "layoutHash": canonical["layoutHash"],
        "mediaOrigin": media_origin,
        "stageAssetId": stage_asset_id,
        "visualAssetId": visual_asset_id,
        "previewMode": is_preview,
        "previewVisual": canonical.get("previewVisual"),
        "payloadBytes": payload_bytes,
        "realtimeHttpStatus": http_status,
        "phases": {
            "validation": "PASS",
            "snapshot": "PASS",
            "stageAssetCheck": "PASS",
            "visualAssetCheck": "PASS",
            "mediaUpload": format!("{} cached, {} uploaded", cached, uploaded),
            "realtimePublish": "PASS"
        }
    }))
}

#[tauri::command]
fn cancel_staging_publish(job_id: String) -> Result<Value, String> {
    if let Ok(mut set) = get_cancelled_jobs().lock() {
        set.insert(job_id.clone());
    }
    Ok(json!({ "ok": true, "cancelled": job_id }))
}

#[tauri::command]
async fn validate_single_media(payload: Value) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || validate_single_media_blocking(payload))
        .await
        .map_err(|e| format!("Validate single media worker failed: {e}"))?
}

#[tauri::command]
async fn validate_selected_media(payload: Value) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || validate_selected_media_blocking(payload))
        .await
        .map_err(|e| format!("Validate selected media worker failed: {e}"))?
}

#[tauri::command]
async fn publish_layout_fast(payload: Value) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || publish_layout_fast_blocking(payload))
        .await
        .map_err(|e| format!("Publish layout fast worker failed: {e}"))?
}

#[tauri::command]
async fn publish_staging(state: Value) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || publish_staging_blocking(state))
        .await
        .map_err(|e| format!("Publish staging worker failed: {e}"))?
}

fn schedule_takeover_blocking(schedule: Value) -> Result<Value, String> {
    let key = dirs::home_dir()
        .ok_or("Home directory unavailable")?
        .join(".ssh/allthings140_visuals_realtime_ed25519");
    if !key.exists() {
        return Err("Dedicated Visuals server SSH key is unavailable".into());
    }
    let remote = "set -a; . /etc/allthings140-visuals/realtime.env; set +a; curl -fsS -X POST -H \"Authorization: Bearer $ADMIN_TOKEN\" -H 'Content-Type: application/json' --data-binary @- http://127.0.0.1:8765/admin/schedule";
    let mut child = Command::new("ssh")
        .args([
            "-i",
            key.to_str().ok_or("Invalid SSH key path")?,
            "-o",
            "BatchMode=yes",
            "opc@163.192.1.208",
            "sudo",
            "bash",
            "-lc",
            remote,
        ])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| e.to_string())?;
    child
        .stdin
        .as_mut()
        .ok_or("SSH input unavailable")?
        .write_all(&serde_json::to_vec(&schedule).map_err(|e| e.to_string())?)
        .map_err(|e| e.to_string())?;
    let out = child.wait_with_output().map_err(|e| e.to_string())?;
    if !out.status.success() {
        return Err(format!(
            "Server schedule failed: {}",
            String::from_utf8_lossy(&out.stderr)
        ));
    }
    serde_json::from_slice(&out.stdout).map_err(|e| format!("Invalid schedule response: {e}"))
}

#[tauri::command]
async fn schedule_takeover(schedule: Value) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || schedule_takeover_blocking(schedule))
        .await
        .map_err(|e| format!("Schedule takeover worker failed: {e}"))?
}

#[tauri::command]
fn app_info() -> Value {
    json!({
        "name":"ALLTHINGS140Radio Visuals",
        "version":env!("CARGO_PKG_VERSION"),
        "gitCommit":option_env!("AT140_GIT_COMMIT").unwrap_or("unknown"),
        "buildUnix":option_env!("AT140_BUILD_UNIX").unwrap_or("0"),
        "environment":"STAGING",
        "production":"LOCKED — NOT READY FOR CUTOVER"
    })
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            load_state,
            save_state,
            probe_media,
            optimize_media,
            import_default_media,
            start_media_server,
            open_staging_url,
            append_app_log,
            scan_layer_media,
            export_report,
            cancel_staging_publish,
            validate_selected_media,
            validate_single_media,
            publish_layout_fast,
            publish_staging,
            schedule_takeover,
            app_info,
            get_visual_routing,
            set_visual_routing,
            get_visual_health
        ])
        .run(tauri::generate_context!())
        .expect("Visuals workstation failed")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn browser_allowlist_accepts_green_staging() {
        assert!(validate_staging_url("https://allthings140-visuals-green.pages.dev/?approval=1").is_ok());
        assert!(validate_staging_url("https://allthings140-visuals-green.pages.dev/layout.json").is_ok());
    }

    #[test]
    fn browser_allowlist_accepts_approved_origins() {
        assert!(validate_staging_url("https://visuals-media-staging.allthings140radio.online/stage/stage-0001.mp4").is_ok());
        assert!(validate_staging_url("https://visuals-realtime-staging.allthings140radio.online/health").is_ok());
        assert!(validate_staging_url("https://allthings140radio.online/room/?approval=1").is_ok());
    }

    #[test]
    fn browser_allowlist_rejects_arbitrary_commands_and_origins() {
        assert!(validate_staging_url("file:///etc/passwd").is_err());
        assert!(validate_staging_url("https://example.com/").is_err());
        assert!(validate_staging_url("http://allthings140-visuals-green.pages.dev/").is_err());
        assert!(validate_staging_url("https://allthings140-visuals-green.pages.dev.evil.example/").is_err());
    }

    #[test]
    fn default_state_structure_integrity() {
        let state = default_state();
        assert_eq!(state["schema"], 3);
        assert_eq!(state["environment"], "staging");
        assert_eq!(state["canonicalComposition"]["width"], 1920);
        assert_eq!(state["canonicalComposition"]["height"], 1080);
        assert!(state["presets"].is_array());
    }

    #[test]
    fn frame_for_layer_fallback() {
        let preset = json!({
            "name": "Test",
            "layerFrames": {
                "custom-1": {"x": 10, "y": 20, "width": 80, "height": 60, "scale": 1, "fit": "cover", "opacity": 1, "visible": true, "flipX": false, "flipY": false}
            }
        });
        let layer = json!({"id": "custom-1", "kind": "media", "role": "media"});
        let frame = frame_for_layer(&preset, &layer);
        assert_eq!(frame["x"], 10);
        assert_eq!(frame["y"], 20);

        let logo_layer = json!({"id": "station-logo", "kind": "logo", "role": "logo"});
        let logo_frame = frame_for_layer(&preset, &logo_layer);
        assert_eq!(logo_frame["x"], 10.5);
        assert_eq!(logo_frame["y"], 77.0);
        assert_eq!(logo_frame["width"], 8.5);
        assert_eq!(logo_frame["height"], 9.0);
    }

    #[test]
    fn sha256_in_memory_hash() {
        let test_bytes = b"ALLTHINGS140-RADIO";
        let hash = sha256_bytes(test_bytes).expect("Hashing should succeed");
        assert_eq!(hash.len(), 64);
    }

    #[test]
    fn valid_video_format_filter() {
        let temp_dir = std::env::temp_dir().join("at140-video-tests-2");
        let _ = fs::create_dir_all(&temp_dir);

        let mp4 = temp_dir.join("test.mp4");
        let webm = temp_dir.join("test.webm");
        let txt = temp_dir.join("test.txt");

        fs::write(&mp4, b"test").unwrap();
        fs::write(&webm, b"test").unwrap();
        fs::write(&txt, b"test").unwrap();

        assert!(valid_video(&mp4));
        assert!(valid_video(&webm));
        assert!(!valid_video(&txt));

        let _ = fs::remove_file(mp4);
        let _ = fs::remove_file(webm);
        let _ = fs::remove_file(txt);
        let _ = fs::remove_dir(temp_dir);
    }

    #[test]
    fn validate_stage_media_only() {
        let stage_path = "/home/ebmarah/Videos/at140radio/desktop visuals/stage/alpha2-transparent-screen.webm";
        if Path::new(stage_path).exists() {
            let res = validate_single_media_blocking(json!({
                "role": "stage",
                "sourcePath": stage_path,
                "name": "alpha2-transparent-screen.webm"
            })).expect("Stage validation should succeed");
            assert_eq!(res["status"], "READY");
            assert!(res["valid"].as_bool().unwrap());
            assert!(res["size"].as_u64().unwrap() > 0);
            assert!(res["width"].as_u64().unwrap() > 0);
        }
    }

    #[test]
    fn validate_visual_media_only() {
        let visual_path = "/home/ebmarah/Videos/at140radio/desktop visuals/visuals/87.mp4";
        if Path::new(visual_path).exists() {
            let res = validate_single_media_blocking(json!({
                "role": "visual",
                "sourcePath": visual_path,
                "name": "87.mp4"
            })).expect("Visual validation should succeed");
            assert_eq!(res["status"], "READY");
            assert!(res["valid"].as_bool().unwrap());
            assert_eq!(res["codec"], "h264");
            assert_eq!(res["width"], 1920);
            assert_eq!(res["height"], 1080);
        }
    }

    #[test]
    fn validate_combined_stage_and_visual() {
        let stage_path = "/home/ebmarah/Videos/at140radio/desktop visuals/stage/alpha2-transparent-screen.webm";
        let visual_path = "/home/ebmarah/Videos/at140radio/desktop visuals/visuals/87.mp4";
        if Path::new(stage_path).exists() && Path::new(visual_path).exists() {
            let res = validate_selected_media_blocking(json!({
                "stage": { "sourcePath": stage_path, "name": "alpha2-transparent-screen.webm" },
                "visual": { "sourcePath": visual_path, "name": "87.mp4" }
            })).expect("Combined validation should succeed");
            assert!(res["ok"].as_bool().unwrap());
            assert_eq!(res["stage"]["status"], "READY");
            assert_eq!(res["visual"]["status"], "READY");
        }
    }

    #[test]
    fn validate_deliberately_invalid_media_does_not_hang() {
        let res = validate_single_media_blocking(json!({
            "role": "visual",
            "sourcePath": "/tmp/nonexistent_corrupt_test_file_12345.mp4",
            "name": "invalid.mp4"
        })).expect("Should return error status cleanly without panic");
        assert_eq!(res["status"], "NOT_FOUND");
        assert_eq!(res["valid"], false);
    }

    #[test]
    fn benchmark_10_consecutive_runs() {
        let stage_path = "/home/ebmarah/Videos/at140radio/desktop visuals/stage/alpha2-transparent-screen.webm";
        let visual_path = "/home/ebmarah/Videos/at140radio/desktop visuals/visuals/87.mp4";

        println!("\n=== BENCHMARK: 10 CONSECUTIVE VALIDATION RUNS ===");
        let mut times = Vec::new();
        for i in 1..=10 {
            let t0 = Instant::now();
            let res = validate_selected_media_blocking(json!({
                "stage": { "sourcePath": stage_path, "name": "alpha2-transparent-screen.webm" },
                "visual": { "sourcePath": visual_path, "name": "87.mp4" }
            })).expect("Run must succeed");
            let elapsed_ms = t0.elapsed().as_secs_f64() * 1000.0;
            times.push(elapsed_ms);
            println!("Run {}: {:.2}ms (status: stage={}, visual={})", i, elapsed_ms, res["stage"]["status"], res["visual"]["status"]);
        }
        let avg: f64 = times.iter().sum::<f64>() / (times.len() as f64);
        println!("Average validation time: {:.2}ms", avg);
        assert!(avg < 50.0, "Average validation time should be fast (< 50ms)");
    }
}
