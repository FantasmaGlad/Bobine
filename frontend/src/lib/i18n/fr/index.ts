import type { Dict } from "../core.ts";

import { nav } from "./nav.ts";
import { storage } from "./storage/index.ts";
import { devices } from "./devices.ts";
import { radioLibrary } from "./radioLibrary.ts";
import { radioSound } from "./radioSound.ts";
import { radioRemote } from "./radioRemote.ts";
import { radioScreen } from "./radioScreen.ts";
import { radioAnnouncements } from "./radioAnnouncements.ts";
import { common } from "./common.ts";
import { dashboard } from "./dashboard.ts";
import { mediaNative } from "./mediaNative.ts";
import { browserCompat } from "./browserCompat.ts";
import { webRendition } from "./webRendition.ts";
import { library } from "./library.ts";
import { playlists } from "./playlists.ts";
import { audioPlaylists } from "./audioPlaylists.ts";
import { schedule } from "./schedule.ts";
import { audio } from "./audio.ts";
import { backgrounds } from "./backgrounds.ts";
import { coach } from "./coach.ts";
import { mobileRemote } from "./mobileRemote.ts";
import { chapters } from "./chapters.ts";
import { logs } from "./logs.ts";
import { cinema } from "./cinema.ts";
import { kiosk } from "./kiosk.ts";
import { settingsPage } from "./settingsPage/index.ts";
import { uploads } from "./uploads.ts";
import { courseRating } from "./courseRating.ts";
import { metricsPage } from "./metricsPage.ts";
import { telemetryDrawer } from "./telemetryDrawer.ts";
import { audioBadge } from "./audioBadge.ts";
import { app } from "./app.ts";
import { uploadManager } from "./uploadManager.ts";
import { signage } from "./signage.ts";

export const dictionary: Dict = {
  nav,
  storage,
  devices,
  radioLibrary,
  radioSound,
  radioRemote,
  radioScreen,
  radioAnnouncements,
  common,
  dashboard,
  mediaNative,
  browserCompat,
  webRendition,
  library,
  playlists,
  audioPlaylists,
  schedule,
  audio,
  backgrounds,
  coach,
  mobileRemote,
  chapters,
  logs,
  cinema,
  kiosk,
  settingsPage,
  uploads,
  courseRating,
  metricsPage,
  telemetryDrawer,
  audioBadge,
  app,
  uploadManager,
  signage,
};
