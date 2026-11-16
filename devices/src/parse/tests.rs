use super::{dbm_to_percent, macos, subnet_cidr, windows};

#[test]
fn dbm_and_subnet() {
    assert_eq!(dbm_to_percent(-50.0), 100);
    assert_eq!(dbm_to_percent(-75.0), 50);
    assert_eq!(dbm_to_percent(-120.0), 0);
    assert_eq!(
        subnet_cidr("192.168.1.17", "255.255.255.0").as_deref(),
        Some("192.168.1.0/24")
    );
    assert_eq!(
        subnet_cidr("10.1.2.3", "0xffff0000").as_deref(),
        Some("10.1.0.0/16")
    );
    assert_eq!(subnet_cidr("10.1.2.3", "255.0.255.0"), None);
    assert_eq!(subnet_cidr("x", "255.0.0.0"), None);
}

#[test]
fn macos_networksetup() {
    let ports = "Hardware Port: Ethernet\nDevice: en5\nEthernet Address: aa\n\nHardware Port: Wi-Fi\nDevice: en0\nEthernet Address: bb\n";
    assert_eq!(macos::wifi_device(ports).as_deref(), Some("en0"));
    assert_eq!(
        macos::wifi_device("Hardware Port: Ethernet\nDevice: en5\n"),
        None
    );
    assert_eq!(macos::wifi_power("Wi-Fi Power (en0): On"), Some(true));
    assert_eq!(macos::wifi_power("Wi-Fi Power (en0): Off"), Some(false));
    assert_eq!(
        macos::current_network("Current Wi-Fi Network: Livebox\n").as_deref(),
        Some("Livebox")
    );
    assert_eq!(
        macos::current_network("You are not associated with an AirPort network.\n"),
        None
    );
    assert_eq!(
        macos::preferred_networks("Preferred networks on en0:\n\tLivebox\n\tFanta\n"),
        vec!["Livebox", "Fanta"]
    );
}

const AIRPORT: &str = r#"{"SPAirPortDataType":[{"spairport_airport_interfaces":[{"_name":"en0",
  "spairport_current_network_information":{"_name":"Livebox","spairport_network_channel":"36 (5GHz, 80MHz)","spairport_security_mode":"spairport_security_mode_wpa2_personal","spairport_signal_noise":"-55 dBm / -90 dBm"},
  "spairport_airport_other_local_wireless_networks":[
    {"_name":"Voisin","spairport_network_channel":"1 (2GHz, 20MHz)","spairport_security_mode":"spairport_security_mode_wpa3_personal","spairport_signal_noise":"-80 dBm / -92 dBm"},
    {"_name":"Cafe","spairport_network_channel":"6 (2GHz, 20MHz)","spairport_security_mode":"spairport_security_mode_none","spairport_signal_noise":"-90 dBm / -92 dBm"}]}]}]}"#;

#[test]
fn macos_airport_lists_current_and_others() {
    let nets = macos::airport(AIRPORT, "en0", &["Livebox".to_string()]).unwrap();
    assert_eq!(nets.len(), 3);
    assert_eq!(nets[0]["ssid"], "Livebox");
    assert_eq!(nets[0]["in_use"], true);
    assert_eq!(nets[0]["known"], true);
    assert_eq!(nets[0]["band"], "5 GHz");
    assert_eq!(nets[0]["security"], "WPA2");
    assert_eq!(nets[1]["security"], "WPA3");
    assert_eq!(nets[2]["security"], "");
    assert_eq!(nets[1]["signal"], 40);
    assert!(macos::airport("pas du json", "en0", &[]).is_none());
}

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

const NETSH_IF_EN: &str = "There is 1 interface on the system:\n\n    Name                   : Wi-Fi\n    Description            : Intel(R) Wi-Fi 6\n    State                  : connected\n    SSID                   : Livebox\n    BSSID                  : aa:bb:cc:dd:ee:ff\n    Network type           : Infrastructure\n    Band                   : 5 GHz\n    Signal                 : 84%\n";
const NETSH_IF_FR: &str = "Il existe 1 interface sur le système :\n\n    Nom                    : Wi-Fi\n    État                   : connecté\n    SSID                   : Livebox\n    BSSID                  : aa:bb:cc:dd:ee:ff\n    Bande                  : 5 GHz\n    Signal                 : 71%\n";

#[test]
fn windows_interface_en_and_fr() {
    let en = windows::interface(NETSH_IF_EN).unwrap();
    assert!(
        en.connected
            && en.ssid.as_deref() == Some("Livebox")
            && en.signal == 84
            && en.band == "5 GHz"
    );
    let fr = windows::interface(NETSH_IF_FR).unwrap();
    assert!(fr.connected && fr.signal == 71 && fr.name == "Wi-Fi");
    let off = windows::interface("    Name : Wi-Fi\n    State : disconnected\n").unwrap();
    assert!(!off.connected && off.ssid.is_none());
    assert!(windows::interface("rien").is_none());
}

#[test]
fn windows_networks_dedupes_and_flags() {
    let text = "Interface name : Wi-Fi\nThere are 3 networks currently visible.\n\nSSID 1 : Livebox\n    Network type            : Infrastructure\n    Authentication          : WPA2-Personal\n    Encryption              : CCMP\n    BSSID 1                 : aa:bb\n         Signal             : 80%\n         Band               : 5 GHz\n    BSSID 2                 : cc:dd\n         Signal             : 55%\n         Band               : 2.4 GHz\n\nSSID 2 : Cafe\n    Authentication          : Open\n    BSSID 1                 : ee:ff\n         Signal             : 30%\n\nSSID 3 : \n    Authentication          : WPA2-Personal\n    BSSID 1                 : 11:22\n         Signal             : 20%\n";
    let nets = windows::networks(text, Some("Livebox"), &["Livebox".to_string()]);
    assert_eq!(nets.len(), 2);
    assert_eq!(nets[0]["signal"], 80);
    assert_eq!(nets[0]["security"], "WPA2");
    assert_eq!(nets[0]["in_use"], true);
    assert_eq!(nets[0]["known"], true);
    assert_eq!(nets[0]["band"], "5 GHz");
    assert_eq!(nets[1]["security"], "");
}

#[test]
fn windows_profiles_and_xml() {
    let text = "Profiles on interface Wi-Fi:\n\nGroup policy profiles (read only)\n---------------------------------\n    <None>\n\nUser profiles\n-------------\n    All User Profile     : Livebox\n    All User Profile     : Café & Co\n";
    assert_eq!(windows::profiles(text), vec!["Livebox", "Café & Co"]);
    let xml = windows::profile_xml("A&B", Some("p<w>\"'"));
    assert!(
        xml.contains("<name>A&amp;B</name>")
            && xml.contains("p&lt;w&gt;&quot;&apos;")
            && xml.contains("WPA2PSK")
    );
    assert!(windows::profile_xml("Libre", None).contains("<authentication>open</authentication>"));
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
