use crate::protocol::RpcError;
use std::io::{Read, Write};
use std::process::{Child, Command, ExitStatus, Stdio};
use std::thread;
use std::time::{Duration, Instant};

const OUTPUT_CAP: u64 = 4 * 1024 * 1024;

pub struct Output {
    pub code: i32,
    pub stdout: String,
    pub stderr: String,
}

pub fn run(
    program: &str,
    args: &[&str],
    timeout: Duration,
    stdin: Option<&str>,
) -> Result<Output, RpcError> {
    run_with_env(program, args, timeout, stdin, &[])
}

fn spawn(
    program: &str,
    args: &[&str],
    piped_stdin: bool,
    envs: &[(&str, &str)],
) -> Result<Child, RpcError> {
    Command::new(program)
        .args(args)
        .envs(envs.iter().copied())
        .stdin(if piped_stdin {
            Stdio::piped()
        } else {
            Stdio::null()
        })
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| match e.kind() {
            std::io::ErrorKind::NotFound => RpcError::app(
                "tool_missing",
                format!("Outil système introuvable : {program}"),
            ),
            _ => RpcError::app(
                "tool_failed",
                format!("Impossible de lancer {program} : {e}"),
            ),
        })
}

fn wait_within(child: &mut Child, program: &str, timeout: Duration) -> Result<ExitStatus, RpcError> {
    let started = Instant::now();
    loop {
        match child.try_wait() {
            Ok(Some(status)) => return Ok(status),
            Ok(None) if started.elapsed() >= timeout => {
                let _ = child.kill();
                let _ = child.wait();
                return Err(RpcError::app(
                    "timeout",
                    format!("{program} n'a pas répondu dans le délai imparti."),
                ));
            }
            Ok(None) => thread::sleep(Duration::from_millis(20)),
            Err(e) => return Err(RpcError::app("tool_failed", format!("{program} : {e}"))),
        }
    }
}

pub fn run_with_env(
    program: &str,
    args: &[&str],
    timeout: Duration,
    stdin: Option<&str>,
    envs: &[(&str, &str)],
) -> Result<Output, RpcError> {
    let mut child = spawn(program, args, stdin.is_some(), envs)?;
    if let (Some(text), Some(mut pipe)) = (stdin, child.stdin.take()) {
        let _ = pipe.write_all(text.as_bytes());
    }
    let mut stdout = child.stdout.take();
    let mut stderr = child.stderr.take();
    let out_reader = thread::spawn(move || read_all(stdout.as_mut()));
    let err_reader = thread::spawn(move || read_all(stderr.as_mut()));
    let status = wait_within(&mut child, program, timeout)?;
    Ok(Output {
        code: status.code().unwrap_or(-1),
        stdout: out_reader.join().unwrap_or_default(),
        stderr: err_reader.join().unwrap_or_default(),
    })
}

fn read_all<R: Read>(reader: Option<&mut R>) -> String {
    let mut buffer = Vec::new();
    if let Some(r) = reader {
        let _ = r.take(OUTPUT_CAP).read_to_end(&mut buffer);
        let _ = std::io::copy(r, &mut std::io::sink());
    }
    String::from_utf8_lossy(&buffer).into_owned()
}

pub fn require_success(out: Output, what: &str) -> Result<Output, RpcError> {
    if out.code == 0 {
        Ok(out)
    } else {
        Err(RpcError::app_with_detail(
            "tool_failed",
            format!("{what} a échoué."),
            out.stderr.lines().next().unwrap_or(""),
        ))
    }
}

pub fn tool_exists(program: &str) -> bool {
    let Some(path) = std::env::var_os("PATH") else {
        return false;
    };
    std::env::split_paths(&path).any(|dir| {
        let candidate = dir.join(program);
        candidate.is_file() || candidate.with_extension("exe").is_file()
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn missing_tool_is_a_structured_error() {
        let err = match run(
            "definitely-not-a-real-tool-xyz",
            &[],
            Duration::from_secs(1),
            None,
        ) {
            Err(e) => e,
            Ok(_) => panic!("attendu : erreur"),
        };
        assert_eq!(err.data.unwrap()["code"], "tool_missing");
    }

    fn output(code: i32, stderr: &str) -> Output {
        Output {
            code,
            stdout: String::new(),
            stderr: stderr.to_string(),
        }
    }

    #[test]
    fn require_success_passes_a_zero_exit() {
        assert!(require_success(output(0, "ignored"), "outil").is_ok());
    }

    #[test]
    fn require_success_keeps_stderr_out_of_the_message() {
        let err = match require_success(output(2, "premiere\nseconde"), "outil") {
            Err(e) => e,
            Ok(_) => panic!("attendu : erreur"),
        };
        assert_eq!(err.message, "outil a échoué.");
        let data = err.data.unwrap();
        assert_eq!(
            (data["code"].as_str(), data["detail"].as_str()),
            (Some("tool_failed"), Some("premiere"))
        );
        let silent = require_success(output(1, ""), "outil").err().unwrap();
        assert_eq!(silent.message, "outil a échoué.");
    }

    #[cfg(unix)]
    #[test]
    fn runs_with_stdin_and_times_out() {
        let out = run("cat", &[], Duration::from_secs(5), Some("bonjour")).unwrap();
        assert_eq!((out.code, out.stdout.as_str()), (0, "bonjour"));
        let err = match run("sleep", &["5"], Duration::from_millis(100), None) {
            Err(e) => e,
            Ok(_) => panic!("attendu : délai dépassé"),
        };
        assert_eq!(err.data.unwrap()["code"], "timeout");
    }

    #[cfg(unix)]
    #[test]
    fn output_past_the_cap_is_drained_and_truncated() {
        let script = "head -c 6291456 /dev/zero | tr '\\0' a";
        let out = run("sh", &["-c", script], Duration::from_secs(10), None).unwrap();
        assert_eq!((out.code, out.stdout.len()), (0, OUTPUT_CAP as usize));
    }
}
