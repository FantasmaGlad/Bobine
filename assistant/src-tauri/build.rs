use std::path::Path;

/// Embarque la version et le commit de build dans le binaire (réf. mission
/// "hiérarchie des versions" — l'assistant ne pouvait pas se comparer
/// correctement aux releases GitHub car il n'avait aucune idée de sa propre
/// version). Lit `VERSION`/`COMMIT` à la racine du dépôt — mêmes fichiers
/// que ceux lus par le backend Python (`app/utils/version.py`), écrits par
/// la CI juste avant `cargo build` (VERSION suffixée "-beta" pour un build
/// du canal Bêta, cf. ci.yml). Repli sur des valeurs de développement si
/// absents (compilation locale hors CI).
fn main() {
    tauri_build::build();

    let repo_root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");

    let version = std::fs::read_to_string(repo_root.join("VERSION"))
        .ok()
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| "0.0.0-dev".to_string());
    let commit = std::fs::read_to_string(repo_root.join("COMMIT"))
        .ok()
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| "unknown".to_string());

    println!("cargo:rustc-env=BOBINE_VERSION={version}");
    println!("cargo:rustc-env=BOBINE_COMMIT={commit}");
    println!("cargo:rerun-if-changed=../../VERSION");
    println!("cargo:rerun-if-changed=../../COMMIT");
}
