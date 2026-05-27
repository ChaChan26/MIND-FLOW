// MIND-FLOW Dashboard Logic

// Global Uncaught Error Tracker for debugging WebView2 client issues
window.addEventListener('error', function(event) {
    const errorMsg = `JS Error: ${event.message} at ${event.filename || 'script'}:${event.lineno}:${event.colno}`;
    console.error(errorMsg);
    if (typeof showToast === 'function') {
        showToast(errorMsg, true);
    }
});

// Security: HTML escape helper to prevent XSS in innerHTML injections
function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
}

let currentTab = 'dashboard';
let statusInterval = null;
let lastActiveTitle = '';
let lastExternalWindow = 'None';
let lastExternalProcess = 'None';
let lastWeekdaySummary = null;
let lastReflections = null;
let appStatsData = [];
let appStatsFilter = 'today';

// DOM Elements
const bodyEl = document.body;
const timeEl = document.getElementById('live-time');
const batteryFill = document.getElementById('battery-fill');
const batteryPct = document.getElementById('battery-pct');
const batteryStatusMsg = document.getElementById('battery-status-msg');
const statusRingCircle = document.getElementById('status-ring-circle');
const statusIcon = document.getElementById('status-icon');
const currentModeTitle = document.getElementById('current-mode-title');
const blockTimer = document.getElementById('block-timer');
const activeAppName = document.getElementById('active-app-name');
const toggleShieldBtn = document.getElementById('toggle-shield-btn');
const trackingPulse = document.getElementById('tracking-pulse');
const trackingStatusText = document.getElementById('tracking-status-text');

// Glow Elements
const glow1 = document.getElementById('glow-1');
const glow2 = document.getElementById('glow-2');

// Ratings Selectors (Quick Reflection)
let selectedEnergy = 5;
let selectedFriction = 2;

document.querySelectorAll('#energy-rating .rate-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('#energy-rating .rate-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        selectedEnergy = parseInt(btn.getAttribute('data-val'));
        
        btn.classList.add('clicked');
        setTimeout(() => btn.classList.remove('clicked'), 400);
    });
});

document.querySelectorAll('#friction-rating .rate-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('#friction-rating .rate-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        selectedFriction = parseInt(btn.getAttribute('data-val'));
        
        btn.classList.add('clicked');
        setTimeout(() => btn.classList.remove('clicked'), 400);
    });
});

// Tab Navigation
function switchTab(tabId) {
    if (tabId !== 'settings' && typeof checkSettingsDirty === 'function' && checkSettingsDirty()) {
        if (!confirm("You have unsaved preferences changes. Do you want to leave without applying?")) {
            // Restore active state on settings button
            const settingsBtn = document.getElementById('nav-btn-settings');
            if (settingsBtn) {
                document.querySelectorAll('.nav-btn').forEach(btn => btn.classList.remove('active'));
                settingsBtn.classList.add('active');
            }
            return;
        } else {
            discardSettingsChanges();
        }
    }
    currentTab = tabId;
    document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(btn => btn.classList.remove('active'));
    
    const activeTab = document.getElementById(`tab-${tabId}`);
    const activeBtn = document.getElementById(`nav-btn-${tabId}`);
    if (activeTab) activeTab.classList.add('active');
    if (activeBtn) activeBtn.classList.add('active');
    
    // Instant scroll to top to prevent animation overhead during tab shifts
    const mainContent = document.querySelector('.main-content');
    if (mainContent) {
        mainContent.scrollTop = 0;
    }
    
    // Defer reading layout properties to the next animation frame
    requestAnimationFrame(() => {
        updateNavIndicator();
    });
    
    if (tabId === 'analytics') {
        loadAnalytics();
        stopZenCanvas();
    } else if (tabId === 'settings') {
        loadSettings();
        stopZenCanvas();
    } else if (tabId === 'zen') {
        initZenCanvas();
    } else {
        stopZenCanvas();
    }
}

// Update Sidebar Sliding Tab Indicator Position and Colors
function updateNavIndicator() {
    const activeBtn = document.querySelector('.nav-btn.active');
    const indicator = document.getElementById('nav-indicator');
    if (activeBtn && indicator) {
        indicator.style.opacity = '1';
        indicator.style.top = `${activeBtn.offsetTop}px`;
        indicator.style.height = `${activeBtn.offsetHeight}px`;
        indicator.style.width = `${activeBtn.offsetWidth}px`;
        
        // Dynamically match active mode's color token
        const isWork = bodyEl.classList.contains('mode-work');
        const isRecharge = bodyEl.classList.contains('mode-recharge');
        const isRest = bodyEl.classList.contains('mode-rest');
        
        let borderCol = 'rgba(148, 163, 184, 0.25)';
        let bgCol = 'rgba(148, 163, 184, 0.08)';
        let shadowCol = 'rgba(148, 163, 184, 0.05)';
        
        if (isWork) {
            borderCol = 'rgba(180, 154, 255, 0.3)';
            bgCol = 'rgba(180, 154, 255, 0.08)';
            shadowCol = 'rgba(180, 154, 255, 0.1)';
        } else if (isRecharge) {
            borderCol = 'rgba(45, 212, 168, 0.3)';
            bgCol = 'rgba(45, 212, 168, 0.08)';
            shadowCol = 'rgba(45, 212, 168, 0.1)';
        } else if (isRest) {
            borderCol = 'rgba(251, 191, 36, 0.3)';
            bgCol = 'rgba(251, 191, 36, 0.08)';
            shadowCol = 'rgba(251, 191, 36, 0.1)';
        }
        
        indicator.style.borderColor = borderCol;
        indicator.style.background = bgCol;
        indicator.style.boxShadow = `0 0 15px ${shadowCol}`;
    } else if (indicator) {
        indicator.style.opacity = '0';
    }
}
window.addEventListener('load', () => {
    updateNavIndicator();
    const volSlider = document.getElementById('audio-volume-slider');
    if (volSlider) {
        updateVolumeSliderBackground(volSlider);
    }
});

// Live Clock Update
function updateClock() {
    const now = new Date();
    let hours = now.getHours();
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const ampm = hours >= 12 ? 'PM' : 'AM';
    hours = hours % 12;
    hours = hours ? hours : 12; // 0 should be 12
    timeEl.textContent = `${hours}:${minutes} ${ampm}`;
}
setInterval(updateClock, 1000);
updateClock();

// Animate BG glow slightly based on mouse move to feel organic (optimized with requestAnimationFrame & GPU acceleration)
let glowTicking = false;
let glowMouseX = 0;
let glowMouseY = 0;

document.addEventListener('mousemove', (e) => {
    glowMouseX = e.clientX;
    glowMouseY = e.clientY;
    
    if (!glowTicking) {
        requestAnimationFrame(updateGlow);
        glowTicking = true;
    }
});

function updateGlow() {
    const x = glowMouseX / window.innerWidth;
    const y = glowMouseY / window.innerHeight;
    
    glow1.style.transform = `translate3d(${x * 30}px, ${y * 30}px, 0)`;
    glow2.style.transform = `translate3d(${-x * 40}px, ${-y * 40}px, 0)`;
    glowTicking = false;
}

// 3D Card Tilt Effect (Optimized with cached dimensions and requestAnimationFrame)
document.querySelectorAll('.card').forEach(card => {
    let rect = null;
    let cardTicking = false;
    let localMouseX = 0;
    let localMouseY = 0;
    
    card.addEventListener('mouseenter', () => {
        rect = card.getBoundingClientRect();
        card.style.transition = 'transform 0.1s ease-out, border-color 0.3s ease, box-shadow 0.4s ease';
    });
    
    card.addEventListener('mousemove', (e) => {
        if (!rect) rect = card.getBoundingClientRect();
        localMouseX = e.clientX - rect.left;
        localMouseY = e.clientY - rect.top;
        
        if (!cardTicking) {
            requestAnimationFrame(updateCardTilt);
            cardTicking = true;
        }
    });
    
    function updateCardTilt() {
        if (!rect) {
            cardTicking = false;
            return;
        }
        card.style.setProperty('--mouse-x', `${localMouseX}px`);
        card.style.setProperty('--mouse-y', `${localMouseY}px`);
        
        const centerX = rect.width / 2;
        const centerY = rect.height / 2;
        const rotateX = ((localMouseY - centerY) / centerY) * -3;
        const rotateY = ((localMouseX - centerX) / centerX) * 3;
        card.style.transform = `perspective(800px) rotate3d(1, 0, 0, ${rotateX}deg) rotate3d(0, 1, 0, ${rotateY}deg) translate3d(0, -4px, 0)`;
        cardTicking = false;
    }
    
    card.addEventListener('mouseleave', () => {
        rect = null;
        card.style.transition = 'transform 0.6s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.4s ease, box-shadow 0.4s ease';
        card.style.transform = 'perspective(800px) rotate3d(1, 0, 0, 0deg) rotate3d(0, 1, 0, 0deg) translate3d(0, 0, 0)';
    });
});

// Format Seconds -> MM:SS
function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

// Show Custom Toast Notification with icon and progress bar
function showToast(message, isError = false) {
    const toast = document.getElementById('app-toast');
    const toastIcon = document.getElementById('toast-icon');
    const toastText = document.getElementById('toast-text');
    const toastProgress = document.getElementById('toast-progress');
    
    if (toastText) toastText.textContent = message;
    if (toastIcon) toastIcon.textContent = isError ? '✗' : '✓';
    
    // Reset progress bar animation
    if (toastProgress) {
        toastProgress.style.animation = 'none';
        toastProgress.offsetHeight; // force reflow
        toastProgress.style.animation = 'toast-countdown 3s linear forwards';
    }
    
    if (isError) {
        toast.style.background = 'rgba(239, 68, 68, 0.95)';
        toast.style.borderColor = '#ef4444';
        toast.style.boxShadow = '0 10px 25px rgba(239, 68, 68, 0.3)';
    } else {
        toast.style.background = 'rgba(16, 185, 129, 0.95)';
        toast.style.borderColor = '#10b981';
        toast.style.boxShadow = '0 10px 25px rgba(16, 185, 129, 0.3)';
    }
    toast.classList.add('show');
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// Animated value counter for smooth transitions
function animateValue(element, start, end, suffix = '%', duration = 500) {
    const range = end - start;
    if (range === 0) return;
    const startTime = performance.now();
    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        const current = Math.round(start + range * eased);
        element.textContent = current + suffix;
        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }
    requestAnimationFrame(update);
}

// Poll Active System Status
async function pollStatus() {
    try {
        const res = await fetch('/api/status');
        if (!res.ok) throw new Error("Status API error");
        const status = await res.json();
        
        // 1. Update Body classes for mode specific glows (only on changes to prevent layout thrashing)
        const activeMode = status.current_mode || 'neutral';
        if (!bodyEl.classList.contains(`mode-${activeMode}`)) {
            bodyEl.className = '';
            bodyEl.classList.add(`mode-${activeMode}`);
            requestAnimationFrame(() => {
                updateNavIndicator();
            });
        }
        
        // 2. Status Details
        currentModeTitle.textContent = `${status.current_mode} mode`;
        activeAppName.textContent = status.active_window_title;
        
        const activeProcessEl = document.getElementById('active-process-display');
        if (activeProcessEl) {
            activeProcessEl.textContent = `Process: ${status.active_process_name}`;
        }
        
        const adviceEl = document.getElementById('companion-advice-text');
        if (adviceEl && status.companion_message) {
            adviceEl.textContent = status.companion_message;
        }
        
        lastActiveTitle = status.active_window_title;
        lastExternalWindow = status.last_external_window;
        lastExternalProcess = status.last_external_process;
        
        const actionContainer = document.getElementById('active-app-actions-container');
        if (actionContainer) {
            const isInvalid = !status.last_external_window || 
                              status.last_external_window === "None" || 
                              status.last_external_window === "None Detected" || 
                              status.last_external_window === "Companion Paused" || 
                              status.last_external_window === "Offline";
            
            actionContainer.style.display = isInvalid ? 'none' : 'flex';
            
            if (!isInvalid) {
                const cleanKw = extractCleanKeyword(status.last_external_window, status.last_external_process);
                
                const addWorkBtn = document.querySelector('.work-add-btn');
                const addRechargeBtn = document.querySelector('.recharge-add-btn');
                if (addWorkBtn && addRechargeBtn) {
                    addWorkBtn.textContent = `+ Work ("${cleanKw}")`;
                    addRechargeBtn.textContent = `+ Recharge ("${cleanKw}")`;
                }
            }
        }
        
        // 3. Block Timer (Enforce counts up or counts down visually) and Radial Progress
        let progress = 0;
        if (status.current_mode === 'work') {
            const limit = status.adaptive_work_limit_seconds || 2700;
            const remaining = Math.max(0, limit - status.elapsed_seconds);
            blockTimer.textContent = formatTime(remaining);
            if (remaining < 60) {
                blockTimer.style.color = '#ef4444'; // Red alarm for last minute
            } else {
                blockTimer.style.color = 'var(--work-color)';
            }
            progress = Math.max(0, Math.min(1, remaining / limit));
        } else if (status.current_mode === 'recharge') {
            blockTimer.textContent = formatTime(status.elapsed_seconds);
            blockTimer.style.color = 'var(--recharge-color)';
            const limit = status.adaptive_rest_limit_seconds || 20;
            progress = Math.max(0, Math.min(1, status.elapsed_seconds / limit));
        } else if (status.current_mode === 'rest') {
            blockTimer.textContent = formatTime(status.idle_seconds);
            blockTimer.style.color = 'var(--rest-color)';
            const limit = status.adaptive_rest_limit_seconds || 20;
            progress = Math.max(0, Math.min(1, status.idle_seconds / limit));
        } else {
            blockTimer.textContent = "00:00";
            blockTimer.style.color = 'var(--text-secondary)';
            progress = 0;
        }

        // Update SVG circle dashoffset
        if (statusRingCircle) {
            const circumference = 210.5;
            const offset = circumference * (1 - progress);
            statusRingCircle.style.strokeDashoffset = offset;
        }
        
        // 3.5. Update Adaptive Timers badge
        const badgeEl = document.getElementById('adaptive-badge');
        if (badgeEl) {
            badgeEl.textContent = status.adaptive_reason;
            badgeEl.className = 'adaptive-status-badge';
            
            const reasonLower = status.adaptive_reason.toLowerCase();
            if (reasonLower.includes('flow')) {
                badgeEl.classList.add('flow');
            } else if (reasonLower.includes('fatigue') || reasonLower.includes('rest alert')) {
                badgeEl.classList.add('fatigue');
            } else if (reasonLower.includes('bypass') || reasonLower.includes('deficit')) {
                badgeEl.classList.add('bypassed');
            }
        }
        
        // 4. Emojis and Rings
        let emoji = '⚪';
        
        if (status.current_mode === 'work') {
            emoji = '💻';
        } else if (status.current_mode === 'recharge') {
            emoji = '🎮';
        } else if (status.current_mode === 'rest') {
            emoji = '💤';
        }
        statusIcon.textContent = emoji;
        
        // 5. Update live battery representation
        const energyPct = status.current_energy * 20; // 1-5 -> 20%-100%
        batteryFill.style.width = `${energyPct}%`;
        const prevPct = parseInt(batteryPct.textContent) || 0;
        if (prevPct !== energyPct) {
            animateValue(batteryPct, prevPct, energyPct, '%', 800);
        }
        
        // Update battery charge/discharge label
        const chargeIndicator = document.getElementById('battery-charge-status');
        if (status.current_mode === 'work') {
            chargeIndicator.textContent = '❌ discharging';
            chargeIndicator.style.color = '#ef4444';
        } else if (status.current_mode === 'recharge' || status.current_mode === 'rest') {
            chargeIndicator.textContent = '⚡ charging';
            chargeIndicator.style.color = 'var(--recharge-color)';
        } else {
            chargeIndicator.textContent = '⏳ holding';
            chargeIndicator.style.color = 'var(--text-secondary)';
        }

        // Trigger dynamic liquid battery bubbles
        updateBatteryBubbles(status.current_mode === 'recharge' || status.current_mode === 'rest');

        // Update session duration statistics
        const formatDuration = (seconds) => {
            const h = Math.floor(seconds / 3600);
            const m = Math.floor((seconds % 3600) / 60);
            return `${h}h ${m}m`;
        };
        document.getElementById('stat-work-time').textContent = formatDuration(status.today_work_seconds);
        document.getElementById('stat-recharge-time').textContent = formatDuration(status.today_recharge_seconds);
        document.getElementById('stat-rest-time').textContent = formatDuration(status.today_rest_seconds);
        
        // Change battery color background based on percentage
        if (status.current_energy <= 2) {
            batteryFill.style.backgroundColor = '#ef4444';
            batteryFill.style.boxShadow = '0 0 15px rgba(239, 68, 68, 0.4)';
            batteryStatusMsg.textContent = 'You\'re running low. Time for a gentle break to recharge.';
            batteryStatusMsg.style.color = '#ef4444';
        } else if (status.current_energy === 3) {
            batteryFill.style.backgroundColor = '#f59e0b';
            batteryFill.style.boxShadow = '0 0 15px rgba(245, 158, 11, 0.4)';
            batteryStatusMsg.textContent = 'Moderate energy. A short break soon would feel nice.';
            batteryStatusMsg.style.color = '#f59e0b';
        } else {
            batteryFill.style.backgroundColor = '#10b981';
            batteryFill.style.boxShadow = '0 0 15px rgba(16, 185, 129, 0.4)';
            batteryStatusMsg.textContent = 'Feeling great! Keep going, and remember to rest when you need it.';
            batteryStatusMsg.style.color = 'var(--text-secondary)';
        }
        
        // 6. Companion Companion State Toggle Status
        if (status.tracking_active) {
            trackingPulse.style.backgroundColor = 'var(--recharge-color)';
            trackingPulse.style.boxShadow = '0 0 8px var(--recharge-color)';
            trackingStatusText.textContent = "Companion Active";
            toggleShieldBtn.textContent = "Pause Companion";
            toggleShieldBtn.style.color = 'var(--text-primary)';
            toggleShieldBtn.style.background = 'rgba(255, 255, 255, 0.06)';
        } else {
            trackingPulse.style.backgroundColor = '#ef4444';
            trackingPulse.style.boxShadow = '0 0 8px #ef4444';
            trackingStatusText.textContent = "Companion Paused";
            toggleShieldBtn.textContent = "Resume Companion";
            toggleShieldBtn.style.background = 'rgba(16, 185, 129, 0.1)';
            toggleShieldBtn.style.color = 'var(--recharge-color)';
        }
        
        // 7. Update Focus Intention Goal UI if set
        if (status.current_goal !== undefined) {
            updateGoalUI(status.current_goal);
        }
        
        // 7.5 Update Daily Hydration UI if set
        if (status.hydration !== undefined) {
            updateHydrationUI(status.hydration);
        }
        
    } catch (e) {
        console.error("Failed status poll: ", e);
        currentModeTitle.textContent = 'Offline';
        activeAppName.textContent = 'App not responding...';
    }
}

// Toggle Tracking on click
toggleShieldBtn.addEventListener('click', async () => {
    try {
        const res = await fetch('/api/status/toggle', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });
        const status = await res.json();
        showToast(status.tracking_active ? "Cognitive Companion Activated" : "Cognitive Companion Deactivated");
        pollStatus();
    } catch (e) {
        showToast("Error updating tracker state", true);
    }
});

// Floating Settings Changes Dirty Tracking
let initialSettings = null;
let dirtyTrackingInitialized = false;

function checkSettingsDirty() {
    if (!initialSettings) return false;
    
    const workLimit = document.getElementById('work-limit-input');
    const idleTimeout = document.getElementById('idle-timeout-input');
    const restDuration = document.getElementById('rest-duration-input');
    const workKeywords = document.getElementById('work-keywords-input');
    const rechargeKeywords = document.getElementById('recharge-keywords-input');
    const autopilot = document.getElementById('autopilot-input');
    const eyecare = document.getElementById('eyecare-input');
    const hydrationTarget = document.getElementById('hydration-target-input');
    const hydrationUnit = document.getElementById('hydration-unit-input');
    const hydrationIncrement = document.getElementById('hydration-increment-input');
    
    if (!workLimit || !idleTimeout || !restDuration || !workKeywords || !rechargeKeywords || !autopilot || !eyecare || !hydrationTarget || !hydrationUnit || !hydrationIncrement) {
        return false;
    }
    
    const current = {
        work_duration_minutes: parseInt(workLimit.value) || 0,
        idle_timeout_seconds: parseInt(idleTimeout.value) || 0,
        rest_duration_seconds: parseInt(restDuration.value) || 0,
        work_keywords: workKeywords.value,
        recharge_keywords: rechargeKeywords.value,
        adaptive_timers_enabled: autopilot.checked,
        eye_care_mode: eyecare.checked,
        hydration_target: parseInt(hydrationTarget.value) || 8,
        hydration_unit: hydrationUnit.value,
        hydration_increment: parseFloat(hydrationIncrement.value) || 1
    };
    
    const isDirty = (
        current.work_duration_minutes !== initialSettings.work_duration_minutes ||
        current.idle_timeout_seconds !== initialSettings.idle_timeout_seconds ||
        current.rest_duration_seconds !== initialSettings.rest_duration_seconds ||
        current.work_keywords !== initialSettings.work_keywords ||
        current.recharge_keywords !== initialSettings.recharge_keywords ||
        current.adaptive_timers_enabled !== initialSettings.adaptive_timers_enabled ||
        current.eye_care_mode !== initialSettings.eye_care_mode ||
        current.hydration_target !== initialSettings.hydration_target ||
        current.hydration_unit !== initialSettings.hydration_unit ||
        current.hydration_increment !== initialSettings.hydration_increment
    );
    
    const banner = document.getElementById('unsaved-changes-banner');
    if (banner) {
        if (isDirty) {
            banner.classList.add('show');
        } else {
            banner.classList.remove('show');
        }
    }
    return isDirty;
}

function discardSettingsChanges() {
    if (!initialSettings) return;
    
    const workLimit = document.getElementById('work-limit-input');
    const idleTimeout = document.getElementById('idle-timeout-input');
    const restDuration = document.getElementById('rest-duration-input');
    const workKeywords = document.getElementById('work-keywords-input');
    const rechargeKeywords = document.getElementById('recharge-keywords-input');
    const autopilot = document.getElementById('autopilot-input');
    const eyecare = document.getElementById('eyecare-input');
    const hydrationTarget = document.getElementById('hydration-target-input');
    const hydrationUnit = document.getElementById('hydration-unit-input');
    const hydrationIncrement = document.getElementById('hydration-increment-input');
    
    if (workLimit) workLimit.value = initialSettings.work_duration_minutes;
    if (idleTimeout) idleTimeout.value = initialSettings.idle_timeout_seconds;
    if (restDuration) restDuration.value = initialSettings.rest_duration_seconds;
    if (workKeywords) workKeywords.value = initialSettings.work_keywords;
    if (rechargeKeywords) rechargeKeywords.value = initialSettings.recharge_keywords;
    if (autopilot) autopilot.checked = initialSettings.adaptive_timers_enabled;
    if (eyecare) {
        eyecare.checked = initialSettings.eye_care_mode;
        if (initialSettings.eye_care_mode) {
            document.body.classList.add('eye-care-active');
        } else {
            document.body.classList.remove('eye-care-active');
        }
    }
    if (hydrationTarget) hydrationTarget.value = initialSettings.hydration_target;
    if (hydrationUnit) hydrationUnit.value = initialSettings.hydration_unit;
    if (hydrationIncrement) hydrationIncrement.value = initialSettings.hydration_increment;
    
    checkSettingsDirty();
}

function applySettingsChanges() {
    const form = document.getElementById('settings-form');
    if (form) {
        if (typeof form.requestSubmit === 'function') {
            form.requestSubmit();
        } else {
            form.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
        }
    }
}

function initSettingsDirtyTracking() {
    if (dirtyTrackingInitialized) return;
    const settingsForm = document.getElementById('settings-form');
    if (settingsForm) {
        settingsForm.querySelectorAll('input, textarea, select').forEach(input => {
            input.addEventListener('input', checkSettingsDirty);
            input.addEventListener('change', checkSettingsDirty);
        });
        dirtyTrackingInitialized = true;
    }
}

// Load Settings from Backend
async function loadSettings() {
    try {
        const res = await fetch('/api/settings');
        const settings = await res.json();
        
        document.getElementById('work-limit-input').value = settings.work_duration_minutes;
        document.getElementById('idle-timeout-input').value = settings.idle_timeout_seconds;
        document.getElementById('rest-duration-input').value = settings.rest_duration_seconds || 20;
        document.getElementById('work-keywords-input').value = settings.work_keywords.join(', ');
        document.getElementById('recharge-keywords-input').value = settings.recharge_keywords.join(', ');
        document.getElementById('autopilot-input').checked = settings.adaptive_timers_enabled !== false;
        
        const eyeCareEnabled = settings.eye_care_mode === true;
        document.getElementById('eyecare-input').checked = eyeCareEnabled;
        if (eyeCareEnabled) {
            document.body.classList.add('eye-care-active');
        } else {
            document.body.classList.remove('eye-care-active');
        }
        
        document.getElementById('hydration-target-input').value = settings.hydration_target !== undefined ? settings.hydration_target : 8;
        document.getElementById('hydration-unit-input').value = settings.hydration_unit || "cups";
        document.getElementById('hydration-increment-input').value = settings.hydration_increment !== undefined ? settings.hydration_increment : 1;
        
        // Cache initial settings
        initialSettings = {
            work_duration_minutes: settings.work_duration_minutes,
            idle_timeout_seconds: settings.idle_timeout_seconds,
            rest_duration_seconds: settings.rest_duration_seconds || 20,
            work_keywords: settings.work_keywords.join(', '),
            recharge_keywords: settings.recharge_keywords.join(', '),
            adaptive_timers_enabled: settings.adaptive_timers_enabled !== false,
            eye_care_mode: settings.eye_care_mode === true,
            hydration_target: settings.hydration_target !== undefined ? settings.hydration_target : 8,
            hydration_unit: settings.hydration_unit || "cups",
            hydration_increment: settings.hydration_increment !== undefined ? settings.hydration_increment : 1
        };
        
        initSettingsDirtyTracking();
        checkSettingsDirty();
        
    } catch (e) {
        showToast("Error loading settings", true);
    }
}

// Save Settings to Backend
document.getElementById('settings-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const settings = {
        work_duration_minutes: parseInt(document.getElementById('work-limit-input').value),
        idle_timeout_seconds: parseInt(document.getElementById('idle-timeout-input').value),
        rest_duration_seconds: parseInt(document.getElementById('rest-duration-input').value),
        work_keywords: document.getElementById('work-keywords-input').value.split(',').map(k => k.trim()),
        recharge_keywords: document.getElementById('recharge-keywords-input').value.split(',').map(k => k.trim()),
        adaptive_timers_enabled: document.getElementById('autopilot-input').checked,
        eye_care_mode: document.getElementById('eyecare-input').checked,
        hydration_target: parseInt(document.getElementById('hydration-target-input').value),
        hydration_unit: document.getElementById('hydration-unit-input').value,
        hydration_increment: parseFloat(document.getElementById('hydration-increment-input').value)
    };
    
    try {
        const res = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });
        if (res.ok) {
            showToast("Settings Applied Successfully!");
            // Dynamic eye care toggle
            const eyeCareEnabled = document.getElementById('eyecare-input').checked;
            if (eyeCareEnabled) {
                document.body.classList.add('eye-care-active');
            } else {
                document.body.classList.remove('eye-care-active');
            }
            
            // Re-cache initial settings
            initialSettings = {
                work_duration_minutes: settings.work_duration_minutes,
                idle_timeout_seconds: settings.idle_timeout_seconds,
                rest_duration_seconds: settings.rest_duration_seconds,
                work_keywords: document.getElementById('work-keywords-input').value,
                recharge_keywords: document.getElementById('recharge-keywords-input').value,
                adaptive_timers_enabled: settings.adaptive_timers_enabled,
                eye_care_mode: settings.eye_care_mode,
                hydration_target: settings.hydration_target,
                hydration_unit: settings.hydration_unit,
                hydration_increment: settings.hydration_increment
            };
            checkSettingsDirty();
            
            // Refresh hydration UI immediately after setting changes
            fetch('/api/hydration')
                .then(r => r.json())
                .then(data => updateHydrationUI(data))
                .catch(e => console.error("Error reloading hydration after settings save:", e));
        } else {
            showToast("Failed to save settings", true);
        }
    } catch (e) {
        showToast("Network error saving settings", true);
    }
});

// Add quick reflection tag helper
function addTag(tagText) {
    const summaryInput = document.getElementById('reflection-summary');
    const currentValue = summaryInput.value.trim();
    if (currentValue === '') {
        summaryInput.value = `[${tagText}] `;
    } else {
        if (!currentValue.includes(`[${tagText}]`)) {
            summaryInput.value = `[${tagText}] ${currentValue}`;
        }
    }
    summaryInput.focus();
}

let lastSubmitClick = null;
const submitBtnEl = document.querySelector('#quick-reflection-form .submit-btn');
if (submitBtnEl) {
    submitBtnEl.addEventListener('click', (e) => {
        lastSubmitClick = e;
    });
}

// Quick Reflection Submit
document.getElementById('quick-reflection-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const summaryInput = document.getElementById('reflection-summary');
    const payload = {
        energy_level: selectedEnergy,
        friction_level: selectedFriction,
        summary: summaryInput.value
    };
    
    try {
        const res = await fetch('/api/reflections', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (res.ok) {
            showToast("Reflection logged inside private vault.");
            triggerParticleBurst(lastSubmitClick);
            summaryInput.value = '';
            pollStatus(); // Immediately update battery meter
        } else {
            showToast("Failed to save reflection", true);
        }
    } catch (err) {
        showToast("Network error submitting reflection", true);
    }
    lastSubmitClick = null;
});

// Dynamic Reflection Submission Particle Burst
function triggerParticleBurst(e, customColor) {
    const container = document.body;
    let x, y;
    
    if (e && e.clientX && e.clientY) {
        x = e.clientX + window.scrollX;
        y = e.clientY + window.scrollY;
    } else {
        const submitBtn = document.querySelector('#quick-reflection-form .submit-btn');
        if (submitBtn) {
            const rect = submitBtn.getBoundingClientRect();
            x = rect.left + rect.width / 2 + window.scrollX;
            y = rect.top + rect.height / 2 + window.scrollY;
        } else {
            x = window.innerWidth / 2;
            y = window.innerHeight / 2;
        }
    }
    
    const particleCount = 24;
    for (let i = 0; i < particleCount; i++) {
        const particle = document.createElement('div');
        particle.className = 'burst-particle';
        
        const size = Math.random() * 8 + 4;
        particle.style.width = `${size}px`;
        particle.style.height = `${size}px`;
        
        let color = customColor || '#a78bfa';
        if (!customColor) {
            if (bodyEl.classList.contains('mode-recharge')) color = '#2dd4a8';
            else if (bodyEl.classList.contains('mode-rest')) color = '#fbbf24';
        }
        
        particle.style.backgroundColor = color;
        particle.style.color = color;
        particle.style.left = `${x}px`;
        particle.style.top = `${y}px`;
        
        const angle = Math.random() * Math.PI * 2;
        const velocity = Math.random() * 8 + 4;
        let vx = Math.cos(angle) * velocity;
        let vy = Math.sin(angle) * velocity - 2;
        
        container.appendChild(particle);
        
        let posX = x;
        let posY = y;
        let opacity = 1;
        
        const updateParticle = () => {
            posX += vx;
            posY += vy;
            vy += 0.25; // gravity
            vx *= 0.97; // air resistance
            opacity -= 0.022; // fade
            
            particle.style.left = `${posX}px`;
            particle.style.top = `${posY}px`;
            particle.style.opacity = opacity;
            
            if (opacity > 0) {
                requestAnimationFrame(updateParticle);
            } else {
                particle.remove();
            }
        };
        
        requestAnimationFrame(updateParticle);
    }
}

// Load Analytics & Draw SVG Line Chart
async function loadAnalytics() {
    try {
        const res = await fetch('/api/analytics');
        const data = await res.json();
        hideSkeletons();
        
        // 1. Load Insights
        const insightsList = document.getElementById('insights-list');
        insightsList.innerHTML = '';
        
        if (data.insights && data.insights.length > 0) {
            // Sort insights by priority (danger > warning > info > success)
            const typeWeights = { danger: 4, warning: 3, info: 2, success: 1 };
            const sortedInsights = [...data.insights].sort((a, b) => {
                return (typeWeights[b.type] || 0) - (typeWeights[a.type] || 0);
            });
            
            // Limit to the top 1 insight to prevent cluttering
            const activeInsights = sortedInsights.slice(0, 1);
            
            activeInsights.forEach(insight => {
                const card = document.createElement('div');
                card.className = `insight-card-item type-${insight.type}`;
                card.innerHTML = `
                    <div class="insight-header">
                        <div class="insight-title-group">
                            <span class="insight-icon">${escapeHtml(insight.icon)}</span>
                            <span class="insight-title">${escapeHtml(insight.title)}</span>
                        </div>
                        <span class="insight-metric-badge">${escapeHtml(insight.metric)}</span>
                    </div>
                    <p class="insight-desc">${escapeHtml(insight.description)}</p>
                    <div class="insight-tip-box">
                        <strong>💡 Action Tip:</strong> ${escapeHtml(insight.actionable_tip)}
                    </div>
                `;
                insightsList.appendChild(card);
            });
        } else {
            // Fallback to legacy recommendations
            const recList = data.recommendations || [];
            if (recList.length === 0) {
                insightsList.innerHTML = `<div class="insight-card-item type-success"><p class="insight-desc">Your routine looks balanced! Keep tracking your focus windows to refine your patterns.</p></div>`;
            } else {
                recList.forEach(rec => {
                    const div = document.createElement('div');
                    div.className = 'insight-card-item type-info';
                    div.innerHTML = `<p class="insight-desc">${escapeHtml(rec)}</p>`;
                    insightsList.appendChild(div);
                });
            }
        }
        
        // 2. Load Reflection Logs table
        const tableBody = document.getElementById('reflections-log-body');
        tableBody.innerHTML = '';
        
        if (data.reflections.length === 0) {
            tableBody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-muted);">No reflection entries found yet. Submit some from the dashboard!</td></tr>`;
        } else {
            // Sort newest first
            const sortedReflections = [...data.reflections].reverse();
            sortedReflections.forEach(ref => {
                const tr = document.createElement('tr');
                
                const summaryLower = (ref.summary || '').toLowerCase();
                if (summaryLower.includes('coding win') || summaryLower.includes('deep flow') || summaryLower.includes('rest break')) {
                    tr.classList.add('win-row');
                } else if (summaryLower.includes('bug roadblock') || summaryLower.includes('stuck in loop') || summaryLower.includes('fatigue alert')) {
                    tr.classList.add('roadblock-row');
                } else if (summaryLower.includes('gratitude') || summaryLower.includes('victory')) {
                    tr.classList.add('gratitude-row');
                }
                
                const dt = new Date(ref.timestamp);
                const dateStr = dt.toLocaleDateString() + ' ' + dt.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                
                let energyBadge = `<span class="rating-badge badge-green">${ref.energy_level} / 5</span>`;
                if (ref.energy_level <= 2) energyBadge = `<span class="rating-badge badge-red">${ref.energy_level} / 5</span>`;
                
                let frictionBadge = `<span class="rating-badge badge-purple">${ref.friction_level} / 5</span>`;
                if (ref.friction_level >= 4) frictionBadge = `<span class="rating-badge badge-red">${ref.friction_level} / 5</span>`;
                
                tr.innerHTML = `
                    <td>${escapeHtml(dateStr)}</td>
                    <td>${energyBadge}</td>
                    <td>${frictionBadge}</td>
                    <td><code>${escapeHtml(ref.summary)}</code></td>
                `;
                tableBody.appendChild(tr);
            });
        }
        
        // 2.5. Render Today's Focus Timeline Widget
        const todaySessions = data.today_sessions || [];
        const timelineProgress = document.getElementById('timeline-progress-bar');
        const timelineEvents = document.getElementById('timeline-events-list');
        const timelinePill = document.getElementById('timeline-summary-pill');
        
        if (timelineProgress && timelineEvents && timelinePill) {
            timelineProgress.innerHTML = '';
            timelineEvents.innerHTML = '';
            
            const totalDuration = todaySessions.reduce((sum, s) => sum + s.duration, 0);
            const totalTrackedMin = Math.round(totalDuration / 60);
            const trackedH = Math.floor(totalTrackedMin / 60);
            const trackedM = totalTrackedMin % 60;
            timelinePill.textContent = `${trackedH}h ${trackedM}m total track`;
            
            if (todaySessions.length === 0) {
                timelineProgress.innerHTML = `<div class="timeline-segment neutral-seg" style="width: 100%;" data-tooltip="No sessions tracked yet today."></div>`;
                timelineEvents.innerHTML = `<div style="text-align: center; color: var(--text-muted); font-size: 0.85rem; padding: 1.25rem 0;">No focus sessions or breaks logged yet today.</div>`;
            } else {
                // Populate progress bar segments
                todaySessions.forEach(session => {
                    const pct = totalDuration > 0 ? (session.duration / totalDuration) * 100 : 0;
                    if (pct <= 0) return;
                    
                    const seg = document.createElement('div');
                    let modeClass = 'neutral-seg';
                    if (session.mode === 'work') modeClass = 'work-seg';
                    else if (session.mode === 'recharge') modeClass = 'recharge-seg';
                    else if (session.mode === 'rest') modeClass = 'rest-seg';
                    
                    seg.className = `timeline-segment ${modeClass}`;
                    seg.style.width = `${pct}%`;
                    
                    const startDt = new Date(session.start);
                    const endDt = new Date(session.end);
                    const startTimeStr = startDt.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                    const endTimeStr = endDt.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                    const durationMin = Math.round(session.duration / 60);
                    
                    const tooltipText = `${session.mode.toUpperCase()}: ${startTimeStr} - ${endTimeStr} (${durationMin} min)`;
                    seg.setAttribute('data-tooltip', tooltipText);
                    timelineProgress.appendChild(seg);
                });
                
                // Populate event list (sorted newest first)
                const sortedTodaySessions = [...todaySessions].sort((a, b) => new Date(b.start) - new Date(a.start));
                sortedTodaySessions.forEach(session => {
                    const item = document.createElement('div');
                    item.className = 'timeline-event-item';
                    
                    const startDt = new Date(session.start);
                    const timeStr = startDt.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                    
                    let badgeClass = 'neutral-badge';
                    if (session.mode === 'work') badgeClass = 'work-badge';
                    else if (session.mode === 'recharge') badgeClass = 'recharge-badge';
                    else if (session.mode === 'rest') badgeClass = 'rest-badge';
                    
                    const durationMin = Math.round(session.duration / 60);
                    let summaryText = `${durationMin} mins of focus/rest`;
                    if (session.brain_dump) {
                        summaryText += ` — Save-State: "${escapeHtml(session.brain_dump)}"`;
                    }
                    if (session.bypassed) {
                        summaryText += ` (Eye Rest Bypassed)`;
                    }
                    
                    item.innerHTML = `
                        <span class="event-time">${escapeHtml(timeStr)}</span>
                        <span class="event-badge ${escapeHtml(badgeClass)}">${escapeHtml(session.mode)}</span>
                        <span class="event-summary">${summaryText}</span>
                    `;
                    timelineEvents.appendChild(item);
                });
            }
        }
        
        // 3. Render Custom SVG Line Chart
        lastWeekdaySummary = data.weekday_summary;
        lastReflections = data.reflections;
        renderEnergyMap(lastWeekdaySummary, lastReflections);
        
        // 4. Render App Usage Statistics
        appStatsData = data.app_usage || [];
        renderAppStats();
        
    } catch (e) {
        showToast("Error loading analytics data", true);
        console.error(e);
    }
}

// Filter application statistics
function setAppStatsFilter(filter) {
    appStatsFilter = filter;
    document.querySelectorAll('.app-stats-filters .filter-pill').forEach(btn => btn.classList.remove('active'));
    
    if (filter === 'today') {
        const btnToday = document.getElementById('app-filter-today');
        if (btnToday) btnToday.classList.add('active');
    } else {
        const btnWeekly = document.getElementById('app-filter-weekly');
        if (btnWeekly) btnWeekly.classList.add('active');
    }
    
    renderAppStats();
}

// Render app stats list
function renderAppStats() {
    const listEl = document.getElementById('app-stats-list');
    if (!listEl) return;
    listEl.innerHTML = '';
    
    // Timezone-safe local date string helper
    const getLocalDateString = (d = new Date()) => {
        const year = d.getFullYear();
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    };

    // Filter data based on selection
    let filteredData = [];
    const todayStr = getLocalDateString();
    
    if (appStatsFilter === 'today') {
        // Find entries matching today's date and aggregate them safely
        const cumulative = {};
        appStatsData.filter(entry => entry.date === todayStr).forEach(entry => {
            const key = entry.process;
            if (!cumulative[key]) {
                cumulative[key] = {
                    process: entry.process,
                    title: entry.title,
                    titles: {},
                    duration: 0,
                    category: entry.category,
                    work_duration: 0,
                    recharge_duration: 0,
                    neutral_duration: 0,
                    title_categories: {}
                };
            }
            cumulative[key].duration += entry.duration;
            if (entry.title && entry.title !== "None") {
                cumulative[key].title = entry.title;
            }
            if (entry.titles) {
                for (const [title, dur] of Object.entries(entry.titles)) {
                    cumulative[key].titles[title] = (cumulative[key].titles[title] || 0) + dur;
                }
            }
            if (entry.title_categories) {
                for (const [title, cat] of Object.entries(entry.title_categories)) {
                    cumulative[key].title_categories[title] = cat;
                }
            }
            
            // Backward compatibility fallback for legacy database entries
            let workD = entry.work_duration || 0;
            let rechargeD = entry.recharge_duration || 0;
            let neutralD = entry.neutral_duration || 0;
            if (workD === 0 && rechargeD === 0 && neutralD === 0) {
                if (entry.category === 'work') workD = entry.duration;
                else if (entry.category === 'recharge') rechargeD = entry.duration;
                else neutralD = entry.duration;
            }
            cumulative[key].work_duration += workD;
            cumulative[key].recharge_duration += rechargeD;
            cumulative[key].neutral_duration += neutralD;
        });
        filteredData = Object.values(cumulative);
    } else {
        // Last 7 days including today
        const cutoffDate = new Date();
        cutoffDate.setDate(cutoffDate.getDate() - 7);
        const cutoffStr = getLocalDateString(cutoffDate);
        
        // Group by process and category to show cumulative totals
        const cumulative = {};
        appStatsData.forEach(entry => {
            if (entry.date >= cutoffStr) {
                const key = entry.process;
                if (!cumulative[key]) {
                    cumulative[key] = {
                        process: entry.process,
                        title: entry.title,
                        titles: {},
                        duration: 0,
                        category: entry.category,
                        work_duration: 0,
                        recharge_duration: 0,
                        neutral_duration: 0,
                        title_categories: {}
                    };
                }
                cumulative[key].duration += entry.duration;
                // Prefer non-empty title or the latest title
                if (entry.title && entry.title !== "None") {
                    cumulative[key].title = entry.title;
                }
                // Merge sub-titles durations
                if (entry.titles) {
                    for (const [title, dur] of Object.entries(entry.titles)) {
                        cumulative[key].titles[title] = (cumulative[key].titles[title] || 0) + dur;
                    }
                }
                if (entry.title_categories) {
                    for (const [title, cat] of Object.entries(entry.title_categories)) {
                        cumulative[key].title_categories[title] = cat;
                    }
                }
                
                // Backward compatibility fallback for legacy database entries
                let workD = entry.work_duration || 0;
                let rechargeD = entry.recharge_duration || 0;
                let neutralD = entry.neutral_duration || 0;
                if (workD === 0 && rechargeD === 0 && neutralD === 0) {
                    if (entry.category === 'work') workD = entry.duration;
                    else if (entry.category === 'recharge') rechargeD = entry.duration;
                    else neutralD = entry.duration;
                }
                cumulative[key].work_duration += workD;
                cumulative[key].recharge_duration += rechargeD;
                cumulative[key].neutral_duration += neutralD;
            }
        });
        filteredData = Object.values(cumulative);
    }
    
    // Re-determine predominant category for each accumulated item
    filteredData.forEach(item => {
        if (item.work_duration >= item.recharge_duration && item.work_duration >= item.neutral_duration) {
            item.category = 'work';
        } else if (item.recharge_duration >= item.work_duration && item.recharge_duration >= item.neutral_duration) {
            item.category = 'recharge';
        } else {
            item.category = 'neutral';
        }
    });

    // Sort by duration descending
    filteredData.sort((a, b) => b.duration - a.duration);
    
    // Calculate total duration for ratio metrics (accurately from sub-item classifications)
    let workDuration = 0;
    let rechargeDuration = 0;
    let neutralDuration = 0;
    
    filteredData.forEach(item => {
        workDuration += item.work_duration;
        rechargeDuration += item.recharge_duration;
        neutralDuration += item.neutral_duration;
    });
    
    const totalDuration = workDuration + rechargeDuration + neutralDuration;
    
    // Render Category Ratio Bar
    const ratioContainer = document.getElementById('app-ratio-bar-container');
    if (totalDuration > 0 && ratioContainer) {
        ratioContainer.style.display = 'block';
        const workPct = Math.round((workDuration / totalDuration) * 100);
        const rechargePct = Math.round((rechargeDuration / totalDuration) * 100);
        const neutralPct = Math.round((neutralDuration / totalDuration) * 100);
        
        document.getElementById('ratio-seg-work').style.width = `${workPct}%`;
        document.getElementById('ratio-seg-recharge').style.width = `${rechargePct}%`;
        document.getElementById('ratio-seg-neutral').style.width = `${neutralPct}%`;
        
        document.getElementById('ratio-pct-work').textContent = `${workPct}%`;
        document.getElementById('ratio-pct-recharge').textContent = `${rechargePct}%`;
        document.getElementById('ratio-pct-neutral').textContent = `${neutralPct}%`;
    } else if (ratioContainer) {
        ratioContainer.style.display = 'none';
    }
    
    if (filteredData.length === 0) {
        listEl.innerHTML = `<div style="text-align: center; color: var(--text-muted); font-size: 0.85rem; padding: 2rem 0;">No application activity tracked for this period.</div>`;
        return;
    }
    
    // Emojis mapping
    const getAppEmoji = (proc) => {
        const p = proc.toLowerCase();
        if (p.includes('code') || p.includes('visualstudio') || p.includes('pycharm') || p.includes('sublime')) return '💻';
        if (p.includes('chrome') || p.includes('edge') || p.includes('firefox') || p.includes('brave') || p.includes('opera') || p.includes('iexplore') || p.includes('browser')) return '🌐';
        if (p.includes('steam') || p.includes('game') || p.includes('epic') || p.includes('xbox') || p.includes('gog')) return '🎮';
        if (p.includes('spotify') || p.includes('music') || p.includes('vlc') || p.includes('netflix') || p.includes('youtube')) return '🎵';
        if (p.includes('discord') || p.includes('teams') || p.includes('slack') || p.includes('skype') || p.includes('zoom')) return '💬';
        if (p.includes('cmd') || p.includes('powershell') || p.includes('terminal') || p.includes('bash')) return '⚡';
        if (p.includes('explorer')) return '📁';
        if (p.includes('word') || p.includes('powerpnt') || p.includes('excel') || p.includes('acrobat') || p.includes('pdf')) return '📄';
        return '📱';
    };
    
    // Format duration nicely
    const formatAppDuration = (sec) => {
        if (sec < 60) return `${sec}s`;
        const mins = Math.floor(sec / 60);
        if (mins < 60) return `${mins}m`;
        const hrs = Math.floor(mins / 60);
        const remMins = mins % 60;
        return `${hrs}h ${remMins}m`;
    };
    
    filteredData.forEach((item, index) => {
        const pct = totalDuration > 0 ? (item.duration / totalDuration) * 100 : 0;
        const emoji = getAppEmoji(item.process);
        const durationText = formatAppDuration(item.duration);
        
        // Build sub-items list html
        let subItemsHtml = '';
        if (item.titles && Object.keys(item.titles).length > 0) {
            // Sort sub-titles by duration descending
            const sortedSubTitles = Object.entries(item.titles).sort((a, b) => b[1] - a[1]);
            sortedSubTitles.forEach(([title, dur]) => {
                const cat = (item.title_categories && item.title_categories[title]) || 'neutral';
                subItemsHtml += `
                    <div class="app-sub-item">
                        <span class="app-sub-name" title="${escapeHtml(title)}">
                            <span class="legend-dot ${cat}" style="display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:6px;"></span>
                            ${escapeHtml(title)}
                        </span>
                        <span class="app-sub-duration">${formatAppDuration(dur)}</span>
                    </div>
                `;
            });
        } else {
            // Fallback to the main title
            subItemsHtml = `
                <div class="app-sub-item">
                    <span class="app-sub-name" title="${escapeHtml(item.title)}">
                        <span class="legend-dot neutral" style="display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:6px;"></span>
                        ${escapeHtml(item.title)}
                    </span>
                    <span class="app-sub-duration">${durationText}</span>
                </div>
            `;
        }
        
        const appItem = document.createElement('div');
        appItem.className = 'app-item';
        appItem.id = `app-item-${index}`;
        appItem.innerHTML = `
            <div class="app-item-top" onclick="toggleAppDetails(${index})">
                <div class="app-item-details">
                    <span class="app-item-icon">${emoji}</span>
                    <div class="app-item-meta">
                        <span class="app-name">${escapeHtml(item.process)}<span class="app-expand-chevron">▼</span></span>
                        <span class="app-title-sub" title="${escapeHtml(item.title)}">${escapeHtml(item.title)}</span>
                    </div>
                </div>
                <span class="app-duration-badge">${durationText}</span>
            </div>
            <div class="app-progress-container" onclick="toggleAppDetails(${index})" style="cursor: pointer;">
                <div class="app-progress-bar ${item.category}" style="width: 0%;"></div>
            </div>
            <div class="app-sub-list">
                ${subItemsHtml}
            </div>
        `;
        
        listEl.appendChild(appItem);
        
        // Trigger reflow for width transition animation
        setTimeout(() => {
            const bar = appItem.querySelector('.app-progress-bar');
            if (bar) bar.style.width = `${pct}%`;
        }, 50);
    });
}

// Toggle expansion of specific window titles list
function toggleAppDetails(index) {
    const el = document.getElementById(`app-item-${index}`);
    if (el) {
        el.classList.toggle('expanded');
    }
}

// Render dynamic custom SVG chart
// Render dynamic custom SVG chart with bezier curves and interactive tooltips
function renderEnergyMap(weekdayData, reflections) {
    const container = document.getElementById('chart-container');
    if (!container) return;
    container.innerHTML = '';
    
    const width = container.clientWidth || 700;
    const height = container.clientHeight || 300;
    
    const svgNS = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(svgNS, "svg");
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.setAttribute("class", "svg-chart");
    svg.style.width = "100%";
    svg.style.height = "100%";
    
    // Margins
    const mLeft = 50;
    const mRight = 30;
    const mTop = 30;
    const mBottom = 40;
    
    const chartW = width - mLeft - mRight;
    const chartH = height - mTop - mBottom;
    
    // Draw Y-Axis Gridlines (Values 1 to 5)
    for (let val = 1; val <= 5; val++) {
        const y = mTop + chartH - ((val - 1) / 4) * chartH;
        
        // Gridline
        const line = document.createElementNS(svgNS, "line");
        line.setAttribute("x1", mLeft);
        line.setAttribute("y1", y);
        line.setAttribute("x2", width - mRight);
        line.setAttribute("y2", y);
        line.setAttribute("class", "chart-grid-line");
        svg.appendChild(line);
        
        // Value Text
        const text = document.createElementNS(svgNS, "text");
        text.setAttribute("x", mLeft - 15);
        text.setAttribute("y", y + 4);
        text.setAttribute("class", "chart-axis-text");
        text.setAttribute("text-anchor", "end");
        
        let axisLabel = val.toString();
        if (val === 5) axisLabel = "5 (Max)";
        if (val === 1) axisLabel = "1 (Min)";
        text.textContent = axisLabel;
        svg.appendChild(text);
    }
    
    // Compile points
    const energyPoints = [];
    const frictionPoints = [];
    
    weekdayData.forEach((day, index) => {
        const x = mLeft + (index / 6) * chartW;
        
        // Draw X-axis label
        const text = document.createElementNS(svgNS, "text");
        text.setAttribute("x", x);
        text.setAttribute("y", height - mBottom + 25);
        text.setAttribute("class", "chart-axis-text");
        text.setAttribute("text-anchor", "middle");
        text.textContent = day.day;
        svg.appendChild(text);
        
        // Calculate Y for Energy (1-5) -> map to chart height
        if (day.count > 0) {
            const yEnergy = mTop + chartH - ((day.avg_energy - 1) / 4) * chartH;
            energyPoints.push({x, y: yEnergy, val: day.avg_energy, day: day.day, index});
            
            const yFriction = mTop + chartH - ((day.avg_friction - 1) / 4) * chartH;
            frictionPoints.push({x, y: yFriction, val: day.avg_friction, day: day.day, index});
        }
    });

    // Draw Gradients Defs
    const defs = document.createElementNS(svgNS, "defs");
    defs.innerHTML = `
        <linearGradient id="grad-energy" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="var(--recharge-color)" stop-opacity="0.18"/>
            <stop offset="100%" stop-color="var(--recharge-color)" stop-opacity="0.0"/>
        </linearGradient>
        <linearGradient id="grad-friction" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="var(--work-color)" stop-opacity="0.18"/>
            <stop offset="100%" stop-color="var(--work-color)" stop-opacity="0.0"/>
        </linearGradient>
    `;
    svg.appendChild(defs);
    
    const bottomY = mTop + chartH;

    // Bezier curve helpers
    function getBezierPath(points) {
        if (points.length === 0) return "";
        if (points.length === 1) return `M ${points[0].x} ${points[0].y}`;
        
        let path = `M ${points[0].x} ${points[0].y}`;
        for (let i = 0; i < points.length - 1; i++) {
            const p0 = points[i];
            const p1 = points[i+1];
            const cpX1 = p0.x + (p1.x - p0.x) / 3;
            const cpY1 = p0.y;
            const cpX2 = p0.x + 2 * (p1.x - p0.x) / 3;
            const cpY2 = p1.y;
            path += ` C ${cpX1} ${cpY1}, ${cpX2} ${cpY2}, ${p1.x} ${p1.y}`;
        }
        return path;
    }

    function getBezierAreaPath(points, bottomY) {
        if (points.length === 0) return "";
        if (points.length === 1) return `M ${points[0].x} ${bottomY} L ${points[0].x} ${points[0].y} L ${points[0].x} ${bottomY} Z`;
        
        let path = `M ${points[0].x} ${bottomY}`;
        path += ` L ${points[0].x} ${points[0].y}`;
        for (let i = 0; i < points.length - 1; i++) {
            const p0 = points[i];
            const p1 = points[i+1];
            const cpX1 = p0.x + (p1.x - p0.x) / 3;
            const cpY1 = p0.y;
            const cpX2 = p0.x + 2 * (p1.x - p0.x) / 3;
            const cpY2 = p1.y;
            path += ` C ${cpX1} ${cpY1}, ${cpX2} ${cpY2}, ${p1.x} ${p1.y}`;
        }
        path += ` L ${points[points.length - 1].x} ${bottomY} Z`;
        return path;
    }

    // Draw Energy Area (Bezier)
    if (energyPoints.length > 0) {
        const area = document.createElementNS(svgNS, "path");
        area.setAttribute("d", getBezierAreaPath(energyPoints, bottomY));
        area.setAttribute("fill", "url(#grad-energy)");
        svg.appendChild(area);
    }

    // Draw Friction Area (Bezier)
    if (frictionPoints.length > 0) {
        const area = document.createElementNS(svgNS, "path");
        area.setAttribute("d", getBezierAreaPath(frictionPoints, bottomY));
        area.setAttribute("fill", "url(#grad-friction)");
        svg.appendChild(area);
    }
    
    // Draw Energy Line (Bezier)
    if (energyPoints.length > 0) {
        const path = document.createElementNS(svgNS, "path");
        path.setAttribute("d", getBezierPath(energyPoints));
        path.setAttribute("class", "chart-line-energy");
        svg.appendChild(path);
    }
    
    // Draw Friction Line (Bezier)
    if (frictionPoints.length > 0) {
        const path = document.createElementNS(svgNS, "path");
        path.setAttribute("d", getBezierPath(frictionPoints));
        path.setAttribute("class", "chart-line-friction");
        svg.appendChild(path);
    }

    // Draw Guidance crosshair line
    const guideLine = document.createElementNS(svgNS, "line");
    guideLine.setAttribute("y1", mTop);
    guideLine.setAttribute("y2", bottomY);
    guideLine.setAttribute("class", "chart-guide-line");
    guideLine.style.opacity = "0";
    guideLine.style.pointerEvents = "none";
    svg.appendChild(guideLine);

    // Setup interactive tooltip element
    let tooltipEl = document.getElementById('chart-tooltip-el');
    if (!tooltipEl) {
        tooltipEl = document.createElement('div');
        tooltipEl.id = 'chart-tooltip-el';
        tooltipEl.className = 'chart-tooltip';
        document.body.appendChild(tooltipEl);
    }

    // Draw Energy Dots with index identifiers
    if (energyPoints.length > 0) {
        energyPoints.forEach(p => {
            const circle = document.createElementNS(svgNS, "circle");
            circle.setAttribute("cx", p.x);
            circle.setAttribute("cy", p.y);
            circle.setAttribute("r", 5);
            circle.setAttribute("class", "chart-dot-energy");
            circle.setAttribute("data-index", p.index);
            svg.appendChild(circle);
        });
    }
    
    // Draw Friction Dots with index identifiers
    if (frictionPoints.length > 0) {
        frictionPoints.forEach(p => {
            const circle = document.createElementNS(svgNS, "circle");
            circle.setAttribute("cx", p.x);
            circle.setAttribute("cy", p.y);
            circle.setAttribute("r", 5);
            circle.setAttribute("class", "chart-dot-friction");
            circle.setAttribute("data-index", p.index);
            svg.appendChild(circle);
        });
    }

    // Draw Hover Tracking Overlay Rect
    const overlay = document.createElementNS(svgNS, "rect");
    overlay.setAttribute("x", mLeft);
    overlay.setAttribute("y", mTop);
    overlay.setAttribute("width", chartW);
    overlay.setAttribute("height", chartH);
    overlay.setAttribute("fill", "transparent");
    overlay.style.cursor = "crosshair";
    svg.appendChild(overlay);

    // Crosshair hover tracking event listeners (optimized with cached dimensions and requestAnimationFrame)
    let svgRect = null;
    let chartTicking = false;
    let chartMouseX = 0;
    let chartPageX = 0;
    let chartPageY = 0;

    overlay.addEventListener('mouseenter', () => {
        svgRect = svg.getBoundingClientRect();
    });

    overlay.addEventListener('mousemove', (e) => {
        if (!svgRect) svgRect = svg.getBoundingClientRect();
        chartMouseX = e.clientX;
        chartPageX = e.pageX;
        chartPageY = e.pageY;
        
        if (!chartTicking) {
            requestAnimationFrame(updateChartTooltip);
            chartTicking = true;
        }
    });

    function updateChartTooltip() {
        if (!svgRect) {
            chartTicking = false;
            return;
        }
        const localX = (chartMouseX - svgRect.left) * (width / svgRect.width);
        
        // Find nearest weekday column
        const colWidth = chartW / 6;
        let index = Math.round((localX - mLeft) / colWidth);
        index = Math.max(0, Math.min(6, index));
        
        const targetX = mLeft + index * colWidth;
        
        // Snap guidance line to current column
        guideLine.setAttribute("x1", targetX);
        guideLine.setAttribute("x2", targetX);
        guideLine.style.opacity = "1";
        
        // Dynamic hovered state for data dots
        svg.querySelectorAll('.chart-dot-energy, .chart-dot-friction').forEach(circle => {
            circle.setAttribute("r", 5);
            circle.classList.remove('hovered');
        });
        
        const energyCircle = svg.querySelector(`.chart-dot-energy[data-index="${index}"]`);
        const frictionCircle = svg.querySelector(`.chart-dot-friction[data-index="${index}"]`);
        
        if (energyCircle) {
            energyCircle.setAttribute("r", 8);
            energyCircle.classList.add('hovered');
        }
        if (frictionCircle) {
            frictionCircle.setAttribute("r", 8);
            frictionCircle.classList.add('hovered');
        }
        
        // Build combined tooltip content
        const dayData = weekdayData[index] || {};
        const dayName = dayData.day;
        const avgEnergy = dayData.avg_energy || 0;
        const avgFriction = dayData.avg_friction || 0;
        
        const dayRefs = reflections ? reflections.filter(ref => {
            try {
                const dt = new Date(ref.timestamp);
                const days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
                return days[dt.getDay()] === dayName;
            } catch(err) {
                return false;
            }
        }) : [];
        
        let summariesText = dayRefs.length > 0 
            ? dayRefs.map(r => `• ${escapeHtml(r.summary)}`).join('<br>') 
            : 'No reflections logged today.';
            
        const getEnergyLabel = (val) => {
            if (val >= 4.5) return "Peak";
            if (val >= 3.5) return "Good";
            if (val >= 2.5) return "Neutral";
            if (val >= 1.5) return "Low";
            return "Drained";
        };
        const getFrictionLabel = (val) => {
            if (val >= 4.5) return "Blocked";
            if (val >= 3.5) return "Tough";
            if (val >= 2.5) return "Mixed";
            if (val >= 1.5) return "Easy";
            return "Smooth";
        };

        tooltipEl.innerHTML = `
            <h4>${dayName} Analysis</h4>
            <div class="chart-tooltip-metric">
                <span>⚡ Avg Energy: <strong style="color: var(--recharge-color);">${avgEnergy.toFixed(1)}/5 (${getEnergyLabel(avgEnergy)})</strong></span>
                <span>🧱 Avg Friction: <strong style="color: var(--work-color);">${avgFriction.toFixed(1)}/5 (${getFrictionLabel(avgFriction)})</strong></span>
            </div>
            <div class="chart-tooltip-summary">
                ${summariesText}
            </div>
        `;
        
        tooltipEl.style.opacity = '1';
        const tooltipRect = tooltipEl.getBoundingClientRect();
        const maxLeft = window.innerWidth - (tooltipRect.width || 200) - 20;
        const maxTop = window.innerHeight - (tooltipRect.height || 100) - 20;
        tooltipEl.style.top = `${Math.min(chartPageY - 20, maxTop + window.scrollY)}px`;
        tooltipEl.style.left = `${Math.min(chartPageX + 15, maxLeft + window.scrollX)}px`;
        
        chartTicking = false;
    }

    overlay.addEventListener('mouseleave', () => {
        svgRect = null;
        guideLine.style.opacity = "0";
        tooltipEl.style.opacity = "0";
        svg.querySelectorAll('.chart-dot-energy, .chart-dot-friction').forEach(circle => {
            circle.setAttribute("r", 5);
            circle.classList.remove('hovered');
        });
    });

    // Draw Legend below chart
    const legend = document.createElement("div");
    legend.className = "chart-legend";
    legend.innerHTML = `
        <div class="legend-item">
            <span class="legend-color energy-legend-color"></span>
            <span>Mental Energy Battery (Higher is Better)</span>
        </div>
        <div class="legend-item">
            <span class="legend-color friction-legend-color"></span>
            <span>Task Friction Level (Lower is Better)</span>
        </div>
    `;
    
    container.appendChild(svg);
    container.appendChild(legend);
}


// Initial status load & continuous poll
pollStatus();
statusInterval = setInterval(pollStatus, 1000);

// Helper to extract a high-quality keyword from active window titles or processes, discarding browser names
function extractCleanKeyword(title, process) {
    if (!title || title === "None" || !process || process === "None") return "";
    
    const browserProcesses = ["chrome.exe", "msedge.exe", "firefox.exe", "opera.exe", "brave.exe", "iexplore.exe"];
    const isBrowser = browserProcesses.includes(process.toLowerCase());
    
    if (isBrowser) {
        let rawKeyword = title.trim();
        // Split by common title separators (dash, pipe, slash, bullet with spaces)
        let separators = rawKeyword.split(/\s+[-–—]\s+|\s*\|\s*|\s+[•·/]\s+|\s+\/\/\s+/);
        if (separators.length > 1) {
            // Discard the last element if it matches a browser name
            const lastPart = separators[separators.length - 1].toLowerCase();
            if (lastPart.includes("chrome") || lastPart.includes("firefox") || lastPart.includes("edge") || lastPart.includes("opera") || lastPart.includes("browser") || lastPart.includes("explorer")) {
                separators.pop();
            }
            // Use the remaining parts (take the first part)
            return separators[0].trim().toLowerCase();
        }
        return rawKeyword.toLowerCase();
    } else {
        // For non-browser apps, return the process name (e.g. code.exe)
        return process.toLowerCase();
    }
}

// Quick Add Keywords helper
async function addCurrentAppToKeywords(type) {
    if (!lastExternalWindow || lastExternalWindow === 'None' || !lastExternalProcess || lastExternalProcess === 'None') return;
    
    const extracted = extractCleanKeyword(lastExternalWindow, lastExternalProcess);
    if (!extracted) return;
    
    try {
        const getRes = await fetch('/api/settings');
        if (!getRes.ok) throw new Error("Failed to fetch settings");
        const settings = await getRes.json();
        
        const arrayKey = type === 'work' ? 'work_keywords' : 'recharge_keywords';
        const targetList = settings[arrayKey] || [];
        
        if (targetList.includes(extracted)) {
            showToast(`"${extracted}" is already in ${type} keywords!`, true);
            return;
        }
        
        targetList.push(extracted);
        settings[arrayKey] = targetList;
        
        const saveRes = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });
        
        if (saveRes.ok) {
            showToast(`Added "${extracted}" to ${type} keywords!`);
            loadSettings();
            pollStatus();
        } else {
            showToast("Failed to update keywords", true);
        }
    } catch (e) {
        console.error(e);
        showToast("Error updating settings", true);
    }
}

// Close application helper
async function quitApplication() {
    if (confirm("Ready to wrap up? Your workspace will be saved and tidied automatically.")) {
        try {
            showToast("Saving your work and closing...");
            await fetch('/api/shutdown', { method: 'POST' });
            document.body.innerHTML = `
                <div style="height: 100vh; display: flex; flex-direction: column; justify-content: center; align-items: center; background: #121218; color: #e8e8ed; font-family: 'Outfit', sans-serif; text-align: center; padding: 2rem;">
                    <div style="font-size: 4rem; margin-bottom: 1.5rem;">🧠</div>
                    <h1 style="font-size: 2rem; margin-bottom: 0.5rem; font-weight: 700; color: #a78bfa;">See You Soon</h1>
                    <p style="color: #a1a1b5; max-width: 420px; line-height: 1.7; font-size: 1.05rem;">Your workspace has been saved and tidied up. Take care of yourself — you can close this tab now.</p>
                </div>
            `;
        } catch (e) {
            console.error(e);
            showToast("Failed to request shutdown", true);
        }
    }
}

// Automatically redraw analytics chart on window resize
let resizeTimeout;
window.addEventListener('resize', () => {
    updateNavIndicator();
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
        if (currentTab === 'analytics' && lastWeekdaySummary) {
            renderEnergyMap(lastWeekdaySummary, lastReflections);
        }
    }, 150); // Debounce redraws to optimize performance
});

// ==========================================
// Focus Sound Synthesizer (Web Audio API)
// ==========================================
let audioCtx = null;
let audioSource = null;
let rainNodes = [];
let gainNode = null;
let isPlayingAudio = false;
let ambientSchedulerInterval = null;
let whiteNoiseBuffer = null;
let pinkNoiseBuffer = null;
let brownNoiseBuffer = null;
let preMuteVolume = 0.5;

function toggleAmbientAudio() {
    const btn = document.getElementById('audio-toggle-btn');
    const waveform = document.getElementById('audio-waveform');
    if (!btn) return;
    
    if (isPlayingAudio) {
        stopAmbientAudio();
        btn.textContent = 'Play';
        btn.classList.remove('playing');
        if (waveform) waveform.classList.remove('active');
    } else {
        startAmbientAudio();
        btn.textContent = 'Pause';
        btn.classList.add('playing');
        if (waveform) waveform.classList.add('active');
    }
}

function createWhiteNoiseBuffer() {
    if (whiteNoiseBuffer) return whiteNoiseBuffer;
    const bufferSize = audioCtx.sampleRate * 2;
    const buffer = audioCtx.createBuffer(1, bufferSize, audioCtx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < bufferSize; i++) {
        data[i] = Math.random() * 2 - 1;
    }
    whiteNoiseBuffer = buffer;
    return buffer;
}

function createPinkNoiseBuffer() {
    if (pinkNoiseBuffer) return pinkNoiseBuffer;
    const bufferSize = audioCtx.sampleRate * 2;
    const buffer = audioCtx.createBuffer(1, bufferSize, audioCtx.sampleRate);
    const data = buffer.getChannelData(0);
    let b0 = 0, b1 = 0, b2 = 0, b3 = 0, b4 = 0, b5 = 0, b6 = 0;
    for (let i = 0; i < bufferSize; i++) {
        let white = Math.random() * 2 - 1;
        b0 = 0.99886 * b0 + white * 0.0555179;
        b1 = 0.99332 * b1 + white * 0.0750759;
        b2 = 0.96900 * b2 + white * 0.1538520;
        b3 = 0.86650 * b3 + white * 0.3104856;
        b4 = 0.55000 * b4 + white * 0.5329522;
        b5 = -0.7616 * b5 - white * 0.0168980;
        let pink = b0 + b1 + b2 + b3 + b4 + b5 + b6 + white * 0.5362;
        b6 = white * 0.115926;
        data[i] = pink * 0.11; // estimate to compensate gain
    }
    pinkNoiseBuffer = buffer;
    return buffer;
}

function createBrownNoiseBuffer() {
    if (brownNoiseBuffer) return brownNoiseBuffer;
    const bufferSize = audioCtx.sampleRate * 2;
    const buffer = audioCtx.createBuffer(1, bufferSize, audioCtx.sampleRate);
    const data = buffer.getChannelData(0);
    let lastOut = 0.0;
    for (let i = 0; i < bufferSize; i++) {
        let white = Math.random() * 2 - 1;
        data[i] = (lastOut + (0.02 * white)) / 1.02;
        lastOut = data[i];
        data[i] *= 3.5; // Compensate for loss of volume
    }
    brownNoiseBuffer = buffer;
    return buffer;
}

function playRaindrop() {
    if (!audioCtx || audioCtx.state === 'suspended' || !gainNode) return;
    const time = audioCtx.currentTime;
    
    const source = audioCtx.createBufferSource();
    source.buffer = createPinkNoiseBuffer();
    
    const filter = audioCtx.createBiquadFilter();
    filter.type = 'bandpass';
    filter.frequency.setValueAtTime(1000 + Math.random() * 800, time);
    filter.Q.setValueAtTime(6 + Math.random() * 4, time);
    
    const dropGain = audioCtx.createGain();
    const peakVolume = 0.008 + Math.random() * 0.012;
    dropGain.gain.setValueAtTime(0, time);
    dropGain.gain.linearRampToValueAtTime(peakVolume, time + 0.002);
    dropGain.gain.exponentialRampToValueAtTime(0.0001, time + 0.035);
    
    source.connect(filter);
    filter.connect(dropGain);
    dropGain.connect(gainNode);
    
    source.start(time);
    source.stop(time + 0.05);
    
    setTimeout(() => {
        try {
            source.disconnect();
            filter.disconnect();
            dropGain.disconnect();
        } catch(e) {}
    }, 100);
}

function playFireCrackle() {
    if (!audioCtx || audioCtx.state === 'suspended' || !gainNode) return;
    const time = audioCtx.currentTime;
    
    const source = audioCtx.createBufferSource();
    source.buffer = createWhiteNoiseBuffer();
    
    const filter = audioCtx.createBiquadFilter();
    filter.type = 'highpass';
    filter.frequency.setValueAtTime(1800 + Math.random() * 1800, time);
    
    const crackleGain = audioCtx.createGain();
    const peakVolume = 0.012 + Math.random() * 0.018;
    crackleGain.gain.setValueAtTime(0, time);
    crackleGain.gain.linearRampToValueAtTime(peakVolume, time + 0.001);
    crackleGain.gain.exponentialRampToValueAtTime(0.0001, time + 0.012);
    
    source.connect(filter);
    filter.connect(crackleGain);
    crackleGain.connect(gainNode);
    
    source.start(time);
    source.stop(time + 0.03);
    
    setTimeout(() => {
        try {
            source.disconnect();
            filter.disconnect();
            crackleGain.disconnect();
        } catch(e) {}
    }, 100);
}

function startAmbientScheduler(type) {
    if (ambientSchedulerInterval) clearInterval(ambientSchedulerInterval);
    ambientSchedulerInterval = setInterval(() => {
        if (!isPlayingAudio) return;
        
        if (type === 'rain') {
            playRaindrop();
        } else if (type === 'fire') {
            const rand = Math.random();
            if (rand < 0.25) {
                playFireCrackle();
                setTimeout(playFireCrackle, 50 + Math.random() * 50);
            } else if (rand < 0.65) {
                playFireCrackle();
            }
        }
    }, 140 + Math.random() * 200);
}

function startAmbientAudio() {
    if (!audioCtx) {
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        audioCtx = new AudioContextClass();
        
        gainNode = audioCtx.createGain();
        const volSlider = document.getElementById('audio-volume-slider');
        gainNode.gain.value = volSlider ? parseFloat(volSlider.value) : 0.5;
        gainNode.connect(audioCtx.destination);
    }
    
    if (audioCtx.state === 'suspended') {
        audioCtx.resume();
    }
    
    stopSoundNodes();
    isPlayingAudio = true;
    
    const select = document.getElementById('ambient-sound-select');
    const soundType = select ? select.value : 'brown';
    
    // Waveform indicator color mapping
    let accentColor = '#8b5cf6'; // default purple
    if (soundType === 'brown') accentColor = '#dfad8f';
    else if (soundType === 'pink') accentColor = '#f472b6';
    else if (soundType === 'white') accentColor = '#ffffff';
    else if (soundType === 'rain') accentColor = '#38bdf8';
    else if (soundType === 'fire') accentColor = '#fb923c';
    else if (soundType === 'waves') accentColor = '#2dd4bf';
    else if (soundType === 'drone') accentColor = '#a78bfa';
    else if (soundType === 'focus') accentColor = '#facc15';
    else if (soundType === 'alpha') accentColor = '#fbbf24';
    document.documentElement.style.setProperty('--ambient-active-color', accentColor);
    
    if (soundType === 'white' || soundType === 'pink' || soundType === 'brown' || soundType === 'rain' || soundType === 'waves') {
        let buffer;
        if (soundType === 'white') {
            buffer = createWhiteNoiseBuffer();
        } else if (soundType === 'pink' || soundType === 'waves') {
            buffer = createPinkNoiseBuffer();
        } else if (soundType === 'brown' || soundType === 'rain') {
            buffer = createBrownNoiseBuffer();
        }
        
        audioSource = audioCtx.createBufferSource();
        audioSource.buffer = buffer;
        audioSource.loop = true;
    }
    
    if (soundType === 'rain') {
        const filter = audioCtx.createBiquadFilter();
        filter.type = 'lowpass';
        filter.frequency.setValueAtTime(320, audioCtx.currentTime);
        
        const lfo = audioCtx.createOscillator();
        lfo.type = 'sine';
        lfo.frequency.value = 0.05;
        
        const lfoGain = audioCtx.createGain();
        lfoGain.gain.value = 140;
        
        lfo.connect(lfoGain);
        lfoGain.connect(filter.frequency);
        
        audioSource.connect(filter);
        filter.connect(gainNode);
        
        lfo.start();
        rainNodes.push(lfo);
        rainNodes.push(lfoGain);
        rainNodes.push(filter);
        
        startAmbientScheduler('rain');
        audioSource.start();
        
    } else if (soundType === 'fire') {
        const bgSource = audioCtx.createBufferSource();
        bgSource.buffer = createBrownNoiseBuffer();
        bgSource.loop = true;
        
        const filter = audioCtx.createBiquadFilter();
        filter.type = 'lowpass';
        filter.frequency.setValueAtTime(140, audioCtx.currentTime);
        
        const lfo = audioCtx.createOscillator();
        lfo.type = 'sine';
        lfo.frequency.value = 1.2;
        
        const lfoGain = audioCtx.createGain();
        lfoGain.gain.value = 0.04;
        
        const bgGain = audioCtx.createGain();
        bgGain.gain.value = 0.15;
        
        lfo.connect(lfoGain);
        lfoGain.connect(bgGain.gain);
        
        bgSource.connect(filter);
        filter.connect(bgGain);
        bgGain.connect(gainNode);
        
        bgSource.start();
        lfo.start();
        
        rainNodes.push(bgSource, filter, lfo, lfoGain, bgGain);
        startAmbientScheduler('fire');
        
    } else if (soundType === 'waves') {
        const filter = audioCtx.createBiquadFilter();
        filter.type = 'lowpass';
        filter.frequency.value = 450;
        
        const waveGain = audioCtx.createGain();
        waveGain.gain.value = 0.28;
        
        const lfo = audioCtx.createOscillator();
        lfo.type = 'sine';
        lfo.frequency.value = 0.12;
        
        const lfoFilterGain = audioCtx.createGain();
        lfoFilterGain.gain.value = 320;
        
        const lfoVolumeGain = audioCtx.createGain();
        lfoVolumeGain.gain.value = 0.22;
        
        lfo.connect(lfoFilterGain);
        lfoFilterGain.connect(filter.frequency);
        
        lfo.connect(lfoVolumeGain);
        lfoVolumeGain.connect(waveGain.gain);
        
        audioSource.connect(waveGain);
        waveGain.connect(filter);
        filter.connect(gainNode);
        
        lfo.start();
        audioSource.start();
        
        rainNodes.push(lfo, lfoFilterGain, lfoVolumeGain, waveGain, filter);
        
    } else if (soundType === 'drone') {
        const osc1 = audioCtx.createOscillator();
        osc1.type = 'sawtooth';
        osc1.frequency.value = 55;
        
        const osc2 = audioCtx.createOscillator();
        osc2.type = 'triangle';
        osc2.frequency.value = 82.5;
        
        const osc3 = audioCtx.createOscillator();
        osc3.type = 'sawtooth';
        osc3.frequency.value = 55.4;
        
        const osc4 = audioCtx.createOscillator();
        osc4.type = 'triangle';
        osc4.frequency.value = 110;
        
        const droneGain = audioCtx.createGain();
        droneGain.gain.value = 0.08;
        
        const filter = audioCtx.createBiquadFilter();
        filter.type = 'lowpass';
        filter.frequency.value = 160;
        filter.Q.value = 3.5;
        
        const lfo = audioCtx.createOscillator();
        lfo.type = 'sine';
        lfo.frequency.value = 0.06;
        
        const lfoFilterGain = audioCtx.createGain();
        lfoFilterGain.gain.value = 70;
        
        lfo.connect(lfoFilterGain);
        lfoFilterGain.connect(filter.frequency);
        
        osc1.connect(droneGain);
        osc2.connect(droneGain);
        osc3.connect(droneGain);
        osc4.connect(droneGain);
        
        droneGain.connect(filter);
        filter.connect(gainNode);
        
        osc1.start();
        osc2.start();
        osc3.start();
        osc4.start();
        lfo.start();
        
        rainNodes.push(osc1, osc2, osc3, osc4, droneGain, filter, lfo, lfoFilterGain);
        
    } else if (soundType === 'focus') {
        const merger = audioCtx.createChannelMerger(2);
        
        const oscLeft = audioCtx.createOscillator();
        oscLeft.type = 'sine';
        oscLeft.frequency.value = 140;
        
        const oscRight = audioCtx.createOscillator();
        oscRight.type = 'sine';
        oscRight.frequency.value = 144;
        
        oscLeft.connect(merger, 0, 0);
        oscRight.connect(merger, 0, 1);
        
        const binGain = audioCtx.createGain();
        binGain.gain.value = 0.12;
        
        merger.connect(binGain);
        
        const noiseSource = audioCtx.createBufferSource();
        noiseSource.buffer = createPinkNoiseBuffer();
        noiseSource.loop = true;
        
        const noiseFilter = audioCtx.createBiquadFilter();
        noiseFilter.type = 'lowpass';
        noiseFilter.frequency.value = 220;
        
        const noiseGain = audioCtx.createGain();
        noiseGain.gain.value = 0.08;
        
        noiseSource.connect(noiseFilter);
        noiseFilter.connect(noiseGain);
        
        binGain.connect(gainNode);
        noiseGain.connect(gainNode);
        
        oscLeft.start();
        oscRight.start();
        noiseSource.start();
        
        rainNodes.push(oscLeft, oscRight, merger, binGain, noiseSource, noiseFilter, noiseGain);
        
    } else if (soundType === 'alpha') {
        const merger = audioCtx.createChannelMerger(2);
        
        const oscLeft = audioCtx.createOscillator();
        oscLeft.type = 'sine';
        oscLeft.frequency.value = 140;
        
        const oscRight = audioCtx.createOscillator();
        oscRight.type = 'sine';
        oscRight.frequency.value = 150; // 10Hz differential (Alpha waves)
        
        oscLeft.connect(merger, 0, 0);
        oscRight.connect(merger, 0, 1);
        
        const binGain = audioCtx.createGain();
        binGain.gain.value = 0.12;
        merger.connect(binGain);
        
        const noiseSource = audioCtx.createBufferSource();
        noiseSource.buffer = createPinkNoiseBuffer();
        noiseSource.loop = true;
        
        const noiseFilter = audioCtx.createBiquadFilter();
        noiseFilter.type = 'lowpass';
        noiseFilter.frequency.value = 220;
        
        const noiseGain = audioCtx.createGain();
        noiseGain.gain.value = 0.08;
        
        noiseSource.connect(noiseFilter);
        noiseFilter.connect(noiseGain);
        
        binGain.connect(gainNode);
        noiseGain.connect(gainNode);
        
        oscLeft.start();
        oscRight.start();
        noiseSource.start();
        
        rainNodes.push(oscLeft, oscRight, merger, binGain, noiseSource, noiseFilter, noiseGain);
    } else {
        audioSource.connect(gainNode);
        audioSource.start();
    }
}

function stopAmbientAudio() {
    isPlayingAudio = false;
    stopSoundNodes();
    if (ambientSchedulerInterval) {
        clearInterval(ambientSchedulerInterval);
        ambientSchedulerInterval = null;
    }
}

function stopSoundNodes() {
    if (audioSource) {
        try {
            audioSource.stop();
            audioSource.disconnect();
        } catch(e) {}
        audioSource = null;
    }
    rainNodes.forEach(node => {
        if (node instanceof OscillatorNode || node instanceof AudioBufferSourceNode) {
            try {
                node.stop();
            } catch(e) {}
        }
        try {
            node.disconnect();
        } catch(e) {}
    });
    rainNodes = [];
}

function changeAmbientSound() {
    if (isPlayingAudio) {
        startAmbientAudio();
    }
}

function selectAmbientSound(soundType) {
    document.querySelectorAll('.audio-preset-btn').forEach(btn => {
        if (btn.getAttribute('data-sound') === soundType) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
    
    const select = document.getElementById('ambient-sound-select');
    if (select) {
        select.value = soundType;
    }
    
    if (isPlayingAudio) {
        startAmbientAudio();
    }
}

function toggleMuteAmbient() {
    const volSlider = document.getElementById('audio-volume-slider');
    const iconBtn = document.getElementById('volume-icon-btn');
    if (!volSlider || !iconBtn) return;
    
    const currentVal = parseFloat(volSlider.value);
    if (currentVal > 0) {
        preMuteVolume = currentVal;
        volSlider.value = 0;
        iconBtn.textContent = '🔇';
        iconBtn.title = "Unmute";
    } else {
        volSlider.value = preMuteVolume;
        iconBtn.textContent = '🔊';
        iconBtn.title = "Mute";
    }
    adjustAmbientVolume(volSlider.value);
}

function updateVolumeSliderBackground(slider) {
    const value = (slider.value - slider.min) / (slider.max - slider.min) * 100;
    slider.style.background = `linear-gradient(to right, var(--ambient-active-color, var(--active-mode-color, var(--work-color))) 0%, var(--ambient-active-color, var(--active-mode-color, var(--work-color))) ${value}%, rgba(255, 255, 255, 0.08) ${value}%, rgba(255, 255, 255, 0.08) 100%)`;
}

function adjustAmbientVolume(val) {
    if (gainNode && audioCtx) {
        gainNode.gain.setValueAtTime(parseFloat(val), audioCtx.currentTime);
    }
    const volSlider = document.getElementById('audio-volume-slider');
    if (volSlider) {
        updateVolumeSliderBackground(volSlider);
    }
    
    const iconBtn = document.getElementById('volume-icon-btn');
    if (iconBtn) {
        if (parseFloat(val) > 0) {
            iconBtn.textContent = '🔊';
            iconBtn.title = "Mute";
        } else {
            iconBtn.textContent = '🔇';
            iconBtn.title = "Unmute";
        }
    }
}

// ==========================================
// Dynamic Liquid Battery Bubbles
// ==========================================
let bubbleInterval = null;

function updateBatteryBubbles(isCharging) {
    const container = document.getElementById('battery-bubbles');
    if (!container) return;
    
    if (!isCharging) {
        if (bubbleInterval) {
            clearInterval(bubbleInterval);
            bubbleInterval = null;
        }
        container.innerHTML = '';
        return;
    }
    
    if (bubbleInterval) return; // already active
    
    bubbleInterval = setInterval(() => {
        const bubble = document.createElement('div');
        bubble.className = 'battery-bubble';
        
        const size = Math.random() * 6 + 4; // 4px to 10px
        bubble.style.width = `${size}px`;
        bubble.style.height = `${size}px`;
        bubble.style.left = `${Math.random() * 100}%`;
        
        const duration = Math.random() * 2.5 + 2; // 2s to 4.5s
        bubble.style.animation = `bubble-float ${duration}s ease-in forwards`;
        
        container.appendChild(bubble);
        
        setTimeout(() => {
            bubble.remove();
        }, duration * 1000);
    }, 450);
}

// ==========================================
// Manual Lockout Trigger
// ==========================================
async function triggerManualLockout() {
    try {
        const res = await fetch('/api/status/lockout', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });
        if (res.ok) {
            const data = await res.json();
            showToast(data.message || "Starting your restful break. Please relax your eyes! 🌸");
            pollStatus();
        } else {
            showToast("Failed to trigger manual break", true);
        }
    } catch(err) {
        console.error(err);
        showToast("Error triggering manual rest break", true);
    }
}

// ==========================================
// Keyboard Shortcuts (1/2/3 for tabs)
// ==========================================
document.addEventListener('keydown', (e) => {
    // Don't trigger if user is typing in an input/textarea
    const tag = document.activeElement.tagName.toLowerCase();
    if (tag === 'input' || tag === 'textarea' || tag === 'select') return;
    
    switch(e.key) {
        case '1':
            switchTab('dashboard');
            break;
        case '2':
            switchTab('analytics');
            break;
        case '3':
            switchTab('settings');
            break;
    }
});

// ==========================================
// Scroll-to-Top Button
// ==========================================
function scrollToTop() {
    const mainContent = document.querySelector('.main-content');
    if (mainContent) {
        mainContent.scrollTo({ top: 0, behavior: 'smooth' });
    }
}

(function initScrollToTop() {
    const mainContent = document.querySelector('.main-content');
    const scrollBtn = document.getElementById('scroll-top-btn');
    if (!mainContent || !scrollBtn) return;
    
    mainContent.addEventListener('scroll', () => {
        if (mainContent.scrollTop > 300) {
            scrollBtn.classList.add('visible');
        } else {
            scrollBtn.classList.remove('visible');
        }
    });
})();

// ==========================================
// Loading Skeleton Show/Hide
// ==========================================
function hideSkeletons() {
    document.querySelectorAll('.skeleton-container').forEach(el => {
        el.style.display = 'none';
    });
}

// ==========================================
// Sidebar Resizing Logic
// ==========================================
(function initSidebarResizer() {
    const sidebar = document.querySelector('.sidebar');
    const resizer = document.getElementById('sidebar-resizer');
    const container = document.querySelector('.app-container');
    
    if (!resizer || !sidebar || !container) return;
    
    // Load saved width from localStorage
    const savedWidth = localStorage.getItem('sidebar-width');
    if (savedWidth && window.innerWidth > 900) {
        container.style.setProperty('--sidebar-width', `${savedWidth}px`);
        setTimeout(updateNavIndicator, 100);
    }
    
    resizer.addEventListener('mousedown', (e) => {
        e.preventDefault();
        
        document.body.classList.add('resizing');
        resizer.classList.add('resizing');
        
        const startX = e.clientX;
        const startWidth = sidebar.getBoundingClientRect().width;
        
        function onMouseMove(moveEvent) {
            const currentX = moveEvent.clientX;
            // Enforce limits: 200px min, 450px max
            const newWidth = Math.max(200, Math.min(450, startWidth + (currentX - startX)));
            container.style.setProperty('--sidebar-width', `${newWidth}px`);
            localStorage.setItem('sidebar-width', newWidth);
            
            updateNavIndicator();
        }
        
        function onMouseUp() {
            document.body.classList.remove('resizing');
            resizer.classList.remove('resizing');
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
            setTimeout(updateNavIndicator, 50);
        }
        
        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
    });
})();

// ==========================================
// Collapsible Soundbox Widget
// ==========================================
function toggleSoundboxCollapse() {
    const body = document.getElementById('soundbox-body');
    const caret = document.getElementById('soundbox-caret');
    if (!body || !caret) return;
    
    const isCollapsed = body.classList.toggle('collapsed');
    caret.textContent = isCollapsed ? '▲' : '▼';
    localStorage.setItem('soundbox-collapsed', isCollapsed ? 'true' : 'false');
    
    // Update active nav indicator position as sidebar height changes
    setTimeout(updateNavIndicator, 320);
}

// Initialize soundbox collapsed state
(function initSoundboxCollapse() {
    const body = document.getElementById('soundbox-body');
    const caret = document.getElementById('soundbox-caret');
    if (!body || !caret) return;
    
    const isCollapsed = localStorage.getItem('soundbox-collapsed') === 'true';
    if (isCollapsed) {
        body.classList.add('collapsed');
        caret.textContent = '▲';
    }
})();

// ==========================================
// Micro-Goals Management Controller
// ==========================================
function updateGoalUI(goal) {
    const inputArea = document.getElementById('goal-input-area');
    const displayArea = document.getElementById('goal-display-area');
    const displayText = document.getElementById('goal-display-text');
    const inputField = document.getElementById('goal-input');
    
    if (goal && goal.trim() !== "") {
        if (inputArea && inputArea.style.display !== 'none') {
            inputArea.style.display = 'none';
        }
        if (displayArea && displayArea.style.display !== 'flex') {
            displayArea.style.display = 'flex';
        }
        if (displayText && displayText.textContent !== goal) {
            displayText.textContent = goal;
        }
    } else {
        // Transition from active goal display mode to input mode
        if (displayArea && displayArea.style.display !== 'none') {
            if (inputArea) inputArea.style.display = 'flex';
            displayArea.style.display = 'none';
            if (inputField) inputField.value = '';
        }
        // If displayArea is already hidden (meaning we are already in input mode),
        // we do NOT touch inputArea or inputField.value to prevent overwriting user input during periodic status polls.
    }
}

async function loadGoal() {
    try {
        const res = await fetch('/api/goal');
        const data = await res.json();
        updateGoalUI(data.goal);
    } catch(e) {
        console.error("Error loading goal:", e);
    }
}

async function saveGoal() {
    const inputField = document.getElementById('goal-input');
    if (!inputField) return;
    
    const goal = inputField.value.trim();
    if (goal === "") {
        showToast("Please enter a goal first", true);
        return;
    }
    
    try {
        const res = await fetch('/api/goal', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ goal: goal })
        });
        if (res.ok) {
            const data = await res.json();
            updateGoalUI(data.goal);
            showToast("Focus intention set!");
        } else {
            showToast("Failed to save goal", true);
        }
    } catch(e) {
        showToast("Network error setting goal", true);
    }
}

async function clearGoal() {
    const displayText = document.getElementById('goal-display-text');
    const inputField = document.getElementById('goal-input');
    const goalText = displayText ? displayText.textContent : "";
    
    try {
        const res = await fetch('/api/goal', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ goal: "" })
        });
        if (res.ok) {
            updateGoalUI("");
            if (inputField) {
                inputField.value = goalText;
                inputField.focus();
            }
            showToast("Focus intention cleared");
        }
    } catch(e) {
        showToast("Error clearing goal", true);
    }
}

async function completeGoal() {
    const displayText = document.getElementById('goal-display-text');
    const goalText = displayText ? displayText.textContent : "";
    
    try {
        // 1. Post to reflections as a win automatically
        const resRefl = await fetch('/api/reflections', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                energy_level: 5,
                friction_level: 1,
                summary: `[Coding Win] Completed Focus Goal: ${goalText}`
            })
        });
        
        // 2. Clear active goal
        const resClear = await fetch('/api/goal', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ goal: "" })
        });
        
        if (resRefl.ok && resClear.ok) {
            updateGoalUI("");
            showToast("Intention accomplished! Logged in private vault.");
            
            // Trigger particle burst at complete button
            const completeBtn = document.querySelector('.goal-complete-btn');
            if (completeBtn) {
                const rect = completeBtn.getBoundingClientRect();
                const fakeEvent = {
                    clientX: rect.left + rect.width / 2,
                    clientY: rect.top + rect.height / 2
                };
                triggerParticleBurst(fakeEvent);
            }
            
            pollStatus();
            loadAnalytics();
        } else {
            showToast("Failed to complete goal", true);
        }
    } catch(e) {
        showToast("Error completing goal", true);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    loadGoal();
    // Fetch initial hydration
    fetch('/api/hydration')
        .then(r => r.json())
        .then(data => updateHydrationUI(data))
        .catch(e => console.error("Error loading hydration: ", e));
    
    // Initialize grounding stepper UI
    updateGroundingUI();

    // Bind event listeners for hydration buttons dynamically
    const hydrationAddBtn = document.getElementById('hydration-quick-add-btn');
    const hydrationSubBtn = document.getElementById('hydration-quick-sub-btn');
    if (hydrationAddBtn) {
        hydrationAddBtn.addEventListener('click', (e) => {
            e.preventDefault();
            logHydrationQuick(e);
        });
    }
    if (hydrationSubBtn) {
        hydrationSubBtn.addEventListener('click', (e) => {
            e.preventDefault();
            logHydrationQuickSub(e);
        });
    }

    // Support submitting goal with Enter key
    const goalInput = document.getElementById('goal-input');
    if (goalInput) {
        goalInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                saveGoal();
            }
        });
    }

    // Initialize Mindful Word Recommender UI
    updateWordRecommenderUI();
});

// Prefill Gratitude Reflection Input
function prefillGratitude() {
    const input = document.getElementById('reflection-summary');
    if (input) {
        input.value = "[Gratitude] 3 things I'm grateful for: 1.  2.  3. ";
        input.focus();
        const pos = "[Gratitude] 3 things I'm grateful for: ".length;
        input.setSelectionRange(pos, pos);
    }
}

// Hydration logging controller
let currentHydrationIncrement = 1;
let lastPresetsUnit = null;

async function logHydrationDelta(delta, e) {
    try {
        const res = await fetch('/api/hydration', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ delta: delta })
        });
        if (res.ok) {
            const data = await res.json();
            updateHydrationUI(data.hydration);
            if (delta > 0) {
                showToast(`Logged +${delta} water! Stay hydrated. 💧`);
                if (e) triggerParticleBurst(e, '#38bdf8');
                
                // If goal is met, do a celebratory burst at the beaker!
                if (data.hydration.cups >= data.hydration.target) {
                    const beaker = document.querySelector('.hydration-beaker');
                    if (beaker) {
                        const rect = beaker.getBoundingClientRect();
                        triggerParticleBurst({
                            clientX: rect.left + rect.width / 2,
                            clientY: rect.top + rect.height / 2
                        }, '#10b981');
                    }
                }
            } else {
                showToast(`Subtracted ${Math.abs(delta)} water. 💧`);
                if (e) triggerParticleBurst(e, '#f43f5e');
            }
        }
    } catch(e) {
        console.error("Failed to log hydration delta: ", e);
    }
}

function logHydrationQuick(e) {
    console.log("logHydrationQuick clicked. currentHydrationIncrement =", currentHydrationIncrement);
    const inc = parseFloat(currentHydrationIncrement) || 1;
    logHydrationDelta(inc, e);
}

function logHydrationQuickSub(e) {
    console.log("logHydrationQuickSub clicked. currentHydrationIncrement =", currentHydrationIncrement);
    const inc = parseFloat(currentHydrationIncrement) || 1;
    logHydrationDelta(-inc, e);
}

// Legacy logHydration for backward compatibility
async function logHydration(index) {
    logHydrationDelta(1);
}

function updateHydrationUI(hydration) {
    const cups = hydration.cups || 0;
    const target = hydration.target || 8;
    const unit = hydration.unit || "cups";
    const increment = hydration.increment || 1;
    currentHydrationIncrement = increment;

    const pct = Math.min(100, Math.round((cups / target) * 100));
    
    const pctText = document.getElementById('hydration-pct-text');
    const msgText = document.getElementById('hydration-msg');
    const liquidFill = document.getElementById('hydration-liquid-fill');
    const quickBtn = document.getElementById('hydration-quick-add-btn');
    
    if (pctText) pctText.textContent = `${pct}%`;
    if (msgText) {
        if (cups >= target) {
            msgText.textContent = `Goal met! (${cups}/${target} ${unit}) 💧`;
            msgText.style.color = "var(--recharge-color)";
        } else {
            msgText.textContent = `${cups}/${target} ${unit} logged.`;
            msgText.style.color = "var(--text-muted)";
        }
    }
    
    if (liquidFill) {
        // Set fill height (rises from bottom)
        liquidFill.style.height = `${pct}%`;
        if (pct === 0) {
            liquidFill.style.opacity = '0';
        } else {
            liquidFill.style.opacity = '1';
        }
        if (pct >= 100) {
            liquidFill.classList.add('full');
        } else {
            liquidFill.classList.remove('full');
        }
    }
    
    if (quickBtn) {
        quickBtn.textContent = `+ Log ${increment} ${unit}`;
    }
    
    const container = document.getElementById('hydration-presets-container');
    if (container && unit !== lastPresetsUnit) {
        container.innerHTML = '';
        let presets = [];
        if (unit === "cups") presets = [0.5, 1, 2];
        else if (unit === "ml") presets = [250, 500, 750];
        else if (unit === "oz") presets = [8, 12, 16];
        
        presets.forEach(p => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'hydration-preset-btn';
            btn.textContent = `+${p} ${unit}`;
            btn.onclick = (ev) => logHydrationDelta(p, ev);
            container.appendChild(btn);
        });
        lastPresetsUnit = unit;
    }
}

// Zen Space tab custom interactive canvas
let zenCanvas = null;
let zenCtx = null;
let zenAnimFrame = null;
let zenParticles = [];
const MAX_ZEN_PARTICLES = 120;
let zenMouse = { x: null, y: null, active: false };
let zenStartTime = 0;

class ZenParticle {
    constructor(w, h) {
        this.reset(w, h);
    }
    reset(w, h) {
        this.x = Math.random() * w;
        this.y = Math.random() * h;
        this.vx = (Math.random() - 0.5) * 0.4;
        this.vy = (Math.random() - 0.5) * 0.4;
        this.baseSize = Math.random() * 2 + 1;
        this.size = this.baseSize;
        this.colorVal = Math.random();
        this.alpha = Math.random() * 0.5 + 0.3;
    }
    update(w, h, breathFactor) {
        this.x += this.vx;
        this.y += this.vy;
        
        if (this.x < 0 || this.x > w) this.vx *= -1;
        if (this.y < 0 || this.y > h) this.vy *= -1;
        
        if (zenMouse.active && zenMouse.x !== null && zenMouse.y !== null) {
            const dx = zenMouse.x - this.x;
            const dy = zenMouse.y - this.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            if (dist < 120) {
                const force = (120 - dist) / 120;
                this.x -= (dx / dist) * force * 1.5;
                this.y -= (dy / dist) * force * 1.5;
            }
        }
        
        this.size = this.baseSize * (1 + breathFactor * 1.2);
    }
    draw(ctx) {
        let r, g, b;
        if (this.colorVal < 0.4) {
            r = 45; g = 212; b = 168;
        } else if (this.colorVal < 0.8) {
            r = 167; g = 139; b = 250;
        } else {
            r = 251; g = 191; b = 36;
        }
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${this.alpha})`;
        ctx.fill();
    }
}

function initZenCanvas() {
    zenCanvas = document.getElementById('zen-canvas');
    if (!zenCanvas) return;
    
    zenCtx = zenCanvas.getContext('2d');
    resizeZenCanvas();
    
    zenParticles = [];
    for (let i = 0; i < MAX_ZEN_PARTICLES; i++) {
        zenParticles.push(new ZenParticle(zenCanvas.width, zenCanvas.height));
    }
    
    zenCanvas.addEventListener('mousemove', handleZenMouseMove);
    zenCanvas.addEventListener('mouseleave', handleZenMouseLeave);
    zenCanvas.addEventListener('mouseenter', handleZenMouseEnter);
    window.addEventListener('resize', resizeZenCanvas);
    
    zenStartTime = Date.now();
    
    if (zenAnimFrame) cancelAnimationFrame(zenAnimFrame);
    animateZen();
}

function stopZenCanvas() {
    if (zenAnimFrame) {
        cancelAnimationFrame(zenAnimFrame);
        zenAnimFrame = null;
    }
    if (zenCanvas) {
        zenCanvas.removeEventListener('mousemove', handleZenMouseMove);
        zenCanvas.removeEventListener('mouseleave', handleZenMouseLeave);
        zenCanvas.removeEventListener('mouseenter', handleZenMouseEnter);
    }
    window.removeEventListener('resize', resizeZenCanvas);
}

function resizeZenCanvas() {
    if (!zenCanvas) return;
    const rect = zenCanvas.parentElement.getBoundingClientRect();
    zenCanvas.width = rect.width;
    zenCanvas.height = rect.height;
    
    zenParticles.forEach(p => {
        if (p.x > zenCanvas.width || p.y > zenCanvas.height) {
            p.reset(zenCanvas.width, zenCanvas.height);
        }
    });
}

function handleZenMouseMove(e) {
    if (!zenCanvas) return;
    const rect = zenCanvas.getBoundingClientRect();
    zenMouse.x = e.clientX - rect.left;
    zenMouse.y = e.clientY - rect.top;
}

function handleZenMouseLeave() {
    zenMouse.active = false;
    zenMouse.x = null;
    zenMouse.y = null;
}

function handleZenMouseEnter() {
    zenMouse.active = true;
}

function resetZenParticles() {
    if (!zenCanvas) return;
    zenParticles.forEach(p => p.reset(zenCanvas.width, zenCanvas.height));
    showToast("Stardust regenerated ✨");
}

function animateZen() {
    if (!zenCanvas || !zenCtx) return;
    
    const w = zenCanvas.width;
    const h = zenCanvas.height;
    
    zenCtx.clearRect(0, 0, w, h);
    
    const elapsed = (Date.now() - zenStartTime) / 1000;
    const cycleTime = elapsed % 16.0;
    
    let breathFactor = 0;
    let breathText = "";
    let breathColor = "rgba(45, 212, 168, 0.4)";
    let textGlowColor = "#2dd4a8";
    
    if (cycleTime < 4.0) {
        breathFactor = cycleTime / 4.0;
        breathText = "Inhale";
        breathColor = "rgba(45, 212, 168, 0.35)";
        textGlowColor = "#2dd4a8";
    } else if (cycleTime < 8.0) {
        breathFactor = 1.0;
        breathText = "Hold";
        breathColor = "rgba(251, 191, 36, 0.35)";
        textGlowColor = "#fbbf24";
    } else if (cycleTime < 12.0) {
        breathFactor = 1.0 - (cycleTime - 8.0) / 4.0;
        breathText = "Exhale";
        breathColor = "rgba(167, 139, 250, 0.35)";
        textGlowColor = "#a78bfa";
    } else {
        breathFactor = 0.0;
        breathText = "Hold";
        breathColor = "rgba(244, 63, 94, 0.35)";
        textGlowColor = "#f43f5e";
    }
    
    zenParticles.forEach(p => {
        p.update(w, h, breathFactor);
        p.draw(zenCtx);
    });
    
    for (let i = 0; i < zenParticles.length; i++) {
        for (let j = i + 1; j < zenParticles.length; j++) {
            const p1 = zenParticles[i];
            const p2 = zenParticles[j];
            const dx = p1.x - p2.x;
            const dy = p1.y - p2.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            
            if (dist < 60) {
                const alpha = (60 - dist) / 60 * 0.15;
                zenCtx.beginPath();
                zenCtx.moveTo(p1.x, p1.y);
                zenCtx.lineTo(p2.x, p2.y);
                zenCtx.strokeStyle = `rgba(255, 255, 255, ${alpha})`;
                zenCtx.lineWidth = 0.5;
                zenCtx.stroke();
            }
        }
    }
    
    const breatherBubble = document.getElementById('zen-breather-bubble');
    const breatherText = document.getElementById('zen-breather-text');
    if (breatherBubble && breatherText) {
        const scaleVal = 1 + breathFactor * 0.8;
        breatherBubble.style.transform = `translate(-50%, -50%) scale(${scaleVal})`;
        breatherBubble.style.borderColor = breathColor;
        breatherBubble.style.boxShadow = `0 0 ${20 + breathFactor * 25}px ${breathColor}`;
        
        breatherText.textContent = breathText;
        breatherText.style.color = textGlowColor;
    }
    
    zenAnimFrame = requestAnimationFrame(animateZen);
}

// CURATED FOCUS WISDOM & AFFIRMATIONS
const WISDOM_QUOTES = [
    "Focus is the art of deciding what NOT to do right now.",
    "You are not a machine; your value is not measured by uninterrupted output.",
    "Breathe in energy, breathe out friction. Focus on one micro-step at a time.",
    "Rest is not laziness; it is the raw fuel of deep creativity.",
    "Progress over perfection. Celebrate your small wins today.",
    "Look away from the screen, drop your shoulders, and relax your jaw.",
    "A clear mind creates clean code. Step back to step forward.",
    "Hydrate your body, pace your mind, protect your focus.",
    "Tension is who you think you should be. Relaxation is who you are.",
    "One single intention holds more power than a dozen scattered tasks."
];
let currentWisdomIndex = 2; // Default starting quote

function cycleWisdom() {
    const quoteText = document.getElementById('wisdom-quote-text');
    if (!quoteText) return;
    
    let nextIdx = currentWisdomIndex;
    while (nextIdx === currentWisdomIndex) {
        nextIdx = Math.floor(Math.random() * WISDOM_QUOTES.length);
    }
    currentWisdomIndex = nextIdx;
    
    quoteText.style.opacity = '0';
    setTimeout(() => {
        quoteText.textContent = `"${WISDOM_QUOTES[currentWisdomIndex]}"`;
        quoteText.style.opacity = '1';
    }, 300);
}

// 5-4-3-2-1 SENSORY GROUNDING STEPPER
const GROUNDING_STEPS = [
    {
        badge: "Step 1 of 5",
        sense: "👀 Sight",
        title: "Find 5 things you can see",
        desc: "Acknowledge 5 items in your visual field. Type them below to ground your focus.",
        count: 5,
        placeholders: ["Object 1", "Object 2", "Object 3", "Object 4", "Object 5"]
    },
    {
        badge: "Step 2 of 5",
        sense: "🤝 Touch",
        title: "Acknowledge 4 things you can feel",
        desc: "Notice the physical sensations: texture, temperature, or pressure (e.g. keyboard keys, desk, fabric).",
        count: 4,
        placeholders: ["Sensation 1", "Sensation 2", "Sensation 3", "Sensation 4"]
    },
    {
        badge: "Step 3 of 5",
        sense: "👂 Sound",
        title: "Listen for 3 distinct sounds",
        desc: "Focus on 3 sounds in your environment (e.g. humming fan, keyboard click, distant traffic).",
        count: 3,
        placeholders: ["Sound 1", "Sound 2", "Sound 3"]
    },
    {
        badge: "Step 4 of 5",
        sense: "👃 Smell",
        title: "Identify 2 things you can smell",
        desc: "Inhale deeply. Notice any aromas in the air, or recall pleasant scents.",
        count: 2,
        placeholders: ["Scent 1", "Scent 2"]
    },
    {
        badge: "Step 5 of 5",
        sense: "👅 Taste / Affirmation",
        title: "Write 1 thing you can taste or an affirmation",
        desc: "Note a lingering taste, or type a positive self-affirmation for your work session.",
        count: 1,
        placeholders: ["Taste or positive statement..."]
    }
];
let currentGroundingStep = 0;

function updateGroundingUI() {
    const step = GROUNDING_STEPS[currentGroundingStep];
    const badgeEl = document.getElementById('grounding-badge');
    const senseEl = document.getElementById('grounding-sense');
    const titleEl = document.getElementById('grounding-prompt-title');
    const descEl = document.getElementById('grounding-prompt-desc');
    const inputsContainer = document.getElementById('grounding-inputs-area');
    
    if (!badgeEl || !senseEl || !titleEl || !descEl || !inputsContainer) return;
    
    badgeEl.textContent = step.badge;
    senseEl.textContent = step.sense;
    titleEl.textContent = step.title;
    descEl.textContent = step.desc;
    
    inputsContainer.innerHTML = '';
    for (let i = 0; i < step.count; i++) {
        const row = document.createElement('div');
        row.className = 'grounding-input-row';
        row.style.marginBottom = '0.5rem';
        
        const input = document.createElement('input');
        input.type = 'text';
        input.className = 'grounding-field';
        input.id = `grounding-input-${i}`;
        input.placeholder = step.placeholders[i] || `Item ${i+1}...`;
        
        row.appendChild(input);
        inputsContainer.appendChild(row);
    }
    
    const prevBtn = document.getElementById('grounding-prev-btn');
    if (prevBtn) {
        prevBtn.style.display = currentGroundingStep === 0 ? 'none' : 'block';
    }
    
    const nextBtn = document.getElementById('grounding-next-btn');
    if (nextBtn) {
        if (currentGroundingStep === 4) {
            nextBtn.textContent = "Complete Reset";
        } else {
            nextBtn.textContent = "Next Step";
        }
    }
}

function prevGroundingStep() {
    if (currentGroundingStep > 0) {
        currentGroundingStep--;
        updateGroundingUI();
    }
}

async function nextGroundingStep() {
    const firstInput = document.getElementById('grounding-input-0');
    if (firstInput && !firstInput.value.trim()) {
        showToast("Please acknowledge at least the first item to continue.", true);
        firstInput.focus();
        return;
    }
    
    if (currentGroundingStep < 4) {
        currentGroundingStep++;
        updateGroundingUI();
    } else {
        try {
            const res = await fetch('/api/reflections', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    energy_level: 4,
                    friction_level: 1,
                    summary: "[Mindfulness Reset] Completed 5-4-3-2-1 grounding exercise."
                })
            });
            if (res.ok) {
                showToast("Mindfulness Grounding Completed! mental battery recharged. 🌟");
                
                const nextBtn = document.getElementById('grounding-next-btn');
                if (nextBtn) {
                    const rect = nextBtn.getBoundingClientRect();
                    triggerParticleBurst({
                        clientX: rect.left + rect.width / 2,
                        clientY: rect.top + rect.height / 2
                    });
                }
                
                currentGroundingStep = 0;
                updateGroundingUI();
                
                pollStatus();
                loadAnalytics();
            }
        } catch(e) {
            showToast("Error saving mindfulness reset", true);
        }
    }
}

// ==========================================
// Mindful Word Recommender Controllers
// ==========================================
const ZEN_WORDS = [
    { word: "Stillness", pronounce: "/ˈstɪlnəs/", category: "Calm", prompt: "Observe the quiet space between your breaths. In this stillness, find your center." },
    { word: "Clarity", pronounce: "/ˈklærɪti/", category: "Focus", prompt: "Let go of scattered thoughts. Focus on a single point of light, letting other details fade." },
    { word: "Presence", pronounce: "/ˈprɛzəns/", category: "Focus", prompt: "Bring your attention entirely to the here and now. The future and past are just thoughts." },
    { word: "Release", pronounce: "/rɪˈliːs/", category: "Calm", prompt: "Unclench your jaw, drop your shoulders, and exhale completely. Let go of accumulated tension." },
    { word: "Serenity", pronounce: "/sɪˈrɛnɪti/", category: "Calm", prompt: "Accept the present moment exactly as it is. Tranquility comes from letting go of resistance." },
    { word: "Flow", pronounce: "/floʊ/", category: "Focus", prompt: "Immerse yourself in the gentle current of your actions. Let task and self merge into one." },
    { word: "Patience", pronounce: "/ˈpeɪʃəns/", category: "Growth", prompt: "Growth happens quietly and in its own time. Rest is a necessary phase of creation." },
    { word: "Gratitude", pronounce: "/ˈɡrætɪtjuːd/", category: "Growth", prompt: "Reflect on one small thing that brought you comfort today. Hold that feeling." },
    { word: "Balance", pronounce: "/ˈbæləns/", category: "Growth", prompt: "Acknowledge the rhythm of work and rest. Both are essential to sustain your energy." },
    { word: "Harmony", pronounce: "/ˈhɑːrməni/", category: "Calm", prompt: "Align your body, breath, and environment. Feel the quiet alignment within." },
    { word: "Resilience", pronounce: "/rɪˈzɪliəns/", category: "Growth", prompt: "Like a tree bending in the wind, you are flexible and strong. You can weather the challenge." },
    { word: "Simplicity", pronounce: "/sɪmˈplɪsɪti/", category: "Calm", prompt: "Strip away the unnecessary clutter. Focus on the core of what truly matters." },
    { word: "Intention", pronounce: "/ɪnˈtɛnʃən/", category: "Focus", prompt: "Define a single, gentle focus for your next hour. Let it guide your steps." },
    { word: "Compassion", pronounce: "/kəmˈpæʃən/", category: "Growth", prompt: "Be kind to yourself in moments of frustration. You are doing the best you can." },
    { word: "Acceptance", pronounce: "/əkˈsɛptəns/", category: "Calm", prompt: "Acknowledge your current state without judgment. Peace begins when struggle ends." }
];

let activeWordIndex = 0;

function updateWordRecommenderUI() {
    const wordObj = ZEN_WORDS[activeWordIndex];
    const badgeEl = document.getElementById('active-word-badge');
    const titleEl = document.getElementById('active-word-title');
    const pronounceEl = document.getElementById('active-word-pronounce');
    const promptEl = document.getElementById('active-word-prompt');
    const contentEl = document.getElementById('active-word-content');
    
    if (!badgeEl || !titleEl || !pronounceEl || !promptEl || !contentEl) return;
    
    // Add transition class
    contentEl.classList.add('fade-out');
    
    setTimeout(() => {
        // Update Content
        titleEl.textContent = wordObj.word;
        pronounceEl.textContent = wordObj.pronounce;
        promptEl.textContent = wordObj.prompt;
        
        // Update Badge class and text
        badgeEl.textContent = wordObj.category;
        badgeEl.className = 'word-badge';
        if (wordObj.category === 'Calm') {
            badgeEl.classList.add('badge-calm');
        } else if (wordObj.category === 'Focus') {
            badgeEl.classList.add('badge-focus');
        } else if (wordObj.category === 'Growth') {
            badgeEl.classList.add('badge-growth');
        }
        
        // Update curated pill active states
        document.querySelectorAll('.word-pill-btn').forEach(btn => {
            if (btn.textContent.trim().toLowerCase() === wordObj.word.toLowerCase()) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
        
        // Fade back in
        contentEl.classList.remove('fade-out');
    }, 200);
}

function recommendRandomWord() {
    let nextIdx = activeWordIndex;
    while (nextIdx === activeWordIndex) {
        nextIdx = Math.floor(Math.random() * ZEN_WORDS.length);
    }
    activeWordIndex = nextIdx;
    updateWordRecommenderUI();
}

function selectRecommendedWordByVal(wordValue) {
    const idx = ZEN_WORDS.findIndex(w => w.word.toLowerCase() === wordValue.toLowerCase());
    if (idx !== -1) {
        activeWordIndex = idx;
        updateWordRecommenderUI();
    }
}

function setAsReflectionTheme() {
    const wordObj = ZEN_WORDS[activeWordIndex];
    
    // 1. Prefill Reflection form on Dashboard
    const reflectionInput = document.getElementById('reflection-summary');
    if (reflectionInput) {
        reflectionInput.value = `[Zen Theme: ${wordObj.word}] Reflecting on the essence of ${wordObj.word.toLowerCase()} during my break.`;
    }
    
    // 2. Set ratings on quick reflection to favorable levels (peak energy, low friction)
    const energyBtn = document.querySelector('#energy-rating button[data-val="4"]');
    if (energyBtn) {
        document.querySelectorAll('#energy-rating button').forEach(b => b.classList.remove('active'));
        energyBtn.classList.add('active');
    }
    const frictionBtn = document.querySelector('#friction-rating button[data-val="1"]');
    if (frictionBtn) {
        document.querySelectorAll('#friction-rating button').forEach(b => b.classList.remove('active'));
        frictionBtn.classList.add('active');
    }
    
    // 3. Switch tab and toast
    switchTab('dashboard');
    showToast(`Focus theme set to "${wordObj.word}"! Copied to Dashboard. 🧘`);
}

async function saveZenWordReflection() {
    const wordObj = ZEN_WORDS[activeWordIndex];
    const inputEl = document.getElementById('word-reflection-input');
    if (!inputEl) return;
    
    const text = inputEl.value.trim();
    if (!text) {
        showToast("Please enter a reflection sentence first.", true);
        inputEl.focus();
        return;
    }
    
    try {
        const res = await fetch('/api/reflections', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                energy_level: 4,
                friction_level: 1,
                summary: `[Zen Reflection: ${wordObj.word}] ${text}`
            })
        });
        if (res.ok) {
            showToast(`Logged reflection on "${wordObj.word}"! Stardust recharged. ✨`);
            inputEl.value = '';
            
            // Trigger particle burst at save button
            const saveBtn = document.getElementById('save-word-reflection-btn');
            if (saveBtn) {
                const rect = saveBtn.getBoundingClientRect();
                triggerParticleBurst({
                    clientX: rect.left + rect.width / 2,
                    clientY: rect.top + rect.height / 2
                });
            }
            
            // Refresh dashboard status & analytics
            pollStatus();
            loadAnalytics();
        } else {
            showToast("Failed to save Zen reflection.", true);
        }
    } catch(e) {
        showToast("Network error saving reflection.", true);
    }
}

