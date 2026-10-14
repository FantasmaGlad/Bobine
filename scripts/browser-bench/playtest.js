const url = arguments[0], done = arguments[arguments.length-1];
const v = document.createElement('video'); v.muted = true; v.preload='auto'; v.src = url; v.style.cssText='position:fixed;right:0;bottom:0;width:480px;height:270px;z-index:99999';
document.body.appendChild(v);
const res = {url, events:[]};
['loadedmetadata','canplay','error','stalled','waiting'].forEach(e=>v.addEventListener(e,()=>res.events.push(e+'@'+Math.round(performance.now()))));
const t0 = performance.now();
v.play().then(()=>{ res.play='ok'; }).catch(e=>{ res.play='REFUSED '+e.name; });
setTimeout(()=>{ const q=v.getVideoPlaybackQuality? v.getVideoPlaybackQuality():{}; res.readyState=v.readyState; res.currentTime=+v.currentTime.toFixed(2); res.size=v.videoWidth+'x'+v.videoHeight; res.error=v.error&&v.error.code+':'+v.error.message; res.total=q.totalVideoFrames; res.dropped=q.droppedVideoFrames; res.mon=window.__mon&&{lagMax:window.__mon.lagMax, lagOver100:window.__mon.lagOver100}; v.remove(); done(res); }, 8000);
