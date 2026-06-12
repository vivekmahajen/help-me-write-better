// Help Me Write Better — desktop shell (Tauri v2).
//
// A thin native window over the hosted editor (see ../dist/index.html). No
// custom commands: the editor already talks to the public JSON API directly.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("error while running Help Me Write Better");
}
