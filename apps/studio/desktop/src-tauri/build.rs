fn main() {
    println!("cargo:rerun-if-changed=capabilities");
    // Ignore hidden macOS metadata files such as ._default.json after transfer.
    tauri_build::try_build(
        tauri_build::Attributes::new().capabilities_path_pattern("./capabilities/**/[!.]*"),
    )
    .expect("failed to build MoCapGate Studio resources");
}
