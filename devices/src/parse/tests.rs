use super::{macos, windows};

#[test]
fn macos_audio_and_bluetooth() {
    let audio = r#"{"SPAudioDataType":[{"_items":[
      {"_name":"MacBook Pro Speakers","coreaudio_default_audio_output_device":"spaudio_yes","coreaudio_device_output":2,"coreaudio_device_transport":"coreaudio_device_type_builtin"},
      {"_name":"AirPods","coreaudio_device_output":2,"coreaudio_device_transport":"coreaudio_device_type_bluetooth"},
      {"_name":"Micro","coreaudio_device_input":1}]}]}"#;
    let (devices, default_id) = macos::audio(audio).unwrap();
    assert_eq!(devices.len(), 2);
    assert_eq!(default_id.as_deref(), Some("MacBook Pro Speakers"));
    assert_eq!(devices[0]["kind"], "internal");
    assert_eq!(devices[1]["kind"], "bluetooth");

    let bt = r#"{"SPBluetoothDataType":[{"controller_properties":{"controller_state":"attrib_on"},
      "device_connected":[{"AirPods":{"device_address":"AA-BB-CC-DD-EE-FF","device_minorType":"Headphones","device_batteryLevelMain":"80%"}}],
      "device_not_connected":[{"Souris":{"device_address":"11:22:33:44:55:66","device_minorType":"Mouse"}}]}]}"#;
    let (powered, devices) = macos::bluetooth(bt).unwrap();
    assert!(powered);
    assert_eq!(devices[0]["address"], "AA:BB:CC:DD:EE:FF");
    assert_eq!(devices[0]["connected"], true);
    assert_eq!(devices[0]["kind"], "headphones");
    assert_eq!(devices[0]["battery"], 80);
    assert_eq!(devices[1]["kind"], "mouse");
}

#[test]
fn powershell_json_and_bluetooth() {
    assert_eq!(windows::powershell_json_array("").len(), 0);
    assert_eq!(windows::powershell_json_array(r#"{"a":1}"#).len(), 1);
    assert_eq!(
        windows::powershell_json_array(r#"[{"a":1},{"a":2}]"#).len(),
        2
    );
    let items = windows::powershell_json_array(
        r#"[{"FriendlyName":"JBL","Status":"OK","InstanceId":"BTHENUM\\DEV_88B2CC9C410E\\7&1&0&BLUETOOTHDEVICE_88B2CC9C410E"},{"FriendlyName":"Radio","Status":"OK","InstanceId":"USB\\VID_8087"}]"#,
    );
    let devices = windows::bluetooth(&items);
    assert_eq!(devices.len(), 1);
    assert_eq!(devices[0]["address"], "88:B2:CC:9C:41:0E");
    assert_eq!(devices[0]["connected"], true);
}
