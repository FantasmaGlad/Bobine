use std::collections::hash_map::RandomState;
use std::fs::OpenOptions;
use std::hash::{BuildHasher, Hasher};
use std::io::{self, Write};
use std::path::{Path, PathBuf};

const ATTEMPTS: usize = 8;

pub struct SecretFile {
    path: PathBuf,
}

impl SecretFile {
    pub fn create(dir: &Path, prefix: &str, contents: &[u8]) -> io::Result<Self> {
        for _ in 0..ATTEMPTS {
            let path = dir.join(format!("{prefix}-{:016x}.xml", random()));
            let mut options = OpenOptions::new();
            options.write(true).create_new(true);
            #[cfg(unix)]
            std::os::unix::fs::OpenOptionsExt::mode(&mut options, 0o600);
            match options.open(&path) {
                Ok(mut file) => {
                    let secret = SecretFile { path };
                    file.write_all(contents)?;
                    file.sync_all()?;
                    return Ok(secret);
                }
                Err(e) if e.kind() == io::ErrorKind::AlreadyExists => continue,
                Err(e) => return Err(e),
            }
        }
        Err(io::Error::new(
            io::ErrorKind::AlreadyExists,
            "no free temporary name",
        ))
    }

    pub fn path(&self) -> &Path {
        &self.path
    }
}

impl Drop for SecretFile {
    fn drop(&mut self) {
        let _ = std::fs::remove_file(&self.path);
    }
}

fn random() -> u64 {
    let mut hasher = RandomState::new().build_hasher();
    hasher.write_u128(
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_nanos())
            .unwrap_or_default(),
    );
    hasher.finish()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn scratch() -> PathBuf {
        let dir = std::env::temp_dir().join(format!("bobine-secret-test-{}", random()));
        std::fs::create_dir_all(&dir).unwrap();
        dir
    }

    #[test]
    fn names_are_unpredictable_within_a_process() {
        let dir = scratch();
        let a = SecretFile::create(&dir, "bobine-wifi", b"a").unwrap();
        let b = SecretFile::create(&dir, "bobine-wifi", b"b").unwrap();
        assert_ne!(a.path(), b.path());
        assert!(!a
            .path()
            .to_string_lossy()
            .contains(&std::process::id().to_string()));
        assert_eq!(std::fs::read(b.path()).unwrap(), b"b");
        drop((a, b));
        std::fs::remove_dir(&dir).unwrap();
    }

    #[test]
    fn file_is_removed_when_dropped() {
        let dir = scratch();
        let path = {
            let secret = SecretFile::create(&dir, "bobine-wifi", b"secret").unwrap();
            secret.path().to_path_buf()
        };
        assert!(!path.exists());
        std::fs::remove_dir(&dir).unwrap();
    }

    #[cfg(unix)]
    #[test]
    fn file_is_private_to_its_owner() {
        use std::os::unix::fs::PermissionsExt;
        let dir = scratch();
        let secret = SecretFile::create(&dir, "bobine-wifi", b"secret").unwrap();
        let mode = std::fs::metadata(secret.path())
            .unwrap()
            .permissions()
            .mode();
        assert_eq!(mode & 0o777, 0o600);
        drop(secret);
        std::fs::remove_dir(&dir).unwrap();
    }
}
