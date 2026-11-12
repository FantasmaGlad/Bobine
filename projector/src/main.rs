use tao::{
    event::{Event, WindowEvent},
    event_loop::{ControlFlow, EventLoop},
    window::{Fullscreen, WindowBuilder},
};
use wry::WebViewBuilder;

#[derive(Debug, Clone, PartialEq, Eq)]
enum MonitorChoice {
    External,
    Primary,
    Index(usize),
}

#[derive(Debug, PartialEq, Eq)]
struct Args {
    url: String,
    monitor: MonitorChoice,
}

fn parse_args(args: &[String]) -> Result<Args, String> {
    let mut url: Option<String> = None;
    let mut monitor = MonitorChoice::External;
    let mut iter = args.iter().skip(1);
    while let Some(arg) = iter.next() {
        match arg.as_str() {
            "--url" => url = Some(iter.next().ok_or("--url demande une valeur")?.clone()),
            "--monitor" => {
                let value = iter.next().ok_or("--monitor demande une valeur")?;
                monitor = match value.as_str() {
                    "external" => MonitorChoice::External,
                    "primary" => MonitorChoice::Primary,
                    other => MonitorChoice::Index(
                        other
                            .parse::<usize>()
                            .map_err(|_| format!("--monitor invalide : {other}"))?,
                    ),
                };
            }
            other => return Err(format!("argument inconnu : {other}")),
        }
    }
    let url = url.ok_or("--url est obligatoire")?;
    if !(url.starts_with("http://") || url.starts_with("https://")) {
        return Err(format!("URL non autorisee : {url}"));
    }
    Ok(Args { url, monitor })
}

fn select_monitor<T: Clone + PartialEq>(
    monitors: &[T],
    primary: Option<&T>,
    choice: &MonitorChoice,
) -> Option<T> {
    match choice {
        MonitorChoice::Primary => primary.cloned().or_else(|| monitors.first().cloned()),
        MonitorChoice::Index(i) => monitors.get(*i).cloned(),
        MonitorChoice::External => monitors
            .iter()
            .find(|m| Some(*m) != primary)
            .cloned()
            .or_else(|| primary.cloned())
            .or_else(|| monitors.first().cloned()),
    }
}

fn main() -> wry::Result<()> {
    let args: Vec<String> = std::env::args().collect();
    let parsed = match parse_args(&args) {
        Ok(parsed) => parsed,
        Err(message) => {
            eprintln!("bobine-projector : {message}");
            std::process::exit(2);
        }
    };

    #[allow(unused_mut)]
    let mut event_loop = EventLoop::new();
    #[cfg(target_os = "macos")]
    {
        use tao::platform::macos::{ActivationPolicy, EventLoopExtMacOS};
        event_loop.set_activation_policy(ActivationPolicy::Accessory);
    }

    let window = WindowBuilder::new()
        .with_title("Bobine")
        .with_decorations(false)
        .build(&event_loop)
        .expect("creation de la fenetre impossible");

    let monitors: Vec<_> = window.available_monitors().collect();
    let primary = window.primary_monitor();
    let target = select_monitor(&monitors, primary.as_ref(), &parsed.monitor);
    window.set_fullscreen(Some(Fullscreen::Borderless(target)));
    window.set_cursor_visible(false);

    let builder = WebViewBuilder::new()
        .with_url(&parsed.url)
        .with_autoplay(true);

    #[cfg(any(
        target_os = "windows",
        target_os = "macos",
        target_os = "ios",
        target_os = "android"
    ))]
    let _webview = builder.build(&window)?;
    #[cfg(not(any(
        target_os = "windows",
        target_os = "macos",
        target_os = "ios",
        target_os = "android"
    )))]
    let _webview = {
        use tao::platform::unix::WindowExtUnix;
        use wry::WebViewBuilderExtUnix;
        let vbox = window.default_vbox().expect("conteneur GTK indisponible");
        builder.build_gtk(vbox)?
    };

    event_loop.run(move |event, _, control_flow| {
        *control_flow = ControlFlow::Wait;
        if let Event::WindowEvent {
            event: WindowEvent::CloseRequested,
            ..
        } = event
        {
            *control_flow = ControlFlow::Exit;
        }
    });
}

#[cfg(test)]
mod tests {
    use super::*;

    fn a(list: &[&str]) -> Vec<String> {
        list.iter().map(|s| s.to_string()).collect()
    }

    #[test]
    fn parse_url_et_ecran_par_defaut() {
        let parsed = parse_args(&a(&[
            "p",
            "--url",
            "http://127.0.0.1:1903/cinema/?channel=cable",
        ]))
        .unwrap();
        assert_eq!(parsed.url, "http://127.0.0.1:1903/cinema/?channel=cable");
        assert_eq!(parsed.monitor, MonitorChoice::External);
    }

    #[test]
    fn parse_choix_d_ecran() {
        assert_eq!(
            parse_args(&a(&["p", "--url", "http://x", "--monitor", "primary"]))
                .unwrap()
                .monitor,
            MonitorChoice::Primary
        );
        assert_eq!(
            parse_args(&a(&["p", "--url", "http://x", "--monitor", "2"]))
                .unwrap()
                .monitor,
            MonitorChoice::Index(2)
        );
    }

    #[test]
    fn parse_refuse_les_entrees_invalides() {
        assert!(parse_args(&a(&["p"])).is_err());
        assert!(parse_args(&a(&["p", "--url"])).is_err());
        assert!(parse_args(&a(&["p", "--url", "file:///etc/passwd"])).is_err());
        assert!(parse_args(&a(&["p", "--url", "javascript:alert(1)"])).is_err());
        assert!(parse_args(&a(&["p", "--url", "http://x", "--monitor", "abc"])).is_err());
        assert!(parse_args(&a(&["p", "--url", "http://x", "--bogus"])).is_err());
    }

    #[test]
    fn selection_ecran_externe_puis_replis() {
        let monitors = ["interne", "projecteur", "tv"];
        assert_eq!(
            select_monitor(&monitors, Some(&"interne"), &MonitorChoice::External),
            Some("projecteur")
        );
        assert_eq!(
            select_monitor(&["interne"], Some(&"interne"), &MonitorChoice::External),
            Some("interne")
        );
        assert_eq!(
            select_monitor(&["a", "b"], None, &MonitorChoice::External),
            Some("a")
        );
        assert_eq!(
            select_monitor::<&str>(&[], None, &MonitorChoice::External),
            None
        );
    }

    #[test]
    fn selection_principal_et_index() {
        let monitors = ["interne", "projecteur"];
        assert_eq!(
            select_monitor(&monitors, Some(&"interne"), &MonitorChoice::Primary),
            Some("interne")
        );
        assert_eq!(
            select_monitor(&monitors, Some(&"interne"), &MonitorChoice::Index(1)),
            Some("projecteur")
        );
        assert_eq!(
            select_monitor(&monitors, Some(&"interne"), &MonitorChoice::Index(9)),
            None
        );
    }
}
