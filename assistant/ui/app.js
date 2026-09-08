/**
 * Bobine — Assistant d'installation
 * Logique IHM & IPC Tauri 2
 */

// Helper d'invocation Tauri avec repli navigateur gracieux
function getTauriInvoke() {
  if (typeof window !== 'undefined') {
    if (window.__TAURI__?.core?.invoke) {
      return window.__TAURI__.core.invoke;
    }
    if (window.__TAURI_INTERNALS__?.invoke) {
      return window.__TAURI_INTERNALS__.invoke;
    }
    if (window.__TAURI__?.invoke) {
      return window.__TAURI__.invoke;
    }
  }
  return null;
}

// Vrai uniquement en prévisualisation navigateur autonome (aucun pont
// __TAURI__ injecté) — jamais dans l'app compilée réelle, où Tauri injecte
// systématiquement window.__TAURI__ avant l'exécution du premier script de
// page (withGlobalTauri: true). Sert à distinguer sans ambiguïté un scan
// réseau RÉEL d'un jeu de données factice de démonstration (réf. mission
// "Tauri n'invente pas d'IP" — les IP de démo utilisent volontairement la
// plage documentaire réservée RFC 5737 203.0.113.0/24, qui ne peut jamais
// correspondre à un appareil LAN réel, pour qu'elles ne soient jamais
// confondues avec un résultat de scan authentique).
const IS_PREVIEW_MODE = getTauriInvoke() === null;

async function invokeTauri(cmd, args = {}) {
  const tauriInvoke = getTauriInvoke();
  if (tauriInvoke) {
    return await tauriInvoke(cmd, args);
  }
  console.warn(`[Aperçu navigateur — données FICTIVES, pas un vrai appel Tauri] ${cmd}`, args);

  // Mocks pour prévisualisation navigateur standalone. IP volontairement
  // hors de toute plage privée réelle (RFC 5737 TEST-NET-3) et noms
  // explicitement marqués "exemple" pour ne jamais pouvoir être confondus
  // avec un appareil réellement détecté sur le réseau de l'utilisateur.
  if (cmd === 'scan_network') {
    await new Promise(r => setTimeout(r, 1200));
    return [
      { ip: '203.0.113.10', hostname: 'exemple-borne-bobine.local', ssh_open: true, bobine_open: true, open_ports: [22, 8000], os_hint: 'Debian 13 (exemple)', is_wyse_or_bobine: true },
      { ip: '203.0.113.20', hostname: 'exemple-poste-admin.local', ssh_open: true, bobine_open: false, open_ports: [22], os_hint: 'Linux (exemple)', is_wyse_or_bobine: false }
    ];
  }
  if (cmd === 'test_ssh_connection') {
    await new Promise(r => setTimeout(r, 800));
    return {
      host: args.creds?.host || '10.0.0.30',
      os_name: 'Debian GNU/Linux 13 (trixie)',
      is_debian: true,
      is_debian_13: true,
      arch: 'x86_64',
      is_amd64: true,
      sudo_installed: true,
      user_is_sudoer: true,
      privilege_decision: 'sudo',
      needs_root_password: false,
      cpu_model: 'AMD Ryzen Embedded / Intel Pentium Silver J5005',
      memory_total_mb: 8192,
      disk_free_gb: 58,
      gpu_info: 'Intel UHD Graphics 605 (VA-API matériel)'
    };
  }
  if (cmd === 'get_app_info') {
    return { version: '0.0.0-dev', commit: 'preview' };
  }
  if (cmd === 'pick_ssh_key_file') {
    await new Promise(r => setTimeout(r, 400));
    return '/home/exemple/.ssh/cle_exemple_ed25519';
  }
  return { status: 'ok' };
}

// Échappement HTML minimal — nécessaire dès qu'une valeur affichée provient
// du réseau (nom d'hôte résolu en DNS inverse, bannière SSH...) : un
// appareil malveillant du LAN peut renvoyer n'importe quel contenu dans ces
// champs, il ne faut jamais les interpoler tels quels dans innerHTML.
function escapeHtml(str) {
  return String(str ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

// État de l'application
const state = {
  currentStep: 1,
  selectedTarget: null,
  selectedKeyPath: null,
  systemInspection: null,
  installSuccessOpened: false,
};

// Bandeau visible et non-cliquable-à-tort signalant que l'app tourne en
// aperçu navigateur autonome (données de démonstration, pas un vrai scan
// réseau) — voir IS_PREVIEW_MODE. N'apparaît jamais dans l'app Tauri
// compilée réelle.
function renderPreviewModeBanner() {
  if (!IS_PREVIEW_MODE) return;
  const banner = document.createElement('div');
  banner.className = 'preview-mode-banner';
  banner.textContent = 'Aperçu navigateur — données de démonstration fictives (IP 203.0.113.x), aucun scan réseau réel';
  document.body.prepend(banner);
}

function init() {
  renderPreviewModeBanner();
  initWizard();
  listenTauriEvents();
  checkAssistantUpdate();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}

/* ========================================================== */
/* Animation & Rendu de découverte réseau                      */
/* ========================================================== */
function renderScanningAnimation() {
  const container = document.getElementById('devices-list');
  container.innerHTML = `
    <div class="scanning-state">
      <div class="radar-container">
        <div class="radar-ripple ripple-1"></div>
        <div class="radar-ripple ripple-2"></div>
        <div class="radar-ripple ripple-3"></div>
        <div class="radar-core">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M5 12.55a11 11 0 0 1 14.08 0"/>
            <path d="M1.42 9a16 16 0 0 1 21.16 0"/>
            <path d="M8.53 16.11a6 6 0 0 1 6.95 0"/>
            <circle cx="12" cy="20" r="1"/>
          </svg>
        </div>
      </div>
      <div class="scanning-info">
        <h4>Recherche des appareils sur le réseau...</h4>
        <p class="scanning-subtitle">Balayage des sous-réseaux locaux — tous les appareils qui répondent (SSH, Bobine, partage Windows, impression réseau...) sont listés, pas seulement les cibles Bobine.</p>
        <div class="scanning-shimmer-bar">
          <div class="shimmer-progress"></div>
        </div>
        <span class="scanning-hint">Recherche active en cours, veuillez patienter quelques secondes</span>
      </div>
    </div>
  `;
}

/* ========================================================== */
/* Wizard d'installation                                       */
/* ========================================================== */
function initWizard() {
  // Découverte réseau
  const btnScan = document.getElementById('btn-scan');
  const btnScanLabel = document.getElementById('btn-scan-label');
  const scanSpinner = document.getElementById('scan-spinner');
  const devicesList = document.getElementById('devices-list');
  const manualIpInput = document.getElementById('manual-ip-input');
  const btnManualTarget = document.getElementById('btn-manual-target');

  btnScan.addEventListener('click', async () => {
    scanSpinner.classList.add('spinning');
    btnScan.classList.add('scanning');
    btnScan.disabled = true;
    if (btnScanLabel) btnScanLabel.textContent = 'Scan en cours...';

    renderScanningAnimation();

    try {
      const devices = await invokeTauri('scan_network', {});
      renderDevicesList(devices);
    } catch (err) {
      devicesList.innerHTML = `<div class="empty-state"><p style="color: var(--accent-error);">Erreur lors du scan : ${escapeHtml(err)}</p></div>`;
    } finally {
      scanSpinner.classList.remove('spinning');
      btnScan.classList.remove('scanning');
      btnScan.disabled = false;
      if (btnScanLabel) btnScanLabel.textContent = 'Lancer le scan réseau';
    }
  });

  btnManualTarget.addEventListener('click', () => {
    const ip = manualIpInput.value.trim();
    if (!ip) return;
    selectTarget(ip);
    goToStep(2);
  });

  manualIpInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      btnManualTarget.click();
    }
  });

  // Import d'une clé SSH privée locale (alternative au mot de passe et au
  // repli automatique sur ~/.ssh/, réf. mission "clé SSH locale")
  const btnImportKey = document.getElementById('btn-import-ssh-key');
  const btnClearKey = document.getElementById('btn-clear-ssh-key');
  const keyFilenameHint = document.getElementById('ssh-key-filename');

  btnImportKey.addEventListener('click', async () => {
    try {
      const path = await invokeTauri('pick_ssh_key_file', {});
      if (!path) return; // utilisateur a annulé le sélecteur
      state.selectedKeyPath = path;
      const filename = path.split(/[\\/]/).pop();
      keyFilenameHint.textContent = `Clé importée : ${filename}`;
      keyFilenameHint.classList.add('has-key');
      btnClearKey.style.display = '';
    } catch (err) {
      keyFilenameHint.textContent = `Erreur lors de la sélection : ${err}`;
    }
  });

  btnClearKey.addEventListener('click', () => {
    state.selectedKeyPath = null;
    keyFilenameHint.textContent = 'Aucune clé importée — mot de passe, agent SSH ou clés ~/.ssh/ courantes utilisés automatiquement';
    keyFilenameHint.classList.remove('has-key');
    btnClearKey.style.display = 'none';
  });

  // Étape 2 -> Étape 3 (Test SSH)
  document.getElementById('btn-back-to-1').addEventListener('click', () => goToStep(1));
  const btnConnectSsh = document.getElementById('btn-connect-ssh');
  const connectSpinner = document.getElementById('connect-spinner');
  const sshErrorBanner = document.getElementById('ssh-error-banner');
  const sshErrorDesc = document.getElementById('ssh-error-desc');
  ['ssh-username', 'ssh-password'].forEach((id) => {
    document.getElementById(id)?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        btnConnectSsh.click();
      }
    });
  });

  btnConnectSsh.addEventListener('click', async () => {
    connectSpinner.classList.add('spinning');
    btnConnectSsh.disabled = true;
    if (sshErrorBanner) sshErrorBanner.style.display = 'none';

    const creds = {
      host: document.getElementById('ssh-host').value,
      port: parseInt(document.getElementById('ssh-port').value, 10) || 22,
      username: document.getElementById('ssh-username').value.trim() || 'fanta',
      password: document.getElementById('ssh-password').value || null,
      key_path: state.selectedKeyPath || null,
    };

    try {
      const inspection = await invokeTauri('test_ssh_connection', { creds });
      state.systemInspection = inspection;
      renderSystemSpecs(inspection);
      goToStep(3);
    } catch (err) {
      if (sshErrorBanner && sshErrorDesc) {
        sshErrorDesc.textContent = err;
        sshErrorBanner.style.display = 'block';
      } else {
        alert(`Erreur de connexion SSH : ${err}`);
      }
    } finally {
      connectSpinner.classList.remove('spinning');
      btnConnectSsh.disabled = false;
    }
  });

  // Étape 3 -> Étape 4 (Options)
  document.getElementById('btn-back-to-2').addEventListener('click', () => goToStep(2));
  document.getElementById('btn-to-options').addEventListener('click', () => goToStep(4));

  // Étape 4 -> Étape 5 (Lancer installation)
  document.getElementById('btn-back-to-3').addEventListener('click', () => goToStep(3));
  document.getElementById('btn-start-install').addEventListener('click', async () => {
    goToStep(5);
    startInstallationRun();
  });

  // Actions fin d'installation
  document.getElementById('btn-clear-logs').addEventListener('click', () => {
    document.getElementById('terminal-logs').innerHTML = '';
  });

  document.getElementById('btn-open-browser').addEventListener('click', () => {
    window.open(adminUrl(), '_blank');
  });

  document.getElementById('btn-open-kiosk').addEventListener('click', () => {
    window.open(kioskUrl(), '_blank');
  });
}

function adminUrl() {
  const target = state.selectedTarget || '10.0.0.30';
  return `http://${target}:8000`;
}

function kioskUrl() {
  return `${adminUrl()}/kiosk`;
}

// Notification "nouvelle version de l'assistant disponible" (réf. mission
// "canal Stable/Bêta" puis "hiérarchie des versions") : l'assistant Tauri
// n'a pas de backend local à interroger (contrairement à BobineTray) —
// appel direct à l'API GitHub depuis le renderer. bobine-assistant embarque
// désormais sa propre version/commit à la compilation (build.rs + commande
// Tauri get_app_info), lus ici via invokeTauri — sans ça, un assistant
// construit depuis le canal Bêta (donc déjà plus récent que la dernière
// Stable) se voyait proposer "une mise à jour" vers cette Stable, en réalité
// PLUS ANCIENNE : bug corrigé en comparant enfin correctement les versions
// au lieu d'annoncer inconditionnellement "la dernière release existe".
const ASSISTANT_UPDATE_DISMISSED_KEY = 'bobine-assistant-update-dismissed';
const GITHUB_RELEASES_LATEST_URL = 'https://api.github.com/repos/FantasmaGlad/Bobine/releases/latest';
const GITHUB_RELEASES_BETA_URL = 'https://api.github.com/repos/FantasmaGlad/Bobine/releases/tags/beta';

// Port JS du comparateur semver du backend (voir
// backend/app/routers/updates.py::_parse_version — même précédence, à
// maintenir synchronisée si l'une des deux implémentations évolue) : à base
// MAJOR.MINOR.PATCH égale, une version SANS pre-release est toujours
// postérieure à une version AVEC pre-release ; deux pre-releases se
// comparent identifiant par identifiant (numérique si possible, sinon
// lexical — un identifiant numérique a une précédence inférieure à un
// alphanumérique, cf. spec semver §11).
function parseVersionForCompare(versionStr) {
  let s = (versionStr || '').trim();
  if (s[0] === 'v' || s[0] === 'V') s = s.slice(1);
  const dashIdx = s.indexOf('-');
  const basePart = dashIdx === -1 ? s : s.slice(0, dashIdx);
  const prereleasePart = dashIdx === -1 ? '' : s.slice(dashIdx + 1);
  const baseNumbers = (basePart.match(/\d+/g) || []).slice(0, 3).map(Number);
  while (baseNumbers.length < 3) baseNumbers.push(0);
  const identifiers = prereleasePart
    ? prereleasePart.split('.').filter(Boolean).map((part) => (/^\d+$/.test(part) ? { n: Number(part) } : { s: part }))
    : null;
  return { base: baseNumbers, identifiers };
}

function compareIdentifier(a, b) {
  const aIsNum = 'n' in a;
  const bIsNum = 'n' in b;
  if (aIsNum && bIsNum) return a.n - b.n;
  if (aIsNum !== bIsNum) return aIsNum ? -1 : 1;
  return a.s < b.s ? -1 : a.s > b.s ? 1 : 0;
}

// > 0 si a postérieure à b, < 0 si antérieure, 0 si égales.
function compareVersions(aStr, bStr) {
  const a = parseVersionForCompare(aStr);
  const b = parseVersionForCompare(bStr);
  for (let i = 0; i < 3; i++) {
    if (a.base[i] !== b.base[i]) return a.base[i] - b.base[i];
  }
  if (!a.identifiers && !b.identifiers) return 0;
  if (!a.identifiers) return 1;
  if (!b.identifiers) return -1;
  const len = Math.max(a.identifiers.length, b.identifiers.length);
  for (let i = 0; i < len; i++) {
    if (i >= a.identifiers.length) return -1;
    if (i >= b.identifiers.length) return 1;
    const c = compareIdentifier(a.identifiers[i], b.identifiers[i]);
    if (c !== 0) return c;
  }
  return 0;
}

function renderAppVersionBadge(version, commit) {
  const badge = document.getElementById('app-version-badge');
  if (!badge || !version) return;
  const shortCommit = (commit && commit !== 'unknown') ? ` (${commit})` : '';
  badge.textContent = `v${version}${shortCommit}`;
  badge.hidden = false;
}

async function checkAssistantUpdate() {
  let myVersion = null;
  let myCommit = null;
  try {
    const info = await invokeTauri('get_app_info', {});
    myVersion = info?.version || null;
    myCommit = info?.commit || null;
  } catch {
    return;
  }
  if (!myVersion) return;
  renderAppVersionBadge(myVersion, myCommit);

  try {
    const [stableRes, betaRes] = await Promise.allSettled([
      fetch(GITHUB_RELEASES_LATEST_URL, { headers: { Accept: 'application/vnd.github+json' } }),
      fetch(GITHUB_RELEASES_BETA_URL, { headers: { Accept: 'application/vnd.github+json' } }),
    ]);

    let candidate = null;

    if (stableRes.status === 'fulfilled' && stableRes.value.ok) {
      const release = await stableRes.value.json();
      const tag = release.tag_name;
      // Seule comparaison fiable pour la Stable : semver complet (cf.
      // compareVersions) — jamais "une release existe donc c'est une
      // mise à jour" comme avant ce correctif.
      if (tag && compareVersions(tag, myVersion) > 0) {
        const asset = (release.assets || []).find((a) => a.name === 'bobine-assistant');
        candidate = {
          key: `stable:${tag}`,
          label: `Bobine Assistant ${tag} (Stable) est disponible.`,
          downloadUrl: asset?.browser_download_url || release.html_url,
        };
      }
    }

    if (!candidate && betaRes.status === 'fulfilled' && betaRes.value.ok) {
      const release = await betaRes.value.json();
      const remoteCommit = (release.target_commitish || '').slice(0, 7);
      // La Bêta n'a pas de numéro de version qui avance à chaque build (tag
      // fixe "beta", cf. mission "canal Stable/Bêta") : comparaison par
      // commit, comme côté backend (_beta_has_update).
      if (
        remoteCommit && myCommit && myCommit !== 'unknown' &&
        !remoteCommit.startsWith(myCommit) && !myCommit.startsWith(remoteCommit)
      ) {
        const asset = (release.assets || []).find((a) => a.name === 'bobine-assistant');
        candidate = {
          key: `beta:${remoteCommit}`,
          label: `Une nouvelle build Bêta de l'assistant est disponible (${remoteCommit}).`,
          downloadUrl: asset?.browser_download_url || release.html_url,
        };
      }
    }

    if (!candidate) return;

    let dismissedKey = null;
    try {
      dismissedKey = localStorage.getItem(ASSISTANT_UPDATE_DISMISSED_KEY);
    } catch {
      // localStorage indisponible (mode privé strict) : tant pis, pas de mémorisation.
    }
    if (candidate.key === dismissedKey) return;

    const banner = document.getElementById('assistant-update-banner');
    const text = document.getElementById('assistant-update-text');
    if (!banner || !text) return;
    text.textContent = candidate.label;
    banner.style.display = 'flex';

    document.getElementById('btn-assistant-update-download').onclick = () => {
      window.open(candidate.downloadUrl, '_blank');
    };
    document.getElementById('btn-assistant-update-dismiss').onclick = () => {
      banner.style.display = 'none';
      try {
        localStorage.setItem(ASSISTANT_UPDATE_DISMISSED_KEY, candidate.key);
      } catch {
        // idem : pas bloquant si indisponible.
      }
    };
  } catch {
    // Hors ligne ou API GitHub indisponible : silencieux, comme le reste de l'assistant.
  }
}

function goToStep(stepNumber) {
  state.currentStep = stepNumber;

  // Mise à jour de la barre d'étapes
  document.querySelectorAll('.wizard-stepper .step-item').forEach(item => {
    const s = parseInt(item.dataset.step, 10);
    item.classList.remove('active', 'completed');
    if (s === stepNumber) item.classList.add('active');
    else if (s < stepNumber) item.classList.add('completed');
  });

  // Affichage du panneau d'étape
  document.querySelectorAll('.step-pane').forEach(pane => pane.classList.remove('active'));
  const activePane = document.getElementById(`wizard-step-${stepNumber}`);
  if (activePane) activePane.classList.add('active');
}

function renderDevicesList(devices) {
  const container = document.getElementById('devices-list');
  if (!devices || devices.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="11" cy="11" r="8"/>
            <line x1="21" y1="21" x2="16.65" y2="16.65"/>
            <line x1="8" y1="11" x2="14" y2="11"/>
          </svg>
        </div>
        <h4>Aucun appareil détecté</h4>
        <p>Aucun appareil n'a répondu sur les sous-réseaux locaux (aucune trace SSH, Bobine, ni aucun autre service courant). Vérifiez que la borne est allumée et reliée au même réseau, ou saisissez son IP manuellement ci-dessus.</p>
        <button id="btn-retry-scan" class="btn btn-secondary btn-sm" style="margin-top: 6px;">Relancer le scan</button>
      </div>
    `;
    document.getElementById('btn-retry-scan')?.addEventListener('click', () => {
      document.getElementById('btn-scan')?.click();
    });
    return;
  }

  container.innerHTML = '';
  devices.forEach(dev => {
    const row = document.createElement('div');
    row.className = `device-row ${dev.is_wyse_or_bobine ? 'selected' : ''}`;
    const ports = (dev.open_ports || []).join(', ');
    row.innerHTML = `
      <div class="device-info">
        <span class="device-ip">${escapeHtml(dev.ip)}</span>
        ${dev.hostname ? `<span class="device-name">${escapeHtml(dev.hostname)}</span>` : ''}
        <div class="device-badges">
          ${dev.bobine_open ? '<span class="pill pill-success">Bobine Actif</span>' : ''}
          ${dev.ssh_open ? '<span class="pill pill-info">SSH Ouvert</span>' : ''}
          <span class="pill" style="background-color: var(--bg-surface-hover);">${escapeHtml(dev.os_hint || 'Appareil inconnu')}</span>
        </div>
        ${ports ? `<span class="device-ports">Ports ouverts : ${escapeHtml(ports)}</span>` : ''}
      </div>
      <button class="btn btn-secondary btn-sm select-btn">Sélectionner</button>
    `;

    row.querySelector('.select-btn').addEventListener('click', () => {
      selectTarget(dev.ip);
      goToStep(2);
    });

    container.appendChild(row);
  });
}

function selectTarget(ip) {
  state.selectedTarget = ip;
  document.getElementById('ssh-host').value = ip;
  document.getElementById('global-status-dot').className = 'status-dot connected';
  document.getElementById('global-status-text').textContent = `Cible : ${ip}`;
}

function renderSystemSpecs(spec) {
  document.getElementById('spec-os').textContent = spec.os_name;
  document.getElementById('spec-cpu').textContent = spec.cpu_model;
  document.getElementById('spec-mem').textContent = `${(spec.memory_total_mb / 1024).toFixed(1)} Go RAM / ${spec.disk_free_gb} Go Libre`;
  document.getElementById('spec-gpu').textContent = spec.gpu_info;

  const rootBlock = document.getElementById('root-password-block');
  if (spec.needs_root_password) {
    rootBlock.style.display = 'block';
  } else {
    rootBlock.style.display = 'none';
  }
}

async function startInstallationRun() {
  const isMock = document.getElementById('opt-mock').checked;
  const noKiosk = !document.getElementById('opt-kiosk').checked;
  const channel = document.getElementById('opt-beta-channel').checked ? 'beta' : 'stable';
  const rootPassword = document.getElementById('ssh-root-password')?.value || null;

  const params = {
    host: state.selectedTarget || '10.0.0.30',
    port: parseInt(document.getElementById('ssh-port').value, 10) || 22,
    username: document.getElementById('ssh-username').value.trim() || 'fanta',
    password: document.getElementById('ssh-password').value || null,
    key_path: state.selectedKeyPath || null,
    root_password: rootPassword,
    elevation_strategy: state.systemInspection?.privilege_decision || 'sudo',
    script_path: null,
    no_kiosk: noKiosk,
    skip_packages: false,
    mock_replay: isMock,
    channel,
  };

  appendLog(`[SYS] Démarrage du processus de déploiement sur ${params.host}...`);

  try {
    await invokeTauri('start_installation', { params });
  } catch (err) {
    appendLog(`[ERREUR CRITIQUE] ${err}`);
  }
}

function appendLog(line) {
  const terminal = document.getElementById('terminal-logs');
  const div = document.createElement('div');
  div.className = 'log-line';
  div.textContent = line;
  terminal.appendChild(div);
  terminal.scrollTop = terminal.scrollHeight;
}

function listenTauriEvents() {
  const listen = window.__TAURI__?.event?.listen;
  if (!listen) return;

  listen('install_progress', (event) => {
    const update = event.payload;
    const fill = document.getElementById('install-progress-fill');
    const label = document.getElementById('install-pct-label');
    const subtitle = document.getElementById('install-step-subtitle');

    fill.style.width = `${update.pct}%`;
    label.textContent = `${update.pct}%`;
    subtitle.textContent = `Étape ${update.step_index} sur ${update.total_steps} : ${update.step_title}`;

    if (update.phase === 'succeeded' || update.pct >= 100) {
      document.getElementById('install-title-heading').textContent = 'Installation terminée !';
      document.getElementById('install-success-card').style.display = 'flex';

      // Ouverture automatique des deux interfaces à la première détection du
      // succès (garde `installSuccessOpened` : cet évènement peut se répéter
      // à 100%, il ne faut ouvrir les onglets qu'une seule fois) — même
      // logique que l'installation CLI/appliance, qui affiche le kiosque
      // câblé de base sans action manuelle. L'utilisateur ferme l'onglet
      // d'administration lui-même s'il n'en a pas l'usage immédiat.
      if (!state.installSuccessOpened) {
        state.installSuccessOpened = true;
        window.open(adminUrl(), '_blank');
        window.open(kioskUrl(), '_blank');
      }
    }
  });

  listen('install_log', (event) => {
    appendLog(event.payload);
  });
}
