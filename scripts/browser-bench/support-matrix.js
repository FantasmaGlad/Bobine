const v = document.createElement('video'), a = document.createElement('audio');
const codecs = {
 'H.264 Baseline 3.1': 'video/mp4; codecs="avc1.42E01F"', 'H.264 High 4.1': 'video/mp4; codecs="avc1.640029"',
 'H.264 High 5.1 (4K)': 'video/mp4; codecs="avc1.640033"', 'H.264 High10 (10-bit)': 'video/mp4; codecs="avc1.6E0033"',
 'HEVC Main': 'video/mp4; codecs="hvc1.1.6.L93.B0"', 'HEVC Main10 4K': 'video/mp4; codecs="hvc1.2.4.L153.B0"',
 'AV1 Main 8-bit': 'video/mp4; codecs="av01.0.08M.08"', 'VP9': 'video/webm; codecs="vp09.00.10.08"', 'VP8': 'video/webm; codecs="vp8"',
 'MKV H.264': 'video/x-matroska; codecs="avc1.640029"', 'MKV container': 'video/x-matroska',
 'AAC-LC': 'audio/mp4; codecs="mp4a.40.2"', 'HE-AAC': 'audio/mp4; codecs="mp4a.40.5"', 'MP3': 'audio/mpeg', 'Opus webm': 'audio/webm; codecs="opus"',
 'FLAC': 'audio/flac', 'AC-3': 'audio/mp4; codecs="ac-3"', 'E-AC-3': 'audio/mp4; codecs="ec-3"', 'WAV': 'audio/wav', 'OGG Vorbis': 'audio/ogg; codecs="vorbis"', 'M4A': 'audio/x-m4a',
};
const out = {codecs:{}, mse:{}, api:{}, css:{}};
for (const [k,t] of Object.entries(codecs)) { out.codecs[k] = (t.startsWith('audio')?a:v).canPlayType(t) || 'non'; out.mse[k] = window.MediaSource ? MediaSource.isTypeSupported(t) : 'n/a'; }
const apis = {
 WebSocket: !!window.WebSocket, 'XHR upload progress': 'upload' in new XMLHttpRequest(), fetch: !!window.fetch,
 'fetch streaming upload (ReadableStream body)': (()=>{ try { return !!window.ReadableStream && new Request('http://x', {method:'POST', body:new ReadableStream(), duplex:'half'}) && true } catch(e){ return false } })(),
 requestVideoFrameCallback: 'requestVideoFrameCallback' in HTMLVideoElement.prototype, 'Screen Wake Lock': 'wakeLock' in navigator,
 Gamepad: 'getGamepads' in navigator, Fullscreen: !!document.documentElement.requestFullscreen, MediaSession: 'mediaSession' in navigator,
 'MediaCapabilities': 'mediaCapabilities' in navigator, 'Cache API': 'caches' in window, 'ServiceWorker': 'serviceWorker' in navigator,
 'AudioContext': !!(window.AudioContext||window.webkitAudioContext), 'setSinkId': 'setSinkId' in HTMLMediaElement.prototype,
 'webkitdirectory (input)': 'webkitdirectory' in document.createElement('input'), 'webkitGetAsEntry': 'webkitGetAsEntry' in DataTransferItem.prototype,
 'File System Access (showDirectoryPicker)': 'showDirectoryPicker' in window, 'BroadcastChannel': !!window.BroadcastChannel,
 'IntersectionObserver': !!window.IntersectionObserver, 'ResizeObserver': !!window.ResizeObserver, 'Web Locks': 'locks' in navigator,
 'structuredClone': !!window.structuredClone, 'crypto.randomUUID': !!(crypto&&crypto.randomUUID), 'Clipboard write': !!(navigator.clipboard&&navigator.clipboard.writeText),
 'PerformanceObserver longtask': (PerformanceObserver.supportedEntryTypes||[]).includes('longtask'), 'Document PiP': 'documentPictureInPicture' in window,
 'Pointer events': !!window.PointerEvent, 'hardwareConcurrency': navigator.hardwareConcurrency, 'deviceMemory': navigator.deviceMemory ?? 'n/a (Firefox ne l\'expose pas)',
};
Object.assign(out.api, apis);
const css = ['backdrop-filter: blur(4px)','-webkit-backdrop-filter: blur(4px)','selector(:has(a))','color: color-mix(in srgb, red, blue)','height: 100dvh','aspect-ratio: 16/9','scrollbar-width: thin','scrollbar-gutter: stable','text-wrap: balance','container-type: inline-size','field-sizing: content','inset: 0','gap: 4px','overscroll-behavior: contain','position: sticky','mask-image: linear-gradient(black, transparent)','-webkit-mask-image: linear-gradient(black, transparent)','background-clip: text','-webkit-background-clip: text','color: oklch(60% .2 250)','view-transition-name: x','animation-timeline: scroll()','interpolate-size: allow-keywords','accent-color: red','-webkit-line-clamp: 2','line-clamp: 2','touch-action: manipulation'];
for (const c of css) out.css[c] = c.startsWith('selector') ? CSS.supports(c) : CSS.supports(c.replace(/^([^:]+):\s*(.*)$/, '$1: $2'));
return out;
