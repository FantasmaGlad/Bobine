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
// réseau RÉEL d'un jeu de données factice de démonstration.
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
      { ip: '203.0.113.10', hostname: 'exemple-borne-bobine.local', ssh_open: true, bobine_open: true, open_ports: [22, 1903], os_hint: 'Debian 13 (exemple)', is_wyse_or_bobine: true, mac: '02:00:5e:00:53:10', seen_via: 'ports' },
      { ip: '203.0.113.20', hostname: 'exemple-poste-admin.local', ssh_open: true, bobine_open: false, open_ports: [22], os_hint: 'Linux (exemple)', is_wyse_or_bobine: false, mac: null, seen_via: 'ports' },
      { ip: '203.0.113.30', hostname: null, ssh_open: false, bobine_open: false, open_ports: [], os_hint: null, is_wyse_or_bobine: false, mac: '02:00:5e:00:53:30', seen_via: 'arp' }
    ];
  }
  if (cmd === 'test_ssh_connection') {
    await new Promise(r => setTimeout(r, 800));
    return {
      host: args.creds?.host || '203.0.113.10',
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
  if (cmd === 'ssh_host_key') {
    return { host: args.host, port: args.port, fingerprint: 'SHA256:exemple', key_type: 'ssh-ed25519', status: 'known', known_hosts: '' };
  }
  if (cmd === 'check_assistant_update') {
    return { available: false, current: '0.0.0-dev', version: null, notes: null };
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
  // Port Bobine de la cible : celui vu au scan (1903, ou 8000 sur une appliance installée avant la 5.1.0),
  // puis celui annoncé par install.sh en fin d'installation.
  selectedBobinePort: null,
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

// Mémorisation locale (identifiant SSH...) : un geste en moins à chaque
// déploiement. Jamais de mot de passe ni de clé. Silencieux si indisponible.
function remember(key, value) {
  try { localStorage.setItem(`bobine-assistant:${key}`, value); } catch { /* mode privé strict */ }
}
function recall(key) {
  try { return localStorage.getItem(`bobine-assistant:${key}`); } catch { return null; }
}

function init() {
  renderPreviewModeBanner();
  const savedUser = recall('sshUsername');
  const userField = document.getElementById('ssh-username');
  if (savedUser && userField && !userField.value) userField.value = savedUser;
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
    <div id="live-devices"></div>
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

  const customNetworkInput = document.getElementById('custom-network-input');
  const btnScanCustom = document.getElementById('btn-scan-custom');

  async function runScan(customSubnet) {
    scanSpinner.classList.add('spinning');
    btnScan.classList.add('scanning');
    btnScan.disabled = true;
    if (btnScanCustom) btnScanCustom.disabled = true;
    if (btnScanLabel) btnScanLabel.textContent = 'Scan en cours...';

    state.liveDevices = new Map();
    renderScanningAnimation();
    updateScanProgress({ done: 0, total: 0, found: 0, networks: [] });

    try {
      const args = customSubnet ? { customSubnet } : {};
      const devices = await invokeTauri('scan_network', args);
      renderDevicesList(devices);
      remember('lastScanCount', String(devices.length));
    } catch (err) {
      devicesList.innerHTML = `<div class="empty-state"><p style="color: var(--accent-error);">Erreur lors du scan : ${escapeHtml(err)}</p></div>`;
    } finally {
      hideScanProgress();
      scanSpinner.classList.remove('spinning');
      btnScan.classList.remove('scanning');
      btnScan.disabled = false;
      if (btnScanCustom) btnScanCustom.disabled = false;
      if (btnScanLabel) btnScanLabel.textContent = 'Lancer le scan réseau';
    }
  }

  btnScan.addEventListener('click', () => runScan(null));
  btnScanCustom?.addEventListener('click', () => {
    const spec = customNetworkInput.value.trim();
    if (!spec) {
      customNetworkInput.focus();
      return;
    }
    runScan(spec);
  });
  customNetworkInput?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      btnScanCustom.click();
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
  // repli automatique sur ~/.ssh/)
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

    const username = document.getElementById('ssh-username').value.trim();
    if (!username) {
      // Aucun identifiant « par défaut » : l'ancien repli silencieux sur un
      // compte précis du mainteneur tentait une connexion avec un login que
      // personne d'autre n'a sur sa borne.
      if (sshErrorBanner && sshErrorDesc) {
        sshErrorDesc.textContent = "Saisissez l'identifiant du compte à utiliser sur la borne (celui créé à l'installation de Debian).";
        sshErrorBanner.style.display = 'block';
      }
      document.getElementById('ssh-username').focus();
      connectSpinner.classList.remove('spinning');
      btnConnectSsh.disabled = false;
      return;
    }
    remember('sshUsername', username);

    const creds = {
      host: document.getElementById('ssh-host').value,
      port: parseInt(document.getElementById('ssh-port').value, 10) || 22,
      username,
      password: document.getElementById('ssh-password').value || null,
      key_path: state.selectedKeyPath || null,
    };

    try {
      if (!(await ensureTrustedHost(creds.host, creds.port))) return;
      const inspection = await invokeTauri('test_ssh_connection', { creds });
      state.systemInspection = inspection;
      renderSystemSpecs(inspection);
      goToStep(3);
    } catch (err) {
      if (sshErrorBanner && sshErrorDesc) {
        sshErrorDesc.textContent = err?.message || err;
        sshErrorBanner.style.display = 'block';
      } else {
        alert(`Erreur de connexion SSH : ${err?.message || err}`);
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

  document.getElementById('btn-retry-install').addEventListener('click', () => {
    hideInstallFailure();
    goToStep(4);
  });
  document.getElementById('btn-copy-logs').addEventListener('click', async (e) => {
    const text = Array.from(document.querySelectorAll('#terminal-logs .log-line')).map((l) => l.textContent).join('\n');
    const button = e.currentTarget;
    try {
      await navigator.clipboard.writeText(text);
      button.textContent = 'Journal copié';
    } catch {
      button.textContent = 'Copie impossible — sélectionnez le journal à la main';
    }
  });

  document.getElementById('btn-open-browser').addEventListener('click', () => {
    window.open(adminUrl(), '_blank');
  });

  document.getElementById('btn-open-kiosk').addEventListener('click', () => {
    window.open(kioskUrl(), '_blank');
  });
}

function adminUrl() {
  const target = state.selectedTarget || '203.0.113.10';
  return `http://${target}:${state.selectedBobinePort || 1903}`;
}

function kioskUrl() {
  return `${adminUrl()}/kiosk`;
}

// Mise à jour de l'assistant lui-même (commandes Rust `check_assistant_update` et `install_assistant_update`, greffon
// de mise à jour de Tauri) : version lue dans `latest.json` de la release du canal de ce build, paquet vérifié par sa
// signature avant installation, puis relance. Une version écartée par « Plus tard » n'est plus proposée.
const ASSISTANT_UPDATE_DISMISSED_KEY = 'bobine-assistant-update-dismissed';

function renderAppVersionBadge(version, commit) {
  const badge = document.getElementById('app-version-badge');
  if (!badge || !version) return;
  const shortCommit = (commit && commit !== 'unknown') ? ` (${commit})` : '';
  badge.textContent = `v${version}${shortCommit}`;
  badge.hidden = false;
}

async function checkAssistantUpdate() {
  try {
    const info = await invokeTauri('get_app_info', {});
    renderAppVersionBadge(info?.version, info?.commit);
  } catch {
    // Version illisible : le badge reste masqué, la recherche de mise à jour continue.
  }

  let update;
  try {
    update = await invokeTauri('check_assistant_update', {});
  } catch {
    return; // Hors ligne ou release du canal indisponible : silencieux, comme le reste de l'assistant.
  }
  if (!update?.available || !update.version) return;

  let dismissed = null;
  try {
    dismissed = localStorage.getItem(ASSISTANT_UPDATE_DISMISSED_KEY);
  } catch {
    // localStorage indisponible (mode privé strict) : pas de mémorisation.
  }
  if (dismissed === update.version) return;

  const banner = document.getElementById('assistant-update-banner');
  const text = document.getElementById('assistant-update-text');
  const install = document.getElementById('btn-assistant-update-install');
  const dismiss = document.getElementById('btn-assistant-update-dismiss');
  if (!banner || !text || !install || !dismiss) return;
  text.textContent = `Bobine Assistant ${update.version} est disponible (version installée : ${update.current}).`;
  banner.style.display = 'flex';

  install.onclick = async () => {
    install.disabled = true;
    dismiss.disabled = true;
    text.textContent = `Téléchargement de Bobine Assistant ${update.version}…`;
    const listen = window.__TAURI__?.event?.listen;
    let unlisten = null;
    try {
      if (listen) {
        unlisten = await listen('assistant-update-progress', (event) => {
          const { downloaded, total } = event.payload || {};
          if (total) text.textContent = `Téléchargement : ${Math.floor((100 * downloaded) / total)} %`;
        });
      }
      await invokeTauri('install_assistant_update', {}); // relance l'assistant en cas de succès
    } catch (error) {
      unlisten?.();
      text.textContent = `La mise à jour a échoué : ${error}. Bobine n'est pas touché ; réessayez plus tard.`;
      install.disabled = false;
      dismiss.disabled = false;
    }
  };
  dismiss.onclick = () => {
    banner.style.display = 'none';
    try {
      localStorage.setItem(ASSISTANT_UPDATE_DISMISSED_KEY, update.version);
    } catch {
      // idem : pas bloquant si indisponible.
    }
  };
}

// Clé d'hôte SSH vérifiée avant tout envoi de mot de passe (host_key.rs) : une machine inconnue n'est enregistrée
// qu'après confirmation de son empreinte ; une clé qui a changé est refusée (une autre machine peut usurper la borne).
async function ensureTrustedHost(host, port) {
  const key = await invokeTauri('ssh_host_key', { host, port });
  if (key.status === 'known') return true;
  if (key.status === 'changed') {
    throw new Error(`La clé d'hôte de ${host} a changé (${key.fingerprint}) : connexion refusée. Si la borne a été réinstallée, retirez l'ancienne entrée avec « ssh-keygen -R ${host} », puis recommencez.`);
  }
  const message = `Première connexion à ${host} : vérifiez que l'empreinte de sa clé SSH est bien celle de la borne.\n\n`
    + `${key.key_type}\n${key.fingerprint}\n\n`
    + `Sur la borne : ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub\n\nFaire confiance à cette machine ?`;
  const ask = window.__TAURI__?.dialog?.ask;
  const accepted = ask
    ? await ask(message, { title: 'Nouvelle machine', kind: 'warning', okLabel: 'Faire confiance', cancelLabel: 'Annuler' })
    : window.confirm(message);
  if (!accepted) throw new Error("Connexion annulée : l'empreinte de la machine n'a pas été confirmée.");
  await invokeTauri('trust_ssh_host_key', { host, port, fingerprint: key.fingerprint });
  return true;
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
        <p>Aucun appareil n'a répondu sur le réseau de ce poste. Causes les plus fréquentes :</p>
        <ul class="empty-hints">
          <li>la borne est éteinte ou n'est pas encore branchée au réseau ;</li>
          <li>ce poste et la borne ne sont pas sur le même réseau (Wi-Fi invité, second routeur, VPN actif) — utilisez « Scanner un autre réseau » ;</li>
          <li>le Wi-Fi isole les appareils entre eux (« isolation AP », réseau invité) : branchez la borne en Ethernet sur le même routeur ou saisissez son adresse IP ci-dessus.</li>
        </ul>
        <button id="btn-retry-scan" class="btn btn-secondary btn-sm" style="margin-top: 6px;">Relancer le scan</button>
      </div>
    `;
    document.getElementById('btn-retry-scan')?.addEventListener('click', () => {
      document.getElementById('btn-scan')?.click();
    });
    return;
  }

  container.innerHTML = '';
  devices.forEach((dev) => container.appendChild(buildDeviceRow(dev)));
}

function buildDeviceRow(dev, animate = false) {
  const row = document.createElement('div');
  row.className = `device-row ${dev.is_wyse_or_bobine ? 'selected' : ''}${animate ? ' device-enter' : ''}`;
  const ports = (dev.open_ports || []).join(', ');
  const via = dev.seen_via === 'arp'
    ? 'Présent sur le réseau (aucun port ouvert — pare-feu)'
    : dev.seen_via === 'mdns' ? 'Trouvé par son nom bobine.local' : '';
  // Toute valeur issue du réseau passe par escapeHtml (cf. en-tête du fichier).
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
      ${via ? `<span class="device-ports">${escapeHtml(via)}</span>` : ''}
      ${dev.mac ? `<span class="device-mac">${escapeHtml(dev.mac)}</span>` : ''}
    </div>
    <button class="btn btn-secondary btn-sm select-btn">Sélectionner</button>
  `;
  row.querySelector('.select-btn').addEventListener('click', () => {
    selectTarget(dev.ip, dev.open_ports);
    goToStep(2);
  });
  return row;
}

function updateScanProgress({ done, total, found, networks }) {
  const box = document.getElementById('scan-progress');
  if (!box) return;
  box.style.display = 'flex';
  const pct = total > 0 ? Math.min(100, Math.round((done * 100) / total)) : 0;
  document.getElementById('scan-progress-fill').style.width = `${pct}%`;
  const nets = (networks || []).length ? ` · réseau : ${networks.join(', ')}` : '';
  const text = total > 0
    ? `${done}/${total} adresses sondées · ${found} appareil${found > 1 ? 's' : ''} trouvé${found > 1 ? 's' : ''}${nets}`
    : 'Préparation du scan…';
  document.getElementById('scan-progress-text').textContent = text;
}

function hideScanProgress() {
  const box = document.getElementById('scan-progress');
  if (box) box.style.display = 'none';
}

function selectTarget(ip, openPorts = []) {
  state.selectedTarget = ip;
  state.selectedBobinePort = openPorts.includes(1903) ? 1903 : openPorts.includes(8000) ? 8000 : null;
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
  const channel = document.querySelector('input[name="update-channel"]:checked')?.value || 'stable';
  const rootPassword = document.getElementById('ssh-root-password')?.value || null;

  const params = {
    host: state.selectedTarget || '203.0.113.10',
    port: parseInt(document.getElementById('ssh-port').value, 10) || 22,
    username: document.getElementById('ssh-username').value.trim(),
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

  hideInstallFailure();
  try {
    await invokeTauri('start_installation', { params });
  } catch (err) {
    appendLog(`[ERREUR CRITIQUE] ${err}`);
    showInstallFailure(String(err));
  }
}

function showInstallFailure(message) {
  document.getElementById('install-title-heading').textContent = "L'installation s'est arrêtée";
  document.getElementById('install-failure-message').textContent = message;
  document.getElementById('install-failure-card').style.display = 'block';
}

function hideInstallFailure() {
  document.getElementById('install-failure-card').style.display = 'none';
  document.getElementById('install-title-heading').textContent = 'Déploiement en cours...';
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

  // Scan en direct : chaque appareil apparaît dès qu'il est trouvé, au lieu
  // d'attendre la fin d'un balayage de plusieurs centaines d'adresses.
  listen('scan_device', (event) => {
    const dev = event.payload;
    const live = document.getElementById('live-devices');
    if (!live || !dev) return;
    state.liveDevices = state.liveDevices || new Map();
    if (state.liveDevices.has(dev.ip)) return;
    state.liveDevices.set(dev.ip, dev);
    live.appendChild(buildDeviceRow(dev, true));
  });
  listen('scan_progress', (event) => updateScanProgress(event.payload));

  listen('install_progress', (event) => {
    const update = event.payload;
    const fill = document.getElementById('install-progress-fill');
    const label = document.getElementById('install-pct-label');
    const subtitle = document.getElementById('install-step-subtitle');

    fill.style.width = `${update.pct}%`;
    label.textContent = `${update.pct}%`;
    subtitle.textContent = `Étape ${update.step_index} sur ${update.total_steps} : ${update.step_title}`;

    if (update.phase === 'failed') {
      showInstallFailure(update.error_message || "Une étape de l'installation a échoué.");
      return;
    }

    if (update.access_port) state.selectedBobinePort = update.access_port;

    // Seul `run_end` (phase succeeded) vaut succès : un simple `pct: 100`
    // peut précéder un échec réel, et le code de sortie distant fait foi.
    if (update.phase === 'succeeded') {
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
