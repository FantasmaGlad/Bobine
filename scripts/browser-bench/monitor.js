// moniteur de réactivité jetable : retard de boucle d'événements + écarts entre frames
(function(){
  if (window.__mon) return;
  const m = window.__mon = {lagMax:0, lagOver100:0, lagOver500:0, ticks:0, frames:0, frameGapMax:0, frameGapOver100:0, longest:[], start:performance.now()};
  let last = performance.now();
  setInterval(()=>{ const now=performance.now(); const lag=now-last-25; last=now; m.ticks++;
    if(lag>m.lagMax) m.lagMax=Math.round(lag); if(lag>100) m.lagOver100++; if(lag>500) m.lagOver500++; },25);
  let lf = performance.now();
  (function raf(){ const n=performance.now(); const g=n-lf; lf=n; m.frames++; if(g>m.frameGapMax) m.frameGapMax=Math.round(g); if(g>100) m.frameGapOver100++; requestAnimationFrame(raf); })();
})();
