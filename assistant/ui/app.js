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

async function invokeTauri(cmd, args = {}) {
  const tauriInvoke = getTauriInvoke();
  if (tauriInvoke) {
    return await tauriInvoke(cmd, args);
  }
  console.log(`[IPC Mock] ${cmd}`, args);

  // Mocks pour prévisualisation navigateur standalone
  if (cmd === 'scan_network') {
    await new Promise(r => setTimeout(r, 1200));
    return [
      { ip: '10.0.0.30', hostname: 'pavilion-malefique.local', ssh_open: true, bobine_open: true, os_hint: 'Debian 13', is_wyse_or_bobine: true },
      { ip: '10.0.0.28', hostname: 'dev-pc.local', ssh_open: true, bobine_open: false, os_hint: 'Linux', is_wyse_or_bobine: false }
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
  return { status: 'ok' };
}

// État de l'application
const state = {
  currentStep: 1,
  selectedTarget: null,
  systemInspection: null,
  installSuccessOpened: false,
};

function init() {
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
        <p class="scanning-subtitle">Balayage des sous-réseaux locaux (SSH port 22, Bobine port 8000)...</p>
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
      devicesList.innerHTML = `<div class="empty-state"><p style="color: var(--accent-error);">Erreur lors du scan : ${err}</p></div>`;
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
// "canal Stable/Bêta") : l'assistant Tauri n'a pas de backend local à
// interroger (contrairement à BobineTray) — appel direct à l'API GitHub
// depuis le renderer. bobine-assistant n'embarque pas son propre numéro de
// version (cf. plan) : on ne peut donc pas dire "vous êtes en retard", mais
// on peut signaler "une version plus récente existe" en se souvenant du tag
// déjà vu/fermé (localStorage) pour ne le proposer qu'une fois par release.
const ASSISTANT_UPDATE_DISMISSED_KEY = 'bobine-assistant-update-dismissed-tag';
const GITHUB_RELEASES_LATEST_URL = 'https://api.github.com/repos/FantasmaGlad/Bobine/releases/latest';

async function checkAssistantUpdate() {
  try {
    const res = await fetch(GITHUB_RELEASES_LATEST_URL, {
      headers: { Accept: 'application/vnd.github+json' },
    });
    if (!res.ok) return;
    const release = await res.json();
    const tag = release.tag_name;
    if (!tag) return;

    let dismissedTag = null;
    try {
      dismissedTag = localStorage.getItem(ASSISTANT_UPDATE_DISMISSED_KEY);
    } catch {
      // localStorage indisponible (mode privé strict) : tant pis, pas de mémorisation.
    }
    if (tag === dismissedTag) return;

    const asset = (release.assets || []).find((a) => a.name === 'bobine-assistant');
    const downloadUrl = asset?.browser_download_url || release.html_url;

    const banner = document.getElementById('assistant-update-banner');
    const text = document.getElementById('assistant-update-text');
    if (!banner || !text) return;
    text.textContent = `Bobine Assistant ${tag} est disponible.`;
    banner.style.display = 'flex';

    document.getElementById('btn-assistant-update-download').onclick = () => {
      window.open(downloadUrl, '_blank');
    };
    document.getElementById('btn-assistant-update-dismiss').onclick = () => {
      banner.style.display = 'none';
      try {
        localStorage.setItem(ASSISTANT_UPDATE_DISMISSED_KEY, tag);
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
        <h4>Aucun appareil compatible trouvé</h4>
        <p>Aucune cible Debian avec le port SSH ouvert (22) n'a répondu sur les sous-réseaux locaux. Vérifiez que la borne est allumée et reliée au même réseau, ou saisissez son IP manuellement ci-dessus.</p>
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
    row.innerHTML = `
      <div class="device-info">
        <span class="device-ip">${dev.ip}</span>
        <div class="device-badges">
          ${dev.bobine_open ? '<span class="pill pill-success">Bobine Actif</span>' : ''}
          ${dev.ssh_open ? '<span class="pill pill-info">SSH Ouvert</span>' : ''}
          <span class="pill" style="background-color: var(--bg-surface-hover);">${dev.os_hint || 'Linux'}</span>
        </div>
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
