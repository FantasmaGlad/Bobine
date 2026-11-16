import type { Dict } from "../core.ts";

export const uploads: Dict = {
  phase: { connecting: "Connecting to the server", sending: "Uploading", processing: "Processing" },
  retrying: "The server is not responding, retry {{attempt}}/{{max}}",
  retryingServerError: "The server returned an error ({{status}}), retry {{attempt}}/{{max}}",
  serverUnreachable: "The server is not responding: tracking will resume when it is back.",
  reason: {
    network: "network error",
    timeout: "timed out",
    stalled: "no data sent for {{seconds}} s",
    server: "server error {{status}}",
  },
  errors: {
    sessionTimeout: "The server is not responding (no answer after {{seconds}} s). Check that Bobine is running, then try again.",
    unreachable: "Unable to reach the server. Check that Bobine is running and your network connection, then try again.",
    sessionLost: "Transfer session lost (the server restarted or the session expired). Start the import again.",
    interrupted: "Transfer interrupted after {{max}} attempts ({{reason}}).",
    jobLost: "Task lost (server restarted or expired). Check the library, then start the import again if the file is not there.",
    mediaToolMissing: "{{tool}} was not found: Bobine needs it to analyse and convert videos. {{hint}}",
    installHint: {
      macos: "Install it with Homebrew (brew install ffmpeg), then restart Bobine.",
      windows: "Reinstall Bobine: ffmpeg is normally bundled with the app.",
      linux: "Install it with your package manager (sudo apt install ffmpeg), then restart Bobine.",
      android: "This component ships with the app: reinstall Bobine.",
    },
  },
};
