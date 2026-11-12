pub mod macos;
pub mod unsupported;
pub mod windows;

use crate::protocol::Platform;

pub fn current() -> Box<dyn Platform> {
    if cfg!(target_os = "macos") {
        Box::new(macos::MacOs::new())
    } else if cfg!(target_os = "windows") {
        Box::new(windows::Windows::new())
    } else {
        Box::new(unsupported::Unsupported)
    }
}
