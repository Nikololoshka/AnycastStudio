use serde::Serialize;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Duration;
use tokio::sync::{oneshot, Notify};

#[derive(Serialize, Clone)]
pub struct OAuthCallbackParams {
    pub code: Option<String>,
    pub state: Option<String>,
    pub error: Option<String>,
}

pub type PendingCallback = oneshot::Receiver<OAuthCallbackParams>;

#[derive(Default)]
pub struct OAuthCallbackState {
    pending: Mutex<Option<PendingCallback>>,
    listener: Mutex<Option<Arc<tiny_http::Server>>>,
    cancelled: Arc<Notify>,
    cancel_requested: AtomicBool,
}

fn percent_decode(value: &str) -> String {
    let bytes = value.as_bytes();
    let mut out = Vec::with_capacity(bytes.len());
    let mut i = 0;
    while i < bytes.len() {
        match bytes[i] {
            b'+' => {
                out.push(b' ');
                i += 1;
            }
            b'%' if i + 2 < bytes.len() => {
                let hex = std::str::from_utf8(&bytes[i + 1..i + 3]).unwrap_or("");
                match u8::from_str_radix(hex, 16) {
                    Ok(byte) => {
                        out.push(byte);
                        i += 3;
                    }
                    Err(_) => {
                        out.push(bytes[i]);
                        i += 1;
                    }
                }
            }
            byte => {
                out.push(byte);
                i += 1;
            }
        }
    }
    String::from_utf8_lossy(&out).into_owned()
}

fn parse_callback_query(url: &str) -> OAuthCallbackParams {
    let query = url.split_once('?').map(|(_, query)| query).unwrap_or("");
    let mut params = OAuthCallbackParams {
        code: None,
        state: None,
        error: None,
    };
    for pair in query.split('&') {
        let Some((key, value)) = pair.split_once('=') else {
            continue;
        };
        let value = percent_decode(value);
        match key {
            "code" => params.code = Some(value),
            "state" => params.state = Some(value),
            "error" => params.error = Some(value),
            _ => {}
        }
    }
    params
}

pub const CANCELLED_MESSAGE: &str = "OAuth sign-in was cancelled";

const CALLBACK_PAGE: &str =
    "<html><body>Sign-in complete. You may close this window.</body></html>";

fn spawn_callback_listener(
    server: Arc<tiny_http::Server>,
    sender: oneshot::Sender<OAuthCallbackParams>,
) {
    std::thread::spawn(move || {
        for request in server.incoming_requests() {
            let params = parse_callback_query(request.url());
            if params.code.is_none() && params.error.is_none() {
                log::debug!("ignoring loopback request without OAuth parameters");
                let _ = request.respond(tiny_http::Response::empty(404));
                continue;
            }
            let response = tiny_http::Response::from_string(CALLBACK_PAGE).with_header(
                tiny_http::Header::from_bytes(&b"Content-Type"[..], &b"text/html"[..]).unwrap(),
            );
            let _ = request.respond(response);
            match (&params.code, &params.error) {
                (_, Some(error)) => log::warn!("OAuth redirect returned error: {error}"),
                (Some(code), None) => log::info!(
                    "OAuth redirect received authorization code ({})",
                    crate::logging::redact(code)
                ),
                _ => {}
            }
            let _ = sender.send(params);
            return;
        }
    });
}

fn arm_callback_server(
    server: tiny_http::Server,
    state: &tauri::State<'_, OAuthCallbackState>,
) -> Result<(), String> {
    let server = Arc::new(server);
    let (sender, receiver) = oneshot::channel();

    state.cancel_requested.store(false, Ordering::SeqCst);
    *state.pending.lock().map_err(|error| error.to_string())? = Some(receiver);
    *state.listener.lock().map_err(|error| error.to_string())? = Some(server.clone());

    spawn_callback_listener(server, sender);
    Ok(())
}

#[tauri::command]
pub fn start_oauth_callback_server(
    state: tauri::State<'_, OAuthCallbackState>,
) -> Result<u16, String> {
    let server = tiny_http::Server::http("127.0.0.1:0").map_err(|error| {
        log::error!("cannot bind OAuth loopback server: {error}");
        error.to_string()
    })?;
    let port = server
        .server_addr()
        .to_ip()
        .ok_or("loopback server has no IP address")?
        .port();

    arm_callback_server(server, &state)?;
    log::info!("OAuth loopback server listening on ephemeral port {port}");

    Ok(port)
}

#[tauri::command]
pub fn start_fixed_port_oauth_callback_server(
    port: u16,
    state: tauri::State<'_, OAuthCallbackState>,
) -> Result<u16, String> {
    let server = tiny_http::Server::http(format!("127.0.0.1:{port}")).map_err(|error| {
        log::error!("cannot bind OAuth loopback server to port {port}: {error}");
        error.to_string()
    })?;

    arm_callback_server(server, &state)?;
    log::info!("OAuth loopback server listening on fixed port {port}");

    Ok(port)
}

#[tauri::command]
pub fn cancel_oauth_callback(state: tauri::State<'_, OAuthCallbackState>) -> Result<(), String> {
    if let Some(server) = state
        .listener
        .lock()
        .map_err(|error| error.to_string())?
        .take()
    {
        server.unblock();
    }
    state
        .pending
        .lock()
        .map_err(|error| error.to_string())?
        .take();
    state.cancel_requested.store(true, Ordering::SeqCst);
    state.cancelled.notify_waiters();
    log::info!("OAuth sign-in cancelled by user");
    Ok(())
}

#[tauri::command]
pub async fn await_oauth_callback(
    state: tauri::State<'_, OAuthCallbackState>,
    timeout_secs: u64,
) -> Result<OAuthCallbackParams, String> {
    let receiver = state
        .pending
        .lock()
        .map_err(|error| error.to_string())?
        .take()
        .ok_or_else(|| {
            log::error!("await_oauth_callback called without a running callback server");
            "no OAuth callback server is running".to_string()
        })?;
    if state.cancel_requested.load(Ordering::SeqCst) {
        return Err(CANCELLED_MESSAGE.to_string());
    }
    let cancelled = state.cancelled.clone();

    log::debug!("waiting up to {timeout_secs}s for the OAuth redirect");
    let outcome = tokio::select! {
        result = tokio::time::timeout(Duration::from_secs(timeout_secs), receiver) => result
            .map_err(|_| "timed out waiting for OAuth redirect".to_string())?
            .map_err(|_| "OAuth callback server closed unexpectedly".to_string()),
        _ = cancelled.notified() => Err(CANCELLED_MESSAGE.to_string()),
    };

    if let Some(server) = state
        .listener
        .lock()
        .map_err(|error| error.to_string())?
        .take()
    {
        server.unblock();
    }

    if let Err(error) = &outcome {
        log::warn!("OAuth callback wait failed: {error}");
    }

    outcome
}
