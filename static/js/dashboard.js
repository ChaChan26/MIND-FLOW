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

// Timezone-safe local ISO date parser
function parseLocalDate(isoStr) {
    if (!isoStr) return new Date();
    if (isoStr.endsWith('Z') || /[+-]\d{2}:?\d{2}$/.test(isoStr)) {
        return new Date(isoStr);
    }
    const parts = isoStr.match(/(\d+)/g);
    if (!parts) return new Date(isoStr);
    
    const year = parseInt(parts[0], 10);
    const month = parseInt(parts[1], 10) - 1;
    const day = parseInt(parts[2], 10);
    const hour = parseInt(parts[3] || 0, 10);
    const minute = parseInt(parts[4] || 0, 10);
    const second = parseInt(parts[5] || 0, 10);
    const ms = parseInt((parts[6] || '0').substring(0, 3), 10);
    
    return new Date(year, month, day, hour, minute, second, ms);
}

let currentTab = 'dashboard';
let statusInterval = null;
let lastActiveTitle = '';
let lastExternalWindow = 'None';
let lastExternalProcess = 'None';
let lastWeekdaySummary = null;
let lastReflections = null;
let appStatsFilter = 'today';
let weekOffset = 0;
let lastAnalyticsLoadTime = 0;

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


// Ratings Selectors (Quick Reflection)
let selectedEnergy = 5;
let selectedFriction = 2;
let selectedMood = 'Neutral';

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

document.querySelectorAll('#mood-rating .rate-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('#mood-rating .rate-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        selectedMood = btn.getAttribute('data-val');
        
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
        clearDashboardIntervals();
    } else if (tabId === 'settings') {
        loadSettings();
        stopZenCanvas();
        clearDashboardIntervals();
    } else if (tabId === 'zen') {
        initZenCanvas();
        clearDashboardIntervals();
    } else {
        stopZenCanvas();
        restoreDashboardIntervals();
    }
}

// Clear and restore intervals to save CPU/GPU when dashboard is hidden
function clearDashboardIntervals() {
    if (hydrationBubbleInterval) {
        clearInterval(hydrationBubbleInterval);
        hydrationBubbleInterval = null;
    }
    const hydBubbles = document.getElementById('hydration-bubbles');
    if (hydBubbles) hydBubbles.innerHTML = '';
    
    if (bubbleInterval) {
        clearInterval(bubbleInterval);
        bubbleInterval = null;
    }
    const batBubbles = document.getElementById('battery-bubbles');
    if (batBubbles) batBubbles.innerHTML = '';
}

function restoreDashboardIntervals() {
    if (document.hidden) return;
    
    if (lastHydrationPct > 0) {
        updateHydrationBubbles(true);
    }
    
    const isCharging = bodyEl.classList.contains('mode-recharge') || bodyEl.classList.contains('mode-rest');
    updateBatteryBubbles(isCharging);
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
        // Removed box-shadow to eliminate hover/active side light flash
        indicator.style.boxShadow = 'none';
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
            bodyEl.classList.remove('mode-work', 'mode-recharge', 'mode-rest', 'mode-neutral');
            bodyEl.classList.add(`mode-${activeMode}`);
            requestAnimationFrame(() => {
                updateNavIndicator();
            });
            loadAnalytics();
        }
        
        // 2. Status Details
        if (!status.tracking_active) {
            currentModeTitle.textContent = "Shield Paused";
        } else {
            currentModeTitle.textContent = `${status.current_mode} mode`;
        }
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
        
        // 3. Block Timer (Enforce counts up visually) and Radial Progress
        let progress = 0;
        const timeLeftTitle = document.getElementById('time-left-title');
        
        if (status.current_mode === 'work') {
            const limit = status.adaptive_work_limit_seconds || 2700;
            const elapsed = status.elapsed_seconds || 0;
            const remaining = Math.max(0, limit - elapsed);
            
            // Show elapsed time as primary timer (how much time i did after switching)
            blockTimer.textContent = formatTime(elapsed);
            if (remaining < 60) {
                blockTimer.style.color = '#ef4444'; // Red alarm for last minute
            } else {
                blockTimer.style.color = 'var(--work-color)';
            }
            
            // Show remaining time until switch in title
            if (timeLeftTitle) {
                timeLeftTitle.textContent = `Switches in ${formatTime(remaining)}`;
            }
            
            // Progress ring fills up as elapsed time increases (until it switches)
            progress = Math.max(0, Math.min(1, elapsed / limit));
            
        } else if (status.current_mode === 'recharge') {
            const limit = status.adaptive_rest_limit_seconds || 20;
            const elapsed = status.elapsed_seconds || 0;
            const remaining = Math.max(0, limit - elapsed);
            
            blockTimer.textContent = formatTime(elapsed);
            blockTimer.style.color = 'var(--recharge-color)';
            
            if (timeLeftTitle) {
                timeLeftTitle.textContent = `Switches in ${formatTime(remaining)}`;
            }
            
            progress = Math.max(0, Math.min(1, elapsed / limit));
            
        } else if (status.current_mode === 'rest') {
            const limit = status.adaptive_rest_limit_seconds || 20;
            const elapsed = status.idle_seconds || 0;
            const remaining = Math.max(0, limit - elapsed);
            
            blockTimer.textContent = formatTime(elapsed);
            blockTimer.style.color = 'var(--rest-color)';
            
            if (timeLeftTitle) {
                timeLeftTitle.textContent = `Switches in ${formatTime(remaining)}`;
            }
            
            progress = Math.max(0, Math.min(1, elapsed / limit));
            
        } else {
            blockTimer.textContent = "00:00";
            blockTimer.style.color = 'var(--text-secondary)';
            if (timeLeftTitle) {
                timeLeftTitle.textContent = "Block Timer";
            }
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
        
        if (!status.tracking_active) {
            emoji = '🛡️';
        } else if (status.current_mode === 'work') {
            emoji = '💻';
        } else if (status.current_mode === 'recharge') {
            emoji = '🎮';
        } else if (status.current_mode === 'rest') {
            emoji = '💤';
        }
        statusIcon.textContent = emoji;
        
        // 5. Update live battery representation
        const energyLevel = status.current_energy; // 1 to 5
        const energyPct = energyLevel * 20;
        
        // Backward compatibility
        if (batteryFill) {
            batteryFill.style.width = `${energyPct}%`;
        }
        
        const prevPct = parseInt(batteryPct.textContent) || 0;
        if (prevPct !== energyPct) {
            animateValue(batteryPct, prevPct, energyPct, '%', 800);
        }
        
        // Update 5 segments active/neon color states
        const segments = document.querySelectorAll('.battery-segment');
        segments.forEach((seg, idx) => {
            const activeIdx = idx + 1;
            if (activeIdx <= energyLevel) {
                seg.classList.add('active');
                if (energyLevel <= 2) {
                    seg.className = 'battery-segment active active-low';
                } else if (energyLevel === 3) {
                    seg.className = 'battery-segment active active-mid';
                } else {
                    seg.className = 'battery-segment active active-high';
                }
            } else {
                seg.className = 'battery-segment';
            }
        });
        
        // Toggle charging layout state
        const batteryOuter = document.querySelector('.battery-outer');
        const isCharging = (status.current_mode === 'recharge' || status.current_mode === 'rest');
        if (batteryOuter) {
            if (isCharging) {
                batteryOuter.classList.add('charging');
            } else {
                batteryOuter.classList.remove('charging');
            }
        }
        
        // Update battery charge/discharge label
        const chargeIndicator = document.getElementById('battery-charge-status');
        if (status.current_mode === 'work') {
            chargeIndicator.textContent = '❌ discharging';
            chargeIndicator.style.color = '#ef4444';
        } else if (isCharging) {
            chargeIndicator.textContent = '⚡ charging';
            chargeIndicator.style.color = 'var(--recharge-color)';
        } else {
            chargeIndicator.textContent = '⏳ holding';
            chargeIndicator.style.color = 'var(--text-secondary)';
        }

        // Trigger dynamic liquid battery bubbles
        updateBatteryBubbles(isCharging);

        // Update session duration statistics
        const formatDuration = (seconds) => {
            const h = Math.floor(seconds / 3600);
            const m = Math.floor((seconds % 3600) / 60);
            return `${h}h ${m}m`;
        };
        document.getElementById('stat-work-time').textContent = formatDuration(status.today_work_seconds);
        document.getElementById('stat-recharge-time').textContent = formatDuration(status.today_recharge_seconds);
        document.getElementById('stat-rest-time').textContent = formatDuration(status.today_rest_seconds);
        
        // Change battery status message color and direct advice based on level
        if (energyLevel === 1) {
            if (batteryFill) {
                batteryFill.style.backgroundColor = '#ef4444';
                batteryFill.style.boxShadow = '0 0 15px rgba(239, 68, 68, 0.4)';
            }
            batteryStatusMsg.textContent = 'CRITICAL ENERGY: Rest more. Stop coding immediately, step away from your screen, stretch your body, and drink water!';
            batteryStatusMsg.style.color = '#ef4444';
        } else if (energyLevel === 2) {
            if (batteryFill) {
                batteryFill.style.backgroundColor = '#ef4444';
                batteryFill.style.boxShadow = '0 0 15px rgba(239, 68, 68, 0.4)';
            }
            batteryStatusMsg.textContent = 'LOW ENERGY: Rest more. Wind down your current task, start Zen Space, and relax your eyes in Forest Light.';
            batteryStatusMsg.style.color = '#ef4444';
        } else if (energyLevel === 3) {
            if (batteryFill) {
                batteryFill.style.backgroundColor = '#f59e0b';
                batteryFill.style.boxShadow = '0 0 15px rgba(245, 158, 11, 0.4)';
            }
            batteryStatusMsg.textContent = 'MODERATE ENERGY: Pace yourself. Take a 2-minute break, stand up, take a deep breath, and rest more before continuing.';
            batteryStatusMsg.style.color = '#f59e0b';
        } else if (energyLevel === 4) {
            if (batteryFill) {
                batteryFill.style.backgroundColor = '#10b981';
                batteryFill.style.boxShadow = '0 0 15px rgba(16, 185, 129, 0.4)';
            }
            batteryStatusMsg.textContent = 'GOOD ENERGY: Steady flow. Keep up the good work, but schedule a short physical break to rest more and protect your battery.';
            batteryStatusMsg.style.color = 'var(--text-secondary)';
        } else {
            if (batteryFill) {
                batteryFill.style.backgroundColor = '#10b981';
                batteryFill.style.boxShadow = '0 0 15px rgba(16, 185, 129, 0.4)';
            }
            batteryStatusMsg.textContent = 'FULLY CHARGED: High energy! Safe for deep focus, but remember to stand up, stretch, and rest more at regular intervals.';
            batteryStatusMsg.style.color = 'var(--text-secondary)';
        }

        // Update battery forecast message
        const forecastMsg = document.getElementById('battery-forecast-msg');
        if (forecastMsg) {
            if (status.forecast_message) {
                forecastMsg.textContent = status.forecast_message;
                forecastMsg.style.display = 'block';
            } else {
                forecastMsg.style.display = 'none';
            }
        }
        
        // 6. Companion Companion State Toggle Status
        if (status.tracking_active) {
            trackingPulse.style.backgroundColor = 'var(--recharge-color)';
            trackingPulse.style.boxShadow = '0 0 8px var(--recharge-color)';
            trackingStatusText.textContent = "Shield Active";
            toggleShieldBtn.textContent = "Pause Companion";
            toggleShieldBtn.style.color = 'var(--text-primary)';
            toggleShieldBtn.style.background = 'rgba(255, 255, 255, 0.06)';
        } else {
            trackingPulse.style.backgroundColor = '#ef4444';
            trackingPulse.style.boxShadow = '0 0 8px #ef4444';
            trackingStatusText.textContent = "Shield Paused";
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

        
        // 7.8 Periodically reload analytics every 30 seconds on active tabs
        const now = Date.now();
        if ((currentTab === 'dashboard' || currentTab === 'analytics') && (now - lastAnalyticsLoadTime >= 30000)) {
            loadAnalytics();
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
        showToast(status.tracking_active ? "Cognitive Shield Activated" : "Cognitive Shield Deactivated");
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
            
            // Dynamically scale particles in Zen Canvas if open
            if (zenCanvas) {
                resetZenParticles();
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
        summary: summaryInput.value,
        mood: selectedMood
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
            
            // Reset selected mood
            selectedMood = 'Neutral';
            document.querySelectorAll('#mood-rating .rate-btn').forEach(btn => {
                if (btn.getAttribute('data-val') === 'Neutral') {
                    btn.classList.add('active');
                } else {
                    btn.classList.remove('active');
                }
            });
            
            pollStatus(); // Immediately update battery meter
        } else {
            showToast("Failed to save reflection", true);
        }
    } catch (err) {
        showToast("Network error submitting reflection", true);
    }
    lastSubmitClick = null;
});

// Dynamic Reflection Submission Particle Burst (Remade Optimized Splash Effect)
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
    
    // 1. Create a Ripple effect at the click location (glowing ring)
    const colors = {
        water: ['#38bdf8', '#0284c7', '#7dd3fc'],
        sub: ['#f43f5e', '#be123c', '#fda4af'],
        default: ['#a78bfa', '#7c3aed', '#c084fc'],
        recharge: ['#2dd4a8', '#059669', '#34d399'],
        rest: ['#fbbf24', '#d97706', '#fcd34d']
    };
    
    let activePalette = colors.default;
    let isWater = false;
    
    if (customColor === '#38bdf8') {
        activePalette = colors.water;
        isWater = true;
    } else if (customColor === '#f43f5e') {
        activePalette = colors.sub;
        isWater = true;
    } else if (customColor === '#10b981') {
        activePalette = colors.recharge;
        isWater = true;
    } else if (customColor) {
        activePalette = [customColor];
    } else {
        const bodyEl = document.body;
        if (bodyEl.classList.contains('mode-recharge')) activePalette = colors.recharge;
        else if (bodyEl.classList.contains('mode-rest')) activePalette = colors.rest;
    }
    
    // Spawn 1 expanding wave ring (optimized)
    const wave = document.createElement('div');
    wave.className = 'click-ripple-ring';
    wave.style.left = `${x}px`;
    wave.style.top = `${y}px`;
    wave.style.color = activePalette[0];
    wave.style.borderColor = 'currentColor';
    wave.style.boxShadow = `0 0 8px ${activePalette[0]}`;
    container.appendChild(wave);
    setTimeout(() => wave.remove(), 500);
    
    // 2. Spawn Splash Particles (Optimized count: 10 for water, 12 for default)
    const particleCount = isWater ? 10 : 12;
    for (let i = 0; i < particleCount; i++) {
        const particle = document.createElement('div');
        particle.className = 'burst-particle';
        
        // Randomize sizes
        const size = Math.random() * (isWater ? 5 : 6) + (isWater ? 2.5 : 3);
        particle.style.width = `${size}px`;
        particle.style.height = `${size}px`;
        
        // Pick a color from active palette
        const color = activePalette[Math.floor(Math.random() * activePalette.length)];
        particle.style.backgroundColor = color;
        particle.style.color = color;
        
        // Position at absolute 0,0 and translate using transform to prevent layout recalculations
        particle.style.left = '0px';
        particle.style.top = '0px';
        
        if (isWater) {
            particle.style.borderRadius = '0 50% 50% 50%';
        } else {
            particle.style.borderRadius = Math.random() > 0.4 ? '50%' : '2px';
        }
        
        // Physics variables
        const angle = Math.random() * Math.PI * 2;
        const velocity = Math.random() * 6 + (isWater ? 3 : 4);
        let vx = Math.cos(angle) * velocity;
        let vy = Math.sin(angle) * velocity - (isWater ? 2.5 : 1);
        
        container.appendChild(particle);
        
        let posX = x;
        let posY = y;
        let opacity = 1;
        let rotation = Math.random() * 360;
        const spinSpeed = (Math.random() - 0.5) * 8;
        
        const updateParticle = () => {
            posX += vx;
            posY += vy;
            vy += isWater ? 0.3 : 0.2; // gravity
            vx *= 0.95; // drag
            opacity -= isWater ? 0.03 : 0.022; // fade
            rotation += spinSpeed;
            
            // Motion blur / stretch effect
            const speed = Math.sqrt(vx * vx + vy * vy);
            const stretch = 1 + speed * 0.08;
            
            particle.style.opacity = opacity;
            
            if (isWater) {
                const travelAngle = Math.atan2(vy, vx) * 180 / Math.PI;
                particle.style.transform = `translate3d(${posX}px, ${posY}px, 0) rotate(${travelAngle + 45}deg) scale(${stretch}, ${2 - stretch / 2})`;
            } else {
                particle.style.transform = `translate3d(${posX}px, ${posY}px, 0) rotate(${rotation}deg) scale(${stretch}, 1)`;
            }
            
            if (opacity > 0) {
                requestAnimationFrame(updateParticle);
            } else {
                particle.remove();
            }
        };
        
        requestAnimationFrame(updateParticle);
    }
}

// Coalesce/Smooth rapid window-switching sessions on Focus Timeline to prevent a fragmented/messy barcode look
function smoothSessions(sessions) {
    if (!sessions || sessions.length === 0) return [];
    
    // 1. Map to raw times and sort chronologically
    let list = [...sessions]
        .map(s => ({
            ...s,
            startMs: parseLocalDate(s.start).getTime(),
            endMs: parseLocalDate(s.end).getTime()
        }))
        .sort((a, b) => a.startMs - b.startMs);
        
    // 2. Pass 1: Merge consecutive segments of the EXACT SAME mode separated by < 60s
    let pass1 = [];
    list.forEach(s => {
        if (pass1.length === 0) {
            pass1.push(s);
            return;
        }
        let last = pass1[pass1.length - 1];
        if (last.mode === s.mode && (s.startMs - last.endMs) < 60000) {
            last.endMs = Math.max(last.endMs, s.endMs);
            const endDt = new Date(last.endMs);
            const pad = (num, size = 2) => ('000' + num).slice(-size);
            last.end = `${endDt.getFullYear()}-${pad(endDt.getMonth() + 1)}-${pad(endDt.getDate())}T${pad(endDt.getHours())}:${pad(endDt.getMinutes())}:${pad(endDt.getSeconds())}.${pad(endDt.getMilliseconds(), 3)}`;
            last.duration = (last.endMs - last.startMs) / 1000;
            if (s.brain_dump) {
                last.brain_dump = last.brain_dump ? `${last.brain_dump} | ${s.brain_dump}` : s.brain_dump;
            }
            last.bypassed = last.bypassed || s.bypassed;
        } else {
            pass1.push(s);
        }
    });
    
    // 3. Pass 2: Absorb micro-neutral/idle gaps (< 60s) sandwiched between the same modes (e.g. Work -> Neutral -> Work)
    let pass2 = [];
    for (let i = 0; i < pass1.length; i++) {
        let s = pass1[i];
        if (s.mode === 'neutral' && s.duration < 60 && i > 0 && i < pass1.length - 1) {
            let prev = pass2[pass2.length - 1];
            let next = pass1[i + 1];
            if (prev.mode === next.mode && (s.startMs - prev.endMs) < 60000 && (next.startMs - s.endMs) < 60000) {
                // Merge everything into prev
                prev.endMs = next.endMs;
                prev.end = next.end;
                prev.duration = (prev.endMs - prev.startMs) / 1000;
                if (s.brain_dump) {
                    prev.brain_dump = prev.brain_dump ? `${prev.brain_dump} | ${s.brain_dump}` : s.brain_dump;
                }
                if (next.brain_dump) {
                    prev.brain_dump = prev.brain_dump ? `${prev.brain_dump} | ${next.brain_dump}` : next.brain_dump;
                }
                prev.bypassed = prev.bypassed || s.bypassed || next.bypassed;
                i++; // skip next as it is absorbed
                continue;
            }
        }
        pass2.push(s);
    }
    
    // 4. Pass 3: Discard leftover transient neutral micro-ticks (< 15 seconds) to clean up noise
    let pass3 = [];
    pass2.forEach(s => {
        if (s.mode === 'neutral' && s.duration < 15 && !s.brain_dump && !s.bypassed) {
            return;
        }
        pass3.push(s);
    });
    
    return pass3;
}

// Load Analytics & Draw SVG Line Chart
async function loadAnalytics() {
    try {
        lastAnalyticsLoadTime = Date.now();
        const res = await fetch(`/api/analytics?week_offset=${weekOffset}`);
        const data = await res.json();
        hideSkeletons();
        
        // Update week navigation UI
        const weekLabel = document.getElementById('current-week-label');
        if (weekLabel && data.week_label) {
            weekLabel.textContent = data.week_label;
            weekLabel.title = data.week_label;
        }
        const nextBtn = document.getElementById('next-week-btn');
        if (nextBtn) {
            nextBtn.disabled = (weekOffset === 0);
            nextBtn.style.opacity = (weekOffset === 0) ? '0.4' : '1.0';
        }
        const prevBtn = document.getElementById('prev-week-btn');
        if (prevBtn) {
            prevBtn.disabled = (weekOffset >= 12);
            prevBtn.style.opacity = (weekOffset >= 12) ? '0.4' : '1.0';
        }

        // Force weekly filter for earlier weeks
        const btnToday = document.getElementById('app-filter-today');
        if (weekOffset > 0) {
            appStatsFilter = 'weekly';
            const btnWeekly = document.getElementById('app-filter-weekly');
            if (btnWeekly) btnWeekly.classList.add('active');
            if (btnToday) {
                btnToday.classList.remove('active');
                btnToday.disabled = true;
                btnToday.style.opacity = '0.4';
                btnToday.style.pointerEvents = 'none';
            }
        } else {
            if (btnToday) {
                btnToday.disabled = false;
                btnToday.style.opacity = '1.0';
                btnToday.style.pointerEvents = 'auto';
            }
        }
        
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
        
        // 1.5. Render Flow Triggers and Cognitive Leaks Analyser
        const flowTriggersList = document.getElementById('flow-triggers-list');
        const cognitiveLeaksList = document.getElementById('cognitive-leaks-list');
        
        if (flowTriggersList && cognitiveLeaksList) {
            flowTriggersList.innerHTML = '';
            cognitiveLeaksList.innerHTML = '';
            
            const flowKeywords = new Set();
            const leakKeywords = new Set();
            
            const reflections = data.reflections || [];
            const stopWords = new Set(['and', 'the', 'for', 'with', 'this', 'that', 'from', 'your', 'continuous', 'focus', 'tracking', 'companion', 'active', 'recovery']);
            
            reflections.forEach(r => {
                const summary = (r.summary || '').toLowerCase();
                const energy = r.energy_level;
                const friction = r.friction_level;
                
                const terms = summary.match(/[a-zA-Z0-9'#+.-]+/g) || [];
                terms.forEach(term => {
                    if (term.length > 3 && !stopWords.has(term)) {
                        if (energy >= 4 && friction <= 2) {
                            flowKeywords.add(term);
                        } else if (friction >= 4 || energy <= 2) {
                            leakKeywords.add(term);
                        }
                    }
                });
            });
            
            const appUsage = data.app_usage || [];
            const workApps = [];
            const distractApps = [];
            
            appUsage.forEach(app => {
                if (app.category === 'work') {
                    workApps.push({ name: app.process, dur: app.duration });
                } else if (app.category === 'recharge' || app.category === 'neutral') {
                    distractApps.push({ name: app.process, dur: app.duration });
                }
            });
            
            workApps.sort((a, b) => b.dur - a.dur);
            distractApps.sort((a, b) => b.dur - a.dur);
            
            const topWork = workApps.slice(0, 3).map(a => a.name);
            const topDistract = distractApps.slice(0, 3).map(a => a.name);
            
            const triggers = new Set([...topWork, ...Array.from(flowKeywords).slice(0, 4)]);
            const leaks = new Set([...topDistract, ...Array.from(leakKeywords).slice(0, 4)]);
            
            const capitalize = s => s.charAt(0).toUpperCase() + s.slice(1);
            
            if (triggers.size === 0) {
                triggers.add('Deep Focus');
                triggers.add('Clean Code');
            }
            if (leaks.size === 0) {
                leaks.add('Multi-tasking');
                leaks.add('Context Switching');
            }
            
            triggers.forEach(t => {
                const pill = document.createElement('span');
                pill.style.background = 'rgba(45, 212, 168, 0.08)';
                pill.style.border = '1px solid rgba(45, 212, 168, 0.25)';
                pill.style.color = '#2dd4a8';
                pill.style.fontSize = '0.72rem';
                pill.style.padding = '0.25rem 0.5rem';
                pill.style.borderRadius = '6px';
                pill.style.fontWeight = '600';
                pill.style.display = 'inline-block';
                pill.textContent = capitalize(t);
                flowTriggersList.appendChild(pill);
            });
            
            leaks.forEach(l => {
                const pill = document.createElement('span');
                pill.style.background = 'rgba(239, 68, 68, 0.08)';
                pill.style.border = '1px solid rgba(239, 68, 68, 0.25)';
                pill.style.color = '#ef4444';
                pill.style.fontSize = '0.72rem';
                pill.style.padding = '0.25rem 0.5rem';
                pill.style.borderRadius = '6px';
                pill.style.fontWeight = '600';
                pill.style.display = 'inline-block';
                pill.textContent = capitalize(l);
                cognitiveLeaksList.appendChild(pill);
            });
        }
        
        // 1.8. Render Mood Distribution Card
        const moodDistList = document.getElementById('mood-distribution-list');
        if (moodDistList) {
            moodDistList.innerHTML = '';
            const moodCounts = data.mood_counts || {};
            const totalMoods = Object.values(moodCounts).reduce((a, b) => a + b, 0);
            
            if (totalMoods === 0) {
                moodDistList.innerHTML = `<div style="text-align: center; padding: 1.5rem 0; color: var(--text-muted); font-size: 0.8rem;">No mood data logged this week. Fill some check-ins above!</div>`;
            } else {
                const moodEmojis = {
                    Calm: '😌', Focused: '🎯', Neutral: '😐',
                    Anxious: '😟', Overwhelmed: '🤯', Frustrated: '😤', Exhausted: '😴'
                };
                const moodColors = {
                    Calm: '#10b981', Focused: '#3b82f6', Neutral: '#9ca3af',
                    Anxious: '#fbbf24', Overwhelmed: '#c084fc', Frustrated: '#ef4444', Exhausted: '#6b7280'
                };
                
                Object.entries(moodCounts).forEach(([mood, count]) => {
                    if (count > 0) {
                        const pct = Math.round((count / totalMoods) * 100);
                        const emoji = moodEmojis[mood] || '🌿';
                        const color = moodColors[mood] || '#a78bfa';
                        
                        const row = document.createElement('div');
                        row.style.display = 'flex';
                        row.style.flexDirection = 'column';
                        row.style.gap = '0.25rem';
                        row.style.marginBottom = '0.5rem';
                        row.innerHTML = `
                            <div style="display: flex; justify-content: space-between; font-size: 0.75rem; font-weight: 500;">
                                <span style="display: flex; align-items: center; gap: 0.25rem;">
                                    <span>${emoji}</span>
                                    <span>${mood}</span>
                                </span>
                                <span style="color: var(--text-secondary); font-weight: 600;">${count} (${pct}%)</span>
                            </div>
                            <div style="width: 100%; height: 6px; background: rgba(255,255,255,0.03); border-radius: 3px; overflow: hidden; border: 1px solid rgba(255,255,255,0.05);">
                                <div style="width: ${pct}%; height: 100%; background: ${color}; border-radius: 3px; box-shadow: 0 0 8px ${color}80; transition: width 0.5s ease-out;"></div>
                            </div>
                        `;
                        moodDistList.appendChild(row);
                    }
                });
                
                if (moodDistList.children.length === 0) {
                    moodDistList.innerHTML = `<div style="text-align: center; padding: 1.5rem 0; color: var(--text-muted); font-size: 0.8rem;">No mood data logged this week. Fill some check-ins above!</div>`;
                }
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
                
                const dt = parseLocalDate(ref.timestamp);
                const dateStr = dt.toLocaleDateString() + ' ' + dt.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                
                let energyBadge = `<span class="rating-badge badge-green">${ref.energy_level} / 5</span>`;
                if (ref.energy_level <= 2) energyBadge = `<span class="rating-badge badge-red">${ref.energy_level} / 5</span>`;
                
                let frictionBadge = `<span class="rating-badge badge-purple">${ref.friction_level} / 5</span>`;
                if (ref.friction_level >= 4) frictionBadge = `<span class="rating-badge badge-red">${ref.friction_level} / 5</span>`;
                
                let summaryText = ref.summary || '';
                let isAutopilot = false;
                if (summaryText.startsWith('[Autopilot]')) {
                    isAutopilot = true;
                    summaryText = summaryText.replace('[Autopilot]', '').trim();
                }
                
                let moodHtml = '';
                if (ref.mood) {
                    const moodEmojis = {
                        Calm: '😌', Focused: '🎯', Neutral: '😐',
                        Anxious: '😟', Overwhelmed: '🤯', Frustrated: '😤', Exhausted: '😴'
                    };
                    const emoji = moodEmojis[ref.mood] || '🌿';
                    moodHtml = `<span class="mood-badge" style="background: rgba(56, 189, 248, 0.12); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.25); padding: 0.15rem 0.4rem; border-radius: 6px; font-size: 0.72rem; font-weight: 600; display: inline-flex; align-items: center; gap: 0.25rem; margin-right: 0.5rem; font-family: sans-serif;" title="Logged Mood: ${ref.mood}">${emoji} ${ref.mood}</span>`;
                }
                
                let summaryHtml = escapeHtml(summaryText);
                if (isAutopilot) {
                    summaryHtml = `<span class="autopilot-badge" style="background: rgba(167, 139, 250, 0.12); color: #a78bfa; border: 1px solid rgba(167, 139, 250, 0.25); padding: 0.15rem 0.4rem; border-radius: 6px; font-size: 0.72rem; font-weight: 600; display: inline-flex; align-items: center; gap: 0.25rem; margin-right: 0.5rem; font-family: sans-serif;" title="Logged automatically by Autopilot">🤖 Autopilot</span>${moodHtml}<code>${summaryHtml}</code>`;
                } else {
                    summaryHtml = `${moodHtml}<code>${summaryHtml}</code>`;
                }
                
                tr.innerHTML = `
                    <td>${escapeHtml(dateStr)}</td>
                    <td>${energyBadge}</td>
                    <td>${frictionBadge}</td>
                    <td>${summaryHtml}</td>
                `;
                tableBody.appendChild(tr);
            });
        }
        
        // 2.5. Render Today's Focus Timeline Widget
        const rawSessions = data.today_sessions || [];
        const todaySessions = smoothSessions(rawSessions);
        const timelineTrack = document.getElementById('timeline-track');
        const timelineAxis = document.getElementById('timeline-axis');
        const timelineEvents = document.getElementById('timeline-events-list');
        const timelinePill = document.getElementById('timeline-summary-pill');
        
        if (timelineTrack && timelineAxis && timelineEvents && timelinePill) {
            timelineTrack.innerHTML = '';
            timelineAxis.innerHTML = '';
            timelineEvents.innerHTML = '';
            
            const totalDuration = todaySessions.reduce((sum, s) => sum + s.duration, 0);
            const totalTrackedMin = Math.round(totalDuration / 60);
            const trackedH = Math.floor(totalTrackedMin / 60);
            const trackedM = totalTrackedMin % 60;
            timelinePill.textContent = `${trackedH}h ${trackedM}m total track`;
            
            if (todaySessions.length === 0) {
                timelineTrack.innerHTML = `<div class="timeline-segment neutral-seg" style="width: 100%; top: 4px; height: 14px; line-height: 12px; font-size: 0.7rem; text-align: center; color: var(--text-muted); cursor: default; box-shadow: none;" data-tooltip="No sessions tracked yet today.">No sessions tracked yet today.</div>`;
                timelineEvents.innerHTML = `<div style="text-align: center; color: var(--text-muted); font-size: 0.85rem; padding: 1.25rem 0;">No focus sessions or breaks logged yet today.</div>`;
            } else {
                // Find chronological bounds
                let minStart = Infinity;
                let maxEnd = -Infinity;
                todaySessions.forEach(s => {
                    const startMs = s.startMs || parseLocalDate(s.start).getTime();
                    const endMs = s.endMs || parseLocalDate(s.end).getTime();
                    if (startMs < minStart) minStart = startMs;
                    if (endMs > maxEnd) maxEnd = endMs;
                });
                
                // Add some padding (e.g. 30 minutes on each side)
                const paddingMs = 30 * 60 * 1000;
                let startBound = minStart - paddingMs;
                let endBound = maxEnd + paddingMs;
                
                // Keep a minimum range of 4 hours
                if (endBound - startBound < 4 * 60 * 60 * 1000) {
                    endBound = startBound + 4 * 60 * 60 * 1000;
                }
                
                const totalRangeMs = endBound - startBound;
                
                // Populate progress track segments
                todaySessions.forEach((session, index) => {
                    const sessionStartMs = session.startMs || parseLocalDate(session.start).getTime();
                    const sessionEndMs = session.endMs || parseLocalDate(session.end).getTime();
                    
                    const leftPct = ((sessionStartMs - startBound) / totalRangeMs) * 100;
                    let widthPct = ((sessionEndMs - sessionStartMs) / totalRangeMs) * 100;
                    
                    if (widthPct <= 0) return;
                    widthPct = Math.max(widthPct, 0.75);
                    
                    const seg = document.createElement('div');
                    let modeClass = 'neutral-seg';
                    if (session.mode === 'work') modeClass = 'work-seg';
                    else if (session.mode === 'recharge') modeClass = 'recharge-seg';
                    else if (session.mode === 'rest') modeClass = 'rest-seg';
                    
                    seg.className = `timeline-segment ${modeClass} timeline-seg-index-${index}`;
                    seg.style.left = `${leftPct}%`;
                    seg.style.width = `${widthPct}%`;
                    
                    const startDt = parseLocalDate(session.start);
                    const endDt = parseLocalDate(session.end);
                    const startTimeStr = startDt.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                    const endTimeStr = endDt.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                    
                    const durationSec = Math.round(session.duration);
                    const durationText = durationSec < 60 ? `${durationSec} sec` : `${Math.round(durationSec / 60)} min`;
                    
                    const tooltipText = `${session.mode.toUpperCase()}: ${startTimeStr} - ${endTimeStr} (${durationText})`;
                    seg.setAttribute('data-tooltip', tooltipText);
                    
                    // Attach dataset properties for shared tooltip styling
                    seg.dataset.leftPct = leftPct;
                    seg.dataset.widthPct = widthPct;
                    seg.dataset.startTime = startTimeStr;
                    seg.dataset.endTime = endTimeStr;
                    seg.dataset.duration = durationText;
                    seg.dataset.mode = session.mode;
                    seg.dataset.brainDump = session.brain_dump || '';
                    
                    // Link hover effects (track seg -> list card) and tooltip
                    seg.addEventListener('mouseenter', () => {
                        const eventItem = timelineEvents.querySelector(`.timeline-event-index-${index}`);
                        if (eventItem) {
                            eventItem.classList.add('highlighted');
                            eventItem.scrollIntoView({ behavior: 'auto', block: 'nearest' });
                        }
                        showTooltipForSegment(seg);
                    });
                    seg.addEventListener('mouseleave', () => {
                        const eventItem = timelineEvents.querySelector(`.timeline-event-index-${index}`);
                        if (eventItem) eventItem.classList.remove('highlighted');
                        hideTooltip();
                    });
                    
                    timelineTrack.appendChild(seg);
                });
                
                // Draw hour ticks on timeline axis
                const startHourDate = new Date(startBound);
                startHourDate.setMinutes(0, 0, 0);
                startHourDate.setHours(startHourDate.getHours() + 1); // Move to next whole hour
                
                let currentTick = startHourDate.getTime();
                while (currentTick < endBound) {
                    const pct = ((currentTick - startBound) / totalRangeMs) * 100;
                    if (pct >= 1.5 && pct <= 98.5) {
                        const tickDate = new Date(currentTick);
                        const label = tickDate.toLocaleTimeString([], { hour: 'numeric', hour12: true });
                        
                        const tickEl = document.createElement('div');
                        tickEl.className = 'timeline-tick';
                        tickEl.style.left = `${pct}%`;
                        tickEl.innerHTML = `
                            <span class="tick-line"></span>
                            <span class="tick-label">${label}</span>
                        `;
                        timelineAxis.appendChild(tickEl);
                    }
                    currentTick += 60 * 60 * 1000; // Next hour
                }
                
                // Populate event list (sorted newest first)
                const sortedTodaySessions = [...todaySessions].sort((a, b) => parseLocalDate(b.start) - parseLocalDate(a.start));
                sortedTodaySessions.forEach(session => {
                    // Find original index to link correctly
                    const originalIndex = todaySessions.indexOf(session);
                    
                    const item = document.createElement('div');
                    let modeClass = 'neutral-item';
                    if (session.mode === 'work') modeClass = 'work-item';
                    else if (session.mode === 'recharge') modeClass = 'recharge-item';
                    else if (session.mode === 'rest') modeClass = 'rest-item';
                    
                    item.className = `timeline-event-item ${modeClass} timeline-event-index-${originalIndex}`;
                    
                    const startDt = parseLocalDate(session.start);
                    const endDt = parseLocalDate(session.end);
                    const startTimeStr = startDt.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                    const endTimeStr = endDt.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                    const timeStr = `${startTimeStr} - ${endTimeStr}`;
                    
                    let badgeClass = 'neutral-badge';
                    if (session.mode === 'work') badgeClass = 'work-badge';
                    else if (session.mode === 'recharge') badgeClass = 'recharge-badge';
                    else if (session.mode === 'rest') badgeClass = 'rest-badge';
                    
                    const durationSec = Math.round(session.duration);
                    const durationText = durationSec < 60 ? `${durationSec}s` : `${Math.round(durationSec / 60)} min`;
                    let modeName = session.mode;
                    if (modeName === 'work') modeName = 'focus';
                    
                    let summaryHtml = `<strong style="color: var(--text-primary); font-weight: 600;">${durationText}</strong> of <span class="mode-name" style="text-transform: capitalize; font-weight: 500;">${modeName}</span>`;
                    if (session.bypassed) {
                        summaryHtml += ` <span style="font-size: 0.72rem; color: #f87171; font-weight: 600; background: rgba(248, 113, 113, 0.1); border: 1px solid rgba(248, 113, 113, 0.2); padding: 0.1rem 0.35rem; border-radius: 4px; margin-left: 0.4rem; display: inline-flex; align-items: center; gap: 0.15rem;" title="Eye care breaks were bypassed">⚠️ Bypassed</span>`;
                    }
                    if (session.brain_dump) {
                        summaryHtml += ` <span class="brain-dump-text" style="color: var(--text-muted); font-size: 0.76rem; font-style: italic; display: block; margin-top: 0.3rem; opacity: 0.85; border-left: 2px solid rgba(255,255,255,0.08); padding-left: 0.5rem; line-height: 1.4;">"${escapeHtml(session.brain_dump)}"</span>`;
                    }
                    
                    item.innerHTML = `
                        <span class="event-time">${escapeHtml(timeStr)}</span>
                        <span class="event-badge ${escapeHtml(badgeClass)}">${escapeHtml(session.mode)}</span>
                        <span class="event-summary">${summaryHtml}</span>
                    `;
                    
                    // Link hover effects (list card -> track seg)
                    item.addEventListener('mouseenter', () => {
                        const trackSeg = timelineTrack.querySelector(`.timeline-seg-index-${originalIndex}`);
                        if (trackSeg) {
                            trackSeg.classList.add('highlighted');
                            showTooltipForSegment(trackSeg);
                        }
                    });
                    item.addEventListener('mouseleave', () => {
                        const trackSeg = timelineTrack.querySelector(`.timeline-seg-index-${originalIndex}`);
                        if (trackSeg) {
                            trackSeg.classList.remove('highlighted');
                            hideTooltip();
                        }
                    });
                    
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
    let totalAppsDuration = 0;
    
    filteredData.forEach(item => {
        workDuration += item.work_duration;
        rechargeDuration += item.recharge_duration;
        neutralDuration += item.neutral_duration;
        totalAppsDuration += item.duration;
    });
    
    const totalDuration = workDuration + rechargeDuration + neutralDuration;
    
    // Render Category Ratio Bar
    const ratioContainer = document.getElementById('app-ratio-bar-container');
    if (totalDuration > 0 && ratioContainer) {
        ratioContainer.style.display = 'block';
        let workPct = Math.round((workDuration / totalDuration) * 100);
        let rechargePct = Math.round((rechargeDuration / totalDuration) * 100);
        let neutralPct = Math.round((neutralDuration / totalDuration) * 100);
        
        // Ensure they sum to exactly 100% to prevent bar overflow/wrapping
        const sumPct = workPct + rechargePct + neutralPct;
        if (sumPct !== 100 && sumPct > 0) {
            const diff = 100 - sumPct;
            // Adjust the largest non-zero value
            const values = [
                { name: 'work', val: workPct },
                { name: 'recharge', val: rechargePct },
                { name: 'neutral', val: neutralPct }
            ];
            values.sort((a, b) => b.val - a.val);
            if (values[0].val > 0) {
                values[0].val += diff;
            }
            values.forEach(v => {
                if (v.name === 'work') workPct = v.val;
                if (v.name === 'recharge') rechargePct = v.val;
                if (v.name === 'neutral') neutralPct = v.val;
            });
        }
        
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
        const pct = Math.min(totalAppsDuration > 0 ? (item.duration / totalAppsDuration) * 100 : 0, 100);
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
                const dt = parseLocalDate(ref.timestamp);
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

// Page Visibility API throttling to save CPU/GPU when minimized/backgrounded
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        document.body.classList.add('page-hidden');
        // App is minimized or backgrounded: slow down status poll and stop rendering
        if (statusInterval) {
            clearInterval(statusInterval);
            statusInterval = setInterval(pollStatus, 5000);
        }
        stopZenCanvas();
        clearDashboardIntervals();
    } else {
        document.body.classList.remove('page-hidden');
        // App returned to foreground: restore normal status polling speed
        if (statusInterval) {
            clearInterval(statusInterval);
            statusInterval = setInterval(pollStatus, 1000);
        }
        pollStatus();
        
        // Restore Zen Visualizer if currently on the Zen Space tab
        const zenTab = document.getElementById('tab-zen');
        if (zenTab && zenTab.classList.contains('active')) {
            initZenCanvas();
        }
        
        // Restore Dashboard visual elements if on dashboard tab
        const dashboardTab = document.getElementById('tab-dashboard');
        if (dashboardTab && dashboardTab.classList.contains('active')) {
            restoreDashboardIntervals();
        }
    }
});

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
let isIndicatorTicking = false;
window.addEventListener('resize', () => {
    if (!isIndicatorTicking) {
        window.requestAnimationFrame(() => {
            updateNavIndicator();
            isIndicatorTicking = false;
        });
        isIndicatorTicking = true;
    }
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
    
    // Only start if the dashboard tab is active and document is not hidden
    const dashboardTab = document.getElementById('tab-dashboard');
    const isTabActive = dashboardTab && dashboardTab.classList.contains('active');
    if (document.hidden || !isTabActive) {
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
        let resizerTicking = false;
        
        function onMouseMove(moveEvent) {
            const currentX = moveEvent.clientX;
            // Enforce limits: 200px min, 450px max
            const newWidth = Math.max(200, Math.min(450, startWidth + (currentX - startX)));
            
            if (!resizerTicking) {
                window.requestAnimationFrame(() => {
                    container.style.setProperty('--sidebar-width', `${newWidth}px`);
                    localStorage.setItem('sidebar-width', newWidth);
                    updateNavIndicator();
                    resizerTicking = false;
                });
                resizerTicking = true;
            }
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
    initAppTheme();
    loadGoal();
    loadAnalytics();
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

    // Start idle water dripping simulation
    startIdleDripping();
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
    // SAFETY: Reject zero or NaN deltas to prevent no-op server calls
    const safeDelta = parseFloat(delta);
    if (isNaN(safeDelta) || safeDelta === 0) {
        console.warn("[Hydration] Rejected invalid delta:", delta);
        return;
    }
    try {
        const payload = { delta: safeDelta };
        const bodyStr = JSON.stringify(payload);
        console.log("[Hydration] Sending POST:", bodyStr);
        const res = await fetch('/api/hydration', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: bodyStr
        });
        if (res.ok) {
            const data = await res.json();
            updateHydrationUI(data.hydration);
            if (safeDelta > 0) {
                showToast(`Logged +${safeDelta} water! Stay hydrated. 💧`);
            } else {
                showToast(`Subtracted ${Math.abs(safeDelta)} water. 💧`);
            }
        } else {
            console.error("[Hydration] Server returned non-OK:", res.status);
        }
    } catch(err) {
        console.error("[Hydration] Failed to log delta:", err);
    }
}

function logHydrationQuick(e) {
    // GUARANTEE: Always sends a POSITIVE delta for the add button
    const inc = Math.abs(parseFloat(currentHydrationIncrement) || 1);
    console.log("[Hydration+] Add clicked, sending delta:", inc);
    logHydrationDelta(inc, e);
}

function logHydrationQuickSub(e) {
    // GUARANTEE: Always sends a NEGATIVE delta for the subtract button
    const inc = -Math.abs(parseFloat(currentHydrationIncrement) || 1);
    console.log("[Hydration-] Sub clicked, sending delta:", inc);
    logHydrationDelta(inc, e);
}

// Legacy logHydration for backward compatibility
async function logHydration(index) {
    logHydrationDelta(1);
}

let hydrationBubbleInterval = null;
let lastHydrationPct = null;
let isPouring = false;
let idleDripInterval = null;

function updateHydrationBubbles(hasWater) {
    const container = document.getElementById('hydration-bubbles');
    if (!container) return;
    
    if (!hasWater) {
        if (hydrationBubbleInterval) {
            clearInterval(hydrationBubbleInterval);
            hydrationBubbleInterval = null;
        }
        container.innerHTML = '';
        return;
    }
    
    // Only start if the dashboard tab is active and document is not hidden
    const dashboardTab = document.getElementById('tab-dashboard');
    const isTabActive = dashboardTab && dashboardTab.classList.contains('active');
    if (document.hidden || !isTabActive) {
        if (hydrationBubbleInterval) {
            clearInterval(hydrationBubbleInterval);
            hydrationBubbleInterval = null;
        }
        container.innerHTML = '';
        return;
    }
    
    if (hydrationBubbleInterval) return; // already active
    
    hydrationBubbleInterval = setInterval(() => {
        if (isPouring) return; // skip normal bubbles during active pour
        const bubble = document.createElement('div');
        bubble.className = 'hydration-bubble';
        
        const size = Math.random() * 4 + 2; // 2px to 6px
        bubble.style.width = `${size}px`;
        bubble.style.height = `${size}px`;
        bubble.style.left = `${Math.random() * 85 + 5}%`;
        
        const wobble = (Math.random() - 0.5) * 20; // -10px to 10px drift
        bubble.style.setProperty('--wobble', `${wobble}px`);
        
        const duration = Math.random() * 1.5 + 2.0; // 2.0s to 3.5s
        bubble.style.animation = `hydrationBubbleFloat ${duration}s ease-in forwards`;
        
        container.appendChild(bubble);
        
        setTimeout(() => {
            bubble.remove();
        }, duration * 1000);
    }, 600);
}

function createSplash(surfaceY, container) {
    if (!container) return;
    const count = 3 + Math.floor(Math.random() * 2); // 3 to 4 particles (optimized)
    for (let i = 0; i < count; i++) {
        const drop = document.createElement('div');
        drop.className = 'splash-droplet';
        drop.style.left = `50%`;
        drop.style.top = `${surfaceY}px`;

        // Random horizontal and vertical movements
        const dx = (Math.random() - 0.5) * 20; // -10px to 10px
        const dy = -(Math.random() * 12 + 6);  // -18px to -6px (upwards)
        
        drop.style.setProperty('--dx', `${dx}px`);
        drop.style.setProperty('--dy', `${dy}px`);

        const size = Math.random() * 1.5 + 1.5; // 1.5px to 3px
        drop.style.width = `${size}px`;
        drop.style.height = `${size}px`;

        container.appendChild(drop);
        setTimeout(() => drop.remove(), 400);
    }
}

function createRipple(surfaceY, container) {
    if (!container) return;
    const ripple = document.createElement('div');
    ripple.className = 'surface-ripple';
    ripple.style.top = `${surfaceY}px`;
    container.appendChild(ripple);
    setTimeout(() => ripple.remove(), 500);
}

function spawnPourBubbles(count, container) {
    if (!container) return;
    for (let i = 0; i < count; i++) {
        const bubble = document.createElement('div');
        bubble.className = 'hydration-bubble pour-bubble';
        
        const size = Math.random() * 5 + 2.5; // 2.5px to 7.5px
        bubble.style.width = `${size}px`;
        bubble.style.height = `${size}px`;
        bubble.style.left = `${Math.random() * 80 + 10}%`;
        
        const wobble = (Math.random() - 0.5) * 16;
        bubble.style.setProperty('--wobble', `${wobble}px`);
        
        container.appendChild(bubble);
        setTimeout(() => bubble.remove(), 1200);
    }
}

function playSingleDrip(currentPct, effectsContainer, bubblesContainer) {
    if (!effectsContainer) return;
    const beakerHeight = 104;
    const surfaceY = beakerHeight * (1 - currentPct / 100);

    // Create a dripping droplet that falls from the top rim
    const drip = document.createElement('div');
    drip.className = 'splash-droplet';
    drip.style.left = '50%';
    drip.style.top = '0px';
    drip.style.width = '4px';
    drip.style.height = '6px';
    drip.style.borderRadius = '50% 50% 40% 40%';
    drip.style.transform = 'translateX(-50%)';
    drip.style.transition = 'top 0.3s cubic-bezier(0.55, 0.055, 0.675, 0.19)';
    
    effectsContainer.appendChild(drip);

    // Trigger fall
    setTimeout(() => {
        drip.style.top = `${surfaceY}px`;
        
        // When it hits
        setTimeout(() => {
            drip.remove();
            
            // Create a small splash and ripple
            createSplash(surfaceY, effectsContainer);
            createRipple(surfaceY, effectsContainer);

            // Spawn a few final bubbles
            spawnPourBubbles(2, bubblesContainer);
        }, 300);
    }, 50);
}

function triggerPourAnimation(oldPct, newPct) {
    if (isPouring) return; // prevent overlapping pour animations if clicked rapidly
    isPouring = true;

    const stream = document.getElementById('water-stream');
    const liquidFill = document.getElementById('hydration-liquid-fill');
    const effectsContainer = document.getElementById('beaker-effects-container');
    const bubblesContainer = document.getElementById('hydration-bubbles');

    if (!stream || !liquidFill) {
        isPouring = false;
        return;
    }

    // 1. Calculate the surface level where stream hits the water initially
    const beakerHeight = 104;
    const startSurfaceY = beakerHeight * (1 - oldPct / 100);
    const streamStartHeight = Math.max(0, startSurfaceY);

    // 2. Show and extend the stream
    stream.style.height = '0px';
    stream.classList.add('pouring');
    void stream.offsetWidth; // force reflow
    stream.style.height = `${streamStartHeight}px`;

    // 3. Set timeout for the stream to hit the surface (150ms)
    setTimeout(() => {
        if (!isPouring) return;

        // Start liquid rising animation
        liquidFill.style.height = `${newPct}%`;
        if (newPct === 0) {
            liquidFill.style.opacity = '0';
        } else {
            liquidFill.style.opacity = '1';
        }
        if (newPct >= 100) {
            liquidFill.classList.add('full');
        } else {
            liquidFill.classList.remove('full');
        }

        // Generate splash and ripples at the surface (optimized to 140ms intervals)
        let splashInterval = setInterval(() => {
            if (!isPouring) {
                clearInterval(splashInterval);
                return;
            }
            const currentFillPct = parseFloat(liquidFill.style.height) || oldPct;
            const currentSurfaceY = beakerHeight * (1 - currentFillPct / 100);

            // Dynamically adjust stream height to meet the rising liquid
            stream.style.height = `${Math.max(0, currentSurfaceY)}px`;

            createSplash(currentSurfaceY, effectsContainer);
            createRipple(currentSurfaceY, effectsContainer);
        }, 140);

        // Generate turbulent bubbles rising from the bottom (optimized to 200ms intervals)
        let bubbleInterval = setInterval(() => {
            if (!isPouring) {
                clearInterval(bubbleInterval);
                return;
            }
            spawnPourBubbles(2, bubblesContainer);
        }, 200);

        // Clean up intervals and stream after animation completes
        setTimeout(() => {
            clearInterval(splashInterval);
            clearInterval(bubbleInterval);

            // Fade out the stream
            stream.classList.remove('pouring');
            
            // Let the stream shrink down to 0
            setTimeout(() => {
                stream.style.height = '0px';
                isPouring = false;

                // Play a final single drip after stream stops
                setTimeout(() => {
                    playSingleDrip(newPct, effectsContainer, bubblesContainer);
                }, 200);
            }, 100);
        }, 700);

    }, 150);
}

function startIdleDripping() {
    if (idleDripInterval) clearInterval(idleDripInterval);
    idleDripInterval = setInterval(() => {
        const dashboardTab = document.getElementById('tab-dashboard');
        const isTabActive = dashboardTab && dashboardTab.classList.contains('active');
        if (!document.hidden && isTabActive && lastHydrationPct > 0 && !isPouring) {
            const effectsContainer = document.getElementById('beaker-effects-container');
            const bubblesContainer = document.getElementById('hydration-bubbles');
            
            playSingleDrip(lastHydrationPct, effectsContainer, bubblesContainer);
        }
    }, 15000);
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
        if (lastHydrationPct !== null && pct > lastHydrationPct) {
            // Trigger pour animation (it updates liquidFill styles inside)
            triggerPourAnimation(lastHydrationPct, pct);
        } else {
            // Set fill height immediately
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
            
            if (!isPouring) {
                updateHydrationBubbles(cups > 0);
            }
        }
    }
    
    lastHydrationPct = pct;
    
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
let lastFrameTime = 0;
const MAX_ZEN_PARTICLES = 120;
let zenMouse = { x: null, y: null, active: false };
let zenStartTime = 0;
let zenVisualizerMode = 'cosmic';
let zenBreathingRhythm = 'box';
let zenRipples = [];
let lastBreathPhase = "";
let lightningFlashAlpha = 0;

// Soundscape states
let zenMasterVolume = 0.5;
let zenMasterGain = null;
let zenOscL = null;
let zenOscR = null;
let zenDroneGain = null;
let zenDroneFilter = null;
let zenPadOscs = [];
let zenPadFilter = null;
let zenPadGain = null;
let zenRainSource = null;
let zenRainFilter = null;
let zenRainGain = null;
let zenRainLfo = null;
let zenRainLfoGain = null;
let zenWindSource = null;
let zenWindFilter = null;
let zenWindGain = null;
let zenWindLfo = null;
let zenWindLfoGain = null;
let zenThunderTimer = null;
let thunderActive = false;
let zenChimesTimer = null;
let chimesActive = false;
let activeZenSounds = {
    drone: false,
    rain: false,
    chimes: false
};

// ==========================================
// Ambient Soundscapes Synthesizer (Web Audio API)
// ==========================================
function initAudioCtx() {
    if (!audioCtx) {
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        audioCtx = new AudioContextClass();
    }
    if (audioCtx.state === 'suspended') {
        audioCtx.resume();
    }
}

function getZenMasterGain() {
    initAudioCtx();
    if (!zenMasterGain) {
        zenMasterGain = audioCtx.createGain();
        zenMasterGain.gain.setValueAtTime(zenMasterVolume, audioCtx.currentTime);
        zenMasterGain.connect(audioCtx.destination);
    }
    return zenMasterGain;
}

function getPinkNoiseBuffer() {
    if (pinkNoiseBuffer) return pinkNoiseBuffer;
    initAudioCtx();
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
        data[i] = pink * 0.11;
    }
    pinkNoiseBuffer = buffer;
    return buffer;
}

function toggleSynthSound(soundType) {
    initAudioCtx();
    
    const active = !activeZenSounds[soundType];
    activeZenSounds[soundType] = active;
    
    const btn = document.getElementById(`sound-btn-${soundType}`);
    const statusText = document.getElementById(`status-${soundType}`);
    
    if (active) {
        if (btn) btn.classList.add('active');
        if (statusText) statusText.textContent = "Playing";
        
        if (soundType === 'drone') {
            startDrone();
        } else if (soundType === 'rain') {
            startRain();
        } else if (soundType === 'chimes') {
            startChimes();
        }
    } else {
        if (btn) btn.classList.remove('active');
        if (statusText) statusText.textContent = "Muted";
        
        if (soundType === 'drone') {
            stopDrone();
        } else if (soundType === 'rain') {
            stopRain();
        } else if (soundType === 'chimes') {
            stopChimes();
        }
    }
    
    checkSoundPlayingState();
}

function checkSoundPlayingState() {
    const eq = document.getElementById('soundscape-eq');
    if (eq) {
        const anyPlaying = activeZenSounds['drone'] || activeZenSounds['rain'] || activeZenSounds['chimes'];
        if (anyPlaying) {
            eq.classList.add('playing');
        } else {
            eq.classList.remove('playing');
        }
    }
}

function updateMasterVolume(val) {
    zenMasterVolume = parseFloat(val) / 100;
    
    const label = document.getElementById('master-volume-label');
    if (label) label.textContent = `${val}%`;
    
    if (zenMasterGain) {
        zenMasterGain.gain.setValueAtTime(zenMasterVolume, audioCtx ? audioCtx.currentTime : 0);
    }
}

function startDrone() {
    initAudioCtx();
    
    zenOscL = audioCtx.createOscillator();
    zenOscR = audioCtx.createOscillator();
    zenDroneGain = audioCtx.createGain();
    zenDroneFilter = audioCtx.createBiquadFilter();
    
    const merger = audioCtx.createChannelMerger(2);
    
    zenOscL.type = 'sine';
    zenOscL.frequency.setValueAtTime(150, audioCtx.currentTime);
    
    zenOscR.type = 'sine';
    zenOscR.frequency.setValueAtTime(160, audioCtx.currentTime);
    
    zenDroneFilter.type = 'lowpass';
    zenDroneFilter.frequency.setValueAtTime(120, audioCtx.currentTime);
    zenDroneFilter.Q.setValueAtTime(1, audioCtx.currentTime);
    
    zenDroneGain.gain.setValueAtTime(0, audioCtx.currentTime);
    zenDroneGain.gain.linearRampToValueAtTime(0.22, audioCtx.currentTime + 1.5);
    
    zenOscL.connect(merger, 0, 0);
    zenOscR.connect(merger, 0, 1);
    
    merger.connect(zenDroneFilter);
    zenDroneFilter.connect(zenDroneGain);
    zenDroneGain.connect(getZenMasterGain());
    
    zenOscL.start();
    zenOscR.start();

    // Swelling Ambient Major 7th Pad Chord
    const pitches = [82.41, 123.47, 164.81, 207.65]; // E2, B2, E3, G#3 (soothing meditative harmony)
    zenPadOscs = [];
    zenPadFilter = audioCtx.createBiquadFilter();
    zenPadFilter.type = 'lowpass';
    zenPadFilter.frequency.setValueAtTime(200, audioCtx.currentTime);
    zenPadFilter.Q.setValueAtTime(1.5, audioCtx.currentTime);
    
    zenPadGain = audioCtx.createGain();
    zenPadGain.gain.setValueAtTime(0, audioCtx.currentTime);
    
    pitches.forEach(freq => {
        const osc = audioCtx.createOscillator();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
        osc.detune.setValueAtTime((Math.random() - 0.5) * 6, audioCtx.currentTime);
        osc.connect(zenPadFilter);
        osc.start();
        zenPadOscs.push(osc);
    });
    
    zenPadFilter.connect(zenPadGain);
    zenPadGain.connect(getZenMasterGain());
    zenPadGain.gain.linearRampToValueAtTime(0.08, audioCtx.currentTime + 3.0);
}

function stopDrone() {
    if (zenOscL) {
        try { zenOscL.stop(); zenOscL.disconnect(); } catch(e) {}
        zenOscL = null;
    }
    if (zenOscR) {
        try { zenOscR.stop(); zenOscR.disconnect(); } catch(e) {}
        zenOscR = null;
    }
    if (zenDroneGain) {
        try { zenDroneGain.disconnect(); } catch(e) {}
        zenDroneGain = null;
    }
    if (zenDroneFilter) {
        try { zenDroneFilter.disconnect(); } catch(e) {}
        zenDroneFilter = null;
    }
    if (zenPadOscs) {
        zenPadOscs.forEach(osc => {
            try { osc.stop(); osc.disconnect(); } catch(e) {}
        });
        zenPadOscs = [];
    }
    if (zenPadGain) {
        try { zenPadGain.disconnect(); } catch(e) {}
        zenPadGain = null;
    }
    if (zenPadFilter) {
        try { zenPadFilter.disconnect(); } catch(e) {}
        zenPadFilter = null;
    }
}

function startRain() {
    initAudioCtx();
    
    zenRainSource = audioCtx.createBufferSource();
    zenRainSource.buffer = getPinkNoiseBuffer();
    zenRainSource.loop = true;
    
    zenRainFilter = audioCtx.createBiquadFilter();
    zenRainFilter.type = 'lowpass';
    zenRainFilter.frequency.setValueAtTime(600, audioCtx.currentTime);
    
    zenRainGain = audioCtx.createGain();
    zenRainGain.gain.setValueAtTime(0, audioCtx.currentTime);
    zenRainGain.gain.linearRampToValueAtTime(0.35, audioCtx.currentTime + 1.0);
    
    zenRainLfo = audioCtx.createOscillator();
    zenRainLfo.type = 'sine';
    zenRainLfo.frequency.setValueAtTime(0.15, audioCtx.currentTime);
    
    zenRainLfoGain = audioCtx.createGain();
    zenRainLfoGain.gain.setValueAtTime(250, audioCtx.currentTime);
    
    zenRainLfo.connect(zenRainLfoGain);
    zenRainLfoGain.connect(zenRainFilter.frequency);
    
    zenRainSource.connect(zenRainFilter);
    zenRainFilter.connect(zenRainGain);
    zenRainGain.connect(getZenMasterGain());
    
    zenRainLfo.start();
    zenRainSource.start();

    // Synthesized Howling Wind Gusts
    zenWindSource = audioCtx.createBufferSource();
    zenWindSource.buffer = getPinkNoiseBuffer();
    zenWindSource.loop = true;
    
    zenWindFilter = audioCtx.createBiquadFilter();
    zenWindFilter.type = 'bandpass';
    zenWindFilter.frequency.setValueAtTime(400, audioCtx.currentTime);
    zenWindFilter.Q.setValueAtTime(3.0, audioCtx.currentTime);
    
    zenWindGain = audioCtx.createGain();
    zenWindGain.gain.setValueAtTime(0, audioCtx.currentTime);
    zenWindGain.gain.linearRampToValueAtTime(0.06, audioCtx.currentTime + 2.0);
    
    zenWindLfo = audioCtx.createOscillator();
    zenWindLfo.type = 'sine';
    zenWindLfo.frequency.setValueAtTime(0.07, audioCtx.currentTime); // 14s cycle
    
    zenWindLfoGain = audioCtx.createGain();
    zenWindLfoGain.gain.setValueAtTime(220, audioCtx.currentTime); // sweeps between 180Hz and 620Hz
    
    zenWindLfo.connect(zenWindLfoGain);
    zenWindLfoGain.connect(zenWindFilter.frequency);
    
    zenWindSource.connect(zenWindFilter);
    zenWindFilter.connect(zenWindGain);
    zenWindGain.connect(getZenMasterGain());
    
    zenWindLfo.start();
    zenWindSource.start();

    // Start random thunder schedule
    thunderActive = true;
    scheduleNextThunder();
}

function stopRain() {
    if (zenRainSource) {
        try { zenRainSource.stop(); zenRainSource.disconnect(); } catch(e) {}
        zenRainSource = null;
    }
    if (zenRainLfo) {
        try { zenRainLfo.stop(); zenRainLfo.disconnect(); } catch(e) {}
        zenRainLfo = null;
    }
    if (zenRainLfoGain) {
        try { zenRainLfoGain.disconnect(); } catch(e) {}
        zenRainLfoGain = null;
    }
    if (zenRainFilter) {
        try { zenRainFilter.disconnect(); } catch(e) {}
        zenRainFilter = null;
    }
    if (zenRainGain) {
        try { zenRainGain.disconnect(); } catch(e) {}
        zenRainGain = null;
    }
    if (zenWindSource) {
        try { zenWindSource.stop(); zenWindSource.disconnect(); } catch(e) {}
        zenWindSource = null;
    }
    if (zenWindLfo) {
        try { zenWindLfo.stop(); zenWindLfo.disconnect(); } catch(e) {}
        zenWindLfo = null;
    }
    if (zenWindLfoGain) {
        try { zenWindLfoGain.disconnect(); } catch(e) {}
        zenWindLfoGain = null;
    }
    if (zenWindFilter) {
        try { zenWindFilter.disconnect(); } catch(e) {}
        zenWindFilter = null;
    }
    if (zenWindGain) {
        try { zenWindGain.disconnect(); } catch(e) {}
        zenWindGain = null;
    }
    
    thunderActive = false;
    if (zenThunderTimer) {
        clearTimeout(zenThunderTimer);
        zenThunderTimer = null;
    }
}

function scheduleNextThunder() {
    if (!thunderActive) return;
    const delay = 25000 + Math.random() * 30000; // 25s - 55s
    zenThunderTimer = setTimeout(() => {
        if (!thunderActive) return;
        triggerThunder();
        scheduleNextThunder();
    }, delay);
}

function triggerThunder() {
    initAudioCtx();
    const now = audioCtx.currentTime;
    
    const thunderGain = audioCtx.createGain();
    thunderGain.gain.setValueAtTime(0, now);
    const peak = 0.22 + Math.random() * 0.18;
    thunderGain.gain.linearRampToValueAtTime(peak, now + 0.35);
    thunderGain.gain.exponentialRampToValueAtTime(0.0001, now + 5.5 + Math.random() * 3.0);
    
    const thunderFilter = audioCtx.createBiquadFilter();
    thunderFilter.type = 'lowpass';
    thunderFilter.frequency.setValueAtTime(75, now);
    
    const thunderSource = audioCtx.createBufferSource();
    if (!brownNoiseBuffer) {
        const bufferSize = audioCtx.sampleRate * 2;
        const buffer = audioCtx.createBuffer(1, bufferSize, audioCtx.sampleRate);
        const data = buffer.getChannelData(0);
        let lastOut = 0.0;
        for (let i = 0; i < bufferSize; i++) {
            let white = Math.random() * 2 - 1;
            data[i] = (lastOut + (0.02 * white)) / 1.02;
            lastOut = data[i];
            data[i] *= 3.5;
        }
        brownNoiseBuffer = buffer;
    }
    thunderSource.buffer = brownNoiseBuffer;
    
    thunderSource.connect(thunderFilter);
    thunderFilter.connect(thunderGain);
    thunderGain.connect(getZenMasterGain());
    
    thunderSource.start(now);
    thunderSource.stop(now + 9.0);
    
    // Trigger visual lightning flash on canvas
    lightningFlashAlpha = 0.55;
    
    setTimeout(() => {
        try {
            thunderSource.disconnect();
            thunderFilter.disconnect();
            thunderGain.disconnect();
        } catch(e) {}
    }, 9500);
}

function startChimes() {
    chimesActive = true;
    scheduleNextChime();
}

function stopChimes() {
    chimesActive = false;
    if (zenChimesTimer) {
        clearTimeout(zenChimesTimer);
        zenChimesTimer = null;
    }
}

function scheduleNextChime() {
    if (!chimesActive) return;
    const delay = 3000 + Math.random() * 5000;
    zenChimesTimer = setTimeout(() => {
        if (!chimesActive) return;
        strikeChime();
        if (Math.random() < 0.4) {
            setTimeout(() => {
                if (chimesActive) strikeChime();
            }, 150 + Math.random() * 250);
        }
        scheduleNextChime();
    }, delay);
}

function strikeChime() {
    initAudioCtx();
    const now = audioCtx.currentTime;
    const pitches = [523.25, 587.33, 659.25, 783.99, 880.00, 1046.50, 1174.66, 1318.51, 1567.98];
    const baseFreq = pitches[Math.floor(Math.random() * pitches.length)];
    
    const harmonics = [1, 1.45, 2.18, 3.12];
    const strikeGain = audioCtx.createGain();
    strikeGain.gain.setValueAtTime(0, now);
    
    const peakVol = 0.035 + Math.random() * 0.035;
    strikeGain.gain.linearRampToValueAtTime(peakVol, now + 0.005);
    strikeGain.gain.exponentialRampToValueAtTime(0.0001, now + 3.0 + Math.random() * 2.0);
    
    // Stereo panning
    const panner = audioCtx.createStereoPanner ? audioCtx.createStereoPanner() : null;
    if (panner) {
        panner.pan.setValueAtTime((Math.random() - 0.5) * 1.7, now); // randomly pan chimes
        strikeGain.connect(panner);
        panner.connect(getZenMasterGain());
    } else {
        strikeGain.connect(getZenMasterGain());
    }
    
    const oscillators = [];
    harmonics.forEach((h, index) => {
        const osc = audioCtx.createOscillator();
        const oscGain = audioCtx.createGain();
        
        osc.type = index === 0 ? 'sine' : 'triangle';
        osc.frequency.setValueAtTime(baseFreq * h, now);
        osc.detune.setValueAtTime((Math.random() - 0.5) * 8, now);
        
        const vol = 0.8 / (index * 1.5 + 1);
        oscGain.gain.setValueAtTime(vol, now);
        
        osc.connect(oscGain);
        oscGain.connect(strikeGain);
        osc.start(now);
        osc.stop(now + 5.5);
        oscillators.push({ osc, oscGain });
    });
    
    setTimeout(() => {
        oscillators.forEach(o => {
            try { o.osc.disconnect(); o.oscGain.disconnect(); } catch(e) {}
        });
        try {
            strikeGain.disconnect();
            if (panner) panner.disconnect();
        } catch(e) {}
    }, 6000);
}

function strikeSingingBowl() {
    initAudioCtx();
    const now = audioCtx.currentTime;
    const baseFreq = 220;
    
    const bowlGain = audioCtx.createGain();
    bowlGain.gain.setValueAtTime(0, now);
    bowlGain.gain.linearRampToValueAtTime(0.25, now + 0.05);
    bowlGain.gain.exponentialRampToValueAtTime(0.0001, now + 7.5);
    
    // Slow stereo sweep wash
    const panner = audioCtx.createStereoPanner ? audioCtx.createStereoPanner() : null;
    if (panner) {
        panner.pan.setValueAtTime(-0.75, now);
        panner.pan.linearRampToValueAtTime(0.75, now + 6.0);
        bowlGain.connect(panner);
        panner.connect(getZenMasterGain());
    } else {
        bowlGain.connect(getZenMasterGain());
    }
    
    const components = [
        { ratio: 1.0, type: 'sine', vol: 1.0 },
        { ratio: 1.006, type: 'sine', vol: 0.85 },
        { ratio: 1.5, type: 'sine', vol: 0.55 },
        { ratio: 2.2, type: 'sine', vol: 0.45 },
        { ratio: 2.76, type: 'sine', vol: 0.35 },
        { ratio: 3.8, type: 'sine', vol: 0.25 }
    ];
    
    const tremoloLfo = audioCtx.createOscillator();
    tremoloLfo.type = 'sine';
    tremoloLfo.frequency.setValueAtTime(1.5, now);
    
    const tremoloGain = audioCtx.createGain();
    tremoloGain.gain.setValueAtTime(0.7, now);
    
    const lfoDepth = audioCtx.createGain();
    lfoDepth.gain.setValueAtTime(0.3, now);
    tremoloLfo.connect(lfoDepth);
    lfoDepth.connect(tremoloGain.gain);
    
    tremoloGain.connect(bowlGain);
    
    const nodes = [];
    components.forEach(comp => {
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        
        osc.type = comp.type;
        osc.frequency.setValueAtTime(baseFreq * comp.ratio, now);
        osc.detune.setValueAtTime((Math.random() - 0.5) * 5, now);
        
        gain.gain.setValueAtTime(comp.vol, now);
        
        osc.connect(gain);
        gain.connect(tremoloGain);
        
        osc.start(now);
        osc.stop(now + 8.5);
        
        nodes.push({ osc, gain });
    });
    
    tremoloLfo.start(now);
    tremoloLfo.stop(now + 8.5);
    
    const bowlBtn = document.getElementById('sound-btn-bowl');
    if (bowlBtn) {
        bowlBtn.classList.add('striking');
        setTimeout(() => {
            bowlBtn.classList.remove('striking');
        }, 800);
    }
    
    const eq = document.getElementById('soundscape-eq');
    if (eq) {
        eq.classList.add('striking');
        setTimeout(() => {
            eq.classList.remove('striking');
        }, 800);
    }
    
    if (zenCanvas) {
        const w = zenCanvas.width;
        const h = zenCanvas.height;
        zenRipples.push({
            x: w / 2,
            y: h / 2,
            radius: 10,
            maxRadius: Math.max(w, h) * 0.9,
            speed: 3.5,
            alpha: 0.9,
            isBowlPulse: true
        });
    }
    
    const breatherBubble = document.getElementById('zen-breather-bubble');
    if (breatherBubble) {
        breatherBubble.classList.add('bowl-pulse');
        setTimeout(() => {
            breatherBubble.classList.remove('bowl-pulse');
        }, 2000);
    }
    
    setTimeout(() => {
        nodes.forEach(n => {
            try { n.osc.disconnect(); n.gain.disconnect(); } catch(e) {}
        });
        try {
            tremoloLfo.disconnect();
            lfoDepth.disconnect();
            tremoloGain.disconnect();
            bowlGain.disconnect();
            if (panner) panner.disconnect();
        } catch(e) {}
    }, 9500);
}

// ==========================================
// Canvas Interactive Modes
// ==========================================
class ZenParticle {
    constructor(w, h) {
        this.reset(w, h);
    }
    reset(w, h) {
        this.x = Math.random() * w;
        this.y = Math.random() * h;
        
        if (zenVisualizerMode === 'forest') {
            this.x = Math.random() * w;
            this.isMote = Math.random() < 0.45; // 45% are micro dust motes
            if (this.isMote) {
                this.y = Math.random() * h;
                this.vx = (Math.random() - 0.5) * 0.15;
                this.vy = -0.1 - Math.random() * 0.2; // slow drift
                this.baseSize = Math.random() * 1.2 + 0.8;
                this.alpha = Math.random() * 0.4 + 0.1;
            } else {
                this.y = h + Math.random() * 50;
                this.vx = (Math.random() - 0.5) * 0.3;
                this.vy = -0.4 - Math.random() * 0.6;
                this.baseSize = Math.random() * 2 + 1;
                this.alpha = Math.random() * 0.6 + 0.2;
            }
        } else if (zenVisualizerMode === 'ocean') {
            this.x = Math.random() * w;
            this.y = Math.random() * h;
            this.vx = (Math.random() - 0.5) * 0.2;
            this.vy = -0.2 - Math.random() * 0.3;
            this.alpha = Math.random() * 0.4 + 0.1;
            this.baseSize = Math.random() * 3 + 1.5;
        } else {
            this.x = Math.random() * w;
            this.y = Math.random() * h;
            this.vx = (Math.random() - 0.5) * 0.4;
            this.vy = (Math.random() - 0.5) * 0.4;
            this.alpha = Math.random() * 0.5 + 0.3;
            this.baseSize = Math.random() * 2 + 1;
        }
        
        this.size = this.baseSize;
        this.colorVal = Math.random();
        this.glowSpeed = 0.02 + Math.random() * 0.03;
        this.glowPhase = Math.random() * Math.PI * 2;
    }
    update(w, h, breathFactor) {
        if (zenVisualizerMode === 'cosmic') {
            const cx = w / 2;
            const cy = h / 2;
            const dx = cx - this.x;
            const dy = cy - this.y;
            const dist = Math.sqrt(dx * dx + dy * dy) || 1;
            
            const gravity = 0.02 * (1 + breathFactor * 1.5);
            this.vx += (dx / dist) * gravity;
            this.vy += (dy / dist) * gravity;
            
            const ox = -dy;
            const oy = dx;
            const orbit = 0.05 * (1 + breathFactor * 0.8);
            this.vx += (ox / dist) * orbit;
            this.vy += (oy / dist) * orbit;
            
            this.vx *= 0.98;
            this.vy *= 0.98;
            
            this.x += this.vx;
            this.y += this.vy;
            
            if (zenMouse.active && zenMouse.x !== null && zenMouse.y !== null) {
                const mdx = zenMouse.x - this.x;
                const mdy = zenMouse.y - this.y;
                const mdist = Math.sqrt(mdx * mdx + mdy * mdy) || 0.001; // Avoid division by zero/NaN
                if (mdist < 100) {
                    const force = (100 - mdist) / 100;
                    this.x -= (mdx / mdist) * force * 2.0;
                    this.y -= (mdy / mdist) * force * 2.0;
                }
            }
            this.size = this.baseSize * (1 + breathFactor * 1.2);
            
        } else if (zenVisualizerMode === 'forest') {
            if (this.isMote) {
                this.y += this.vy;
                this.x += this.vx + Math.sin(Date.now() / 1500 + this.colorVal * 5) * 0.08;
                this.alpha = 0.1 + Math.sin(Date.now() * this.glowSpeed + this.glowPhase) * 0.25;
                if (this.y < -10) this.reset(w, h);
            } else {
                this.y += this.vy * (1 + breathFactor * 0.5);
                this.x += this.vx + Math.sin(Date.now() / 1000 + this.colorVal * 10) * 0.15;
                
                if (zenMouse.active && zenMouse.x !== null && zenMouse.y !== null) {
                    const mdx = zenMouse.x - this.x;
                    const mdy = zenMouse.y - this.y;
                    const mdist = Math.sqrt(mdx * mdx + mdy * mdy) || 0.001; // Avoid division by zero/NaN
                    if (mdist < 120) {
                        const force = (120 - mdist) / 120;
                        this.x -= (mdx / mdist) * force * 2.5;
                        this.y -= (mdy / mdist) * force * 2.5;
                    }
                }
                
                if (this.y < -10 || this.x < -10 || this.x > w + 10) {
                    this.reset(w, h);
                }
            }
            this.size = this.baseSize * (1 + breathFactor * 0.8);
            
        } else if (zenVisualizerMode === 'ocean') {
            this.y += this.vy * (1 + breathFactor * 0.3);
            this.x += this.vx;
            this.x += Math.sin(Date.now() / 2000 + this.y * 0.01) * 0.1;
            
            if (zenMouse.active && zenMouse.x !== null && zenMouse.y !== null) {
                const mdx = zenMouse.x - this.x;
                const mdy = zenMouse.y - this.y;
                const mdist = Math.sqrt(mdx * mdx + mdy * mdy) || 0.001; // Avoid division by zero/NaN
                if (mdist < 150) {
                    const force = (150 - mdist) / 150;
                    this.x += (mdx / mdist) * force * 0.5;
                    this.y += (mdy / mdist) * force * 0.5;
                }
            }
            
            if (this.y < -20 || this.x < -20 || this.x > w + 20) {
                this.reset(w, h);
            }
            this.size = this.baseSize * (1 + breathFactor * 0.5);
        }
    }
    draw(ctx) {
        let r = 167, g = 139, b = 250; // Default fallback to cosmic purple
        if (zenVisualizerMode === 'cosmic') {
            if (this.colorVal < 0.4) {
                r = 45; g = 212; b = 168;
            } else if (this.colorVal < 0.8) {
                r = 167; g = 139; b = 250;
            } else {
                r = 251; g = 191; b = 36;
            }
        } else if (zenVisualizerMode === 'forest') {
            if (this.isMote) {
                r = 253; g = 230; b = 138;
            } else {
                if (this.colorVal < 0.8) {
                    r = 16; g = 185; b = 129;
                } else if (this.colorVal < 0.95) {
                    r = 245; g = 158; b = 11;
                } else {
                    r = 253; g = 230; b = 138;
                }
            }
        } else if (zenVisualizerMode === 'ocean') {
            if (this.colorVal < 0.5) {
                r = 56; g = 189; b = 248;
            } else if (this.colorVal < 0.85) {
                r = 14; g = 165; b = 233;
            } else {
                r = 45; g = 212; b = 168;
            }
        }
        
        if (zenVisualizerMode === 'forest') {
            // High-performance hardware-accelerated outer glow (avoiding costly shadowBlur)
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.size * 3.0, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${this.alpha * 0.18})`;
            ctx.fill();
        }
        
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${this.alpha})`;
        ctx.fill();
    }
}

let zenResizeTimeout = null;
function handleZenCanvasResize() {
    clearTimeout(zenResizeTimeout);
    zenResizeTimeout = setTimeout(() => {
        resizeZenCanvas();
    }, 100);
}

function initZenCanvas() {
    zenCanvas = document.getElementById('zen-canvas');
    if (!zenCanvas) return;
    
    zenCtx = zenCanvas.getContext('2d');
    resizeZenCanvas();
    
    zenParticles = [];
    const maxParticles = MAX_ZEN_PARTICLES;
    for (let i = 0; i < maxParticles; i++) {
        zenParticles.push(new ZenParticle(zenCanvas.width, zenCanvas.height));
    }
    
    zenCanvas.addEventListener('mousemove', handleZenMouseMove);
    zenCanvas.addEventListener('mouseleave', handleZenMouseLeave);
    zenCanvas.addEventListener('mouseenter', handleZenMouseEnter);
    zenCanvas.addEventListener('mousedown', handleZenCanvasClick);
    window.addEventListener('resize', handleZenCanvasResize);
    
    zenStartTime = Date.now();
    lastFrameTime = 0;
    
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
        zenCanvas.removeEventListener('mousedown', handleZenCanvasClick);
        zenCanvas = null;
    }
    zenCtx = null;
    window.removeEventListener('resize', handleZenCanvasResize);
}

function resizeZenCanvas() {
    if (!zenCanvas) return;
    const rect = zenCanvas.parentElement.getBoundingClientRect();
    zenCanvas.width = rect.width;
    zenCanvas.height = rect.height;
    
    zenParticles.forEach(p => {
        if (p.reset && (p.x > zenCanvas.width || p.y > zenCanvas.height)) {
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

function handleZenCanvasClick(e) {
    if (!zenCanvas) return;
    const rect = zenCanvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    zenRipples.push({
        x: x,
        y: y,
        radius: 0,
        maxRadius: 180 + Math.random() * 70,
        speed: 3 + Math.random() * 2,
        alpha: 1.0
    });
    
    if (zenRipples.length > 8) {
        zenRipples.shift();
    }

    // Spark visual bursts in Cosmic and foam in Ocean
    if (zenVisualizerMode === 'cosmic') {
        for (let i = 0; i < 18; i++) {
            const angle = Math.random() * Math.PI * 2;
            const speed = 1.2 + Math.random() * 2.8;
            zenParticles.push({
                x: x,
                y: y,
                vx: Math.cos(angle) * speed,
                vy: Math.sin(angle) * speed,
                baseSize: Math.random() * 2.2 + 1.2,
                size: 0,
                colorVal: Math.random(),
                alpha: 1.0,
                isTemp: true,
                life: 1.0,
                update(w, h, breathFactor) {
                    this.x += this.vx;
                    this.y += this.vy;
                    this.vx *= 0.96;
                    this.vy *= 0.96;
                    this.life = Math.max(0, this.life - 0.022); // Prevent negative life values
                    this.alpha = this.life;
                    this.size = this.baseSize * this.life;
                },
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
                    ctx.arc(this.x, this.y, Math.max(0, this.size), 0, Math.PI * 2); // Prevent negative radius
                    ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${this.alpha})`;
                    ctx.fill();
                }
            });
        }
    } else if (zenVisualizerMode === 'ocean') {
        for (let i = 0; i < 12; i++) {
            zenParticles.push({
                x: x + (Math.random() - 0.5) * 20,
                y: y + (Math.random() - 0.5) * 10,
                vx: (Math.random() - 0.5) * 0.8,
                vy: -0.8 - Math.random() * 1.2,
                baseSize: Math.random() * 3.5 + 2.0,
                size: 0,
                colorVal: Math.random(),
                alpha: 0.8,
                isTemp: true,
                life: 1.0,
                update(w, h, breathFactor) {
                    this.x += this.vx;
                    this.y += this.vy;
                    this.vy *= 0.97;
                    this.life = Math.max(0, this.life - 0.015); // Prevent negative life values
                    this.alpha = this.life * 0.65;
                    this.size = this.baseSize * (0.5 + this.life * 0.5);
                },
                draw(ctx) {
                    ctx.beginPath();
                    ctx.arc(this.x, this.y, Math.max(0, this.size), 0, Math.PI * 2); // Prevent negative radius
                    ctx.strokeStyle = `rgba(255, 255, 255, ${this.alpha})`;
                    ctx.lineWidth = 1.0;
                    ctx.stroke();
                }
            });
        }
    }
}

function setZenVisualizerMode(mode) {
    zenVisualizerMode = mode;
    
    document.querySelectorAll('.zen-visualizer-bar .filter-pill').forEach(btn => {
        if (btn.id === `zen-mode-${mode}`) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
    
    const container = document.querySelector('.zen-canvas-container');
    if (container) {
        container.classList.remove('visualizer-cosmic', 'visualizer-ocean', 'visualizer-forest');
        container.classList.add(`visualizer-${mode}`);
    }
    
    if (zenCanvas) {
        resizeZenCanvas();
        zenParticles = [];
        const maxParticles = MAX_ZEN_PARTICLES;
        for (let i = 0; i < maxParticles; i++) {
            zenParticles.push(new ZenParticle(zenCanvas.width, zenCanvas.height));
        }
    }
    
    showToast(`Visualizer mode set to ${mode.toUpperCase()} ✨`);
}

function setBreathingRhythm(rhythm) {
    zenBreathingRhythm = rhythm;
    document.querySelectorAll('.zen-breathing-bar .filter-pill').forEach(btn => {
        if (btn.id === `breath-rhythm-${rhythm}`) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
    
    // Play a brief visual phase ripple
    if (zenCanvas) {
        const w = zenCanvas.width;
        const h = zenCanvas.height;
        zenRipples.push({
            x: w / 2,
            y: h / 2,
            radius: 10,
            maxRadius: Math.max(w, h) * 0.5,
            speed: 3.0,
            alpha: 0.8,
            color: '45, 212, 168'
        });
    }
    
    showToast(`Breathing rhythm set to ${rhythm.toUpperCase()} ✨`);
}

function resetZenParticles() {
    if (!zenCanvas) return;
    zenParticles = [];
    const maxParticles = MAX_ZEN_PARTICLES;
    for (let i = 0; i < maxParticles; i++) {
        zenParticles.push(new ZenParticle(zenCanvas.width, zenCanvas.height));
    }
    showToast("Stardust regenerated ✨");
}

function drawForestLightBeams(ctx, w, h, elapsed, breathFactor) {
    // 1. Golden Sunburst Glow & Lens Flare Ring
    ctx.save();
    const sunGrad = ctx.createRadialGradient(w * 0.85, 0, 5, w * 0.85, 0, Math.max(120, w * 0.35 * (0.8 + breathFactor * 0.4)));
    sunGrad.addColorStop(0, `rgba(253, 230, 138, ${0.18 + breathFactor * 0.12})`);
    sunGrad.addColorStop(0.4, `rgba(245, 158, 11, ${0.06 + breathFactor * 0.04})`);
    sunGrad.addColorStop(1, 'transparent');
    ctx.fillStyle = sunGrad;
    ctx.beginPath();
    ctx.arc(w * 0.85, 0, w * 0.35 * (0.8 + breathFactor * 0.4), 0, Math.PI * 2);
    ctx.fill();
    
    // Lens flare ring
    if (breathFactor > 0.15) {
        ctx.beginPath();
        ctx.arc(w * 0.85, 0, w * 0.48 * (0.85 + breathFactor * 0.15), 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(253, 230, 138, ${(breathFactor - 0.15) * 0.045})`;
        ctx.lineWidth = 2.5 + breathFactor * 5.0;
        ctx.stroke();
    }
    ctx.restore();

    // 2. Crepuscular Light Beams (God Rays) - 1 Big Sweeping Beam
    ctx.save();
    ctx.globalCompositeOperation = 'screen';
    
    const timeScale = elapsed * 0.05;
    const angleOffset = Math.sin(timeScale) * (w * 0.12) + Math.cos(timeScale * 0.55) * (w * 0.035);
    
    // Position starting at the sunburst glow (w * 0.85)
    const startX = w * 0.85 + Math.cos(timeScale * 0.65) * (w * 0.02);
    const topWidth = w * 0.15 + Math.sin(timeScale) * 15;
    const bottomWidth = w * 0.65 + Math.cos(timeScale * 0.95) * 50;
    
    const endX = w * 0.35 + angleOffset;
    
    const baseAlpha = 0.045 + 0.025 * Math.sin(timeScale * 0.4);
    const breathAlpha = breathFactor * 0.095;
    const alpha = Math.max(0.02, baseAlpha + breathAlpha);
    
    const grad = ctx.createLinearGradient(startX, 0, endX, h);
    grad.addColorStop(0, `rgba(230, 253, 138, ${alpha})`);
    grad.addColorStop(0.25, `rgba(74, 222, 128, ${alpha * 0.8})`);
    grad.addColorStop(0.65, `rgba(16, 185, 129, ${alpha * 0.5})`);
    grad.addColorStop(1, `rgba(6, 95, 70, 0)`);
    
    ctx.beginPath();
    ctx.moveTo(startX - topWidth / 2, 0);
    ctx.lineTo(startX + topWidth / 2, 0);
    ctx.lineTo(endX + bottomWidth / 2, h);
    ctx.lineTo(endX - bottomWidth / 2, h);
    ctx.closePath();
    
    ctx.fillStyle = grad;
    ctx.fill();
    
    ctx.restore();

    // 3. Dynamic Swaying Leaf Canopy Silhouette
    ctx.save();
    ctx.fillStyle = 'rgba(6, 20, 10, 0.45)';
    if (document.body.classList.contains('theme-light')) {
        ctx.fillStyle = 'rgba(16, 85, 49, 0.08)'; // Soft translucent green in light theme
    }
    
    // Wind soughing offset
    const wind = Math.sin(elapsed * 0.07) * 14;
    
    // Top-left clump
    ctx.beginPath();
    ctx.moveTo(-40, -40);
    ctx.quadraticCurveTo(w * 0.22 + wind, h * 0.18 + wind * 0.3, w * 0.38 + wind, -40);
    ctx.quadraticCurveTo(w * 0.18 + wind * 0.5, h * 0.06, -40, -40);
    ctx.fill();
    
    // Top-right clump sifting sun shafts
    ctx.beginPath();
    ctx.moveTo(w + 40, -40);
    ctx.quadraticCurveTo(w * 0.62 + wind * 0.8, h * 0.24 + wind * 0.4, w * 0.42 + wind * 0.6, -40);
    ctx.quadraticCurveTo(w * 0.78 + wind * 0.3, h * 0.08, w + 40, -40);
    ctx.fill();
    
    // Helper function to draw organic hanging leaves soughing in wind
    const drawLeaf = (lx, ly, lsize, langle) => {
        ctx.save();
        ctx.translate(lx, ly);
        ctx.rotate(langle * Math.PI / 180);
        ctx.beginPath();
        ctx.moveTo(0, 0);
        ctx.quadraticCurveTo(lsize * 0.5, -lsize * 0.35, lsize, 0);
        ctx.quadraticCurveTo(lsize * 0.5, lsize * 0.35, 0, 0);
        ctx.closePath();
        ctx.fill();
        ctx.restore();
    };
    
    // Soughing leaves
    drawLeaf(w * 0.15 + wind, h * 0.08, 28, 40 + wind * 0.15);
    drawLeaf(w * 0.28 + wind * 1.1, h * 0.13, 20, -30 + wind * 0.2);
    drawLeaf(w * 0.52 + wind * 0.8, h * 0.15, 24, 20 - wind * 0.1);
    drawLeaf(w * 0.75 + wind * 0.6, h * 0.19, 30, -60 + wind * 0.08);
    
    ctx.restore();
}

function drawOceanWaves(ctx, w, h, elapsed, breathFactor) {
    // Under water light shafts sifting caustics
    ctx.save();
    ctx.globalCompositeOperation = 'screen';
    const numShafts = 2;
    for (let i = 0; i < numShafts; i++) {
        const time = elapsed * 0.1 + i * 1.2;
        const startX = w * 0.1 + Math.sin(time) * 40;
        const endX = w * 0.6 + Math.cos(time) * 100;
        const alpha = 0.02 + 0.02 * Math.sin(time * 0.5) + breathFactor * 0.03;
        
        const grad = ctx.createLinearGradient(startX, 0, endX, h);
        grad.addColorStop(0, `rgba(56, 189, 248, ${alpha})`);
        grad.addColorStop(0.7, `rgba(45, 212, 168, ${alpha * 0.3})`);
        grad.addColorStop(1, 'transparent');
        
        ctx.beginPath();
        ctx.moveTo(startX - 20, 0);
        ctx.lineTo(startX + 20, 0);
        ctx.lineTo(endX + 80, h * 0.7);
        ctx.lineTo(endX - 80, h * 0.7);
        ctx.closePath();
        ctx.fillStyle = grad;
        ctx.fill();
    }
    ctx.restore();

    const waveLayers = [
        { amp: 35, waveLen: 0.005, speed: 1.2, color: '56, 189, 248', baseHeight: h * 0.65 },
        { amp: 25, waveLen: 0.008, speed: 1.8, color: '14, 165, 233', baseHeight: h * 0.72 },
        { amp: 18, waveLen: 0.012, speed: 2.3, color: '45, 212, 168', baseHeight: h * 0.80 }
    ];
    
    ctx.save();
    waveLayers.forEach(layer => {
        ctx.beginPath();
        
        const step = 8;
        for (let x = 0; x <= w + step; x += step) {
            const timeTerm = (elapsed * layer.speed);
            const rawAmp = layer.amp * (1 + breathFactor * 0.8);
            let y = layer.baseHeight + Math.sin(x * layer.waveLen + timeTerm) * rawAmp;
            
            zenRipples.forEach(rip => {
                const dx = x - rip.x;
                const dist = Math.abs(dx);
                if (dist < rip.radius && dist > rip.radius - 40) {
                    const factor = (40 - (rip.radius - dist)) / 40;
                    const rippleDisplacement = Math.sin((rip.radius - dist) * 0.2) * 15 * rip.alpha * factor;
                    y += rippleDisplacement;
                }
            });
            
            if (zenMouse.active && zenMouse.x !== null && zenMouse.y !== null) {
                const distToCursor = Math.abs(x - zenMouse.x);
                if (distToCursor < 120) {
                    const depth = (120 - distToCursor) / 120;
                    y += Math.sin(elapsed * 5) * 8 * depth;
                }
            }
            
            if (x === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        }
        
        ctx.lineTo(w, h);
        ctx.lineTo(0, h);
        ctx.closePath();
        
        ctx.fillStyle = `rgba(${layer.color}, 0.25)`;
        ctx.fill();
        
        ctx.strokeStyle = `rgba(${layer.color}, 0.75)`;
        ctx.lineWidth = 2.5;
        ctx.stroke();
    });
    ctx.restore();
}

function animateZen() {
    if (!zenCanvas || !zenCtx) return;
    
    lastFrameTime = Date.now();
    
    // If canvas size is zero, try to resize it (in case layout was not complete during init)
    if (zenCanvas.width === 0 || zenCanvas.height === 0) {
        resizeZenCanvas();
    }
    
    const w = zenCanvas.width;
    const h = zenCanvas.height;
    if (w === 0 || h === 0) {
        // Still zero, defer rendering to next frame
        zenAnimFrame = requestAnimationFrame(animateZen);
        return;
    }
    
    const elapsed = (Date.now() - zenStartTime) / 1000;
    
    let cycleTotal = 16.0;
    if (zenBreathingRhythm === 'relax') {
        cycleTotal = 19.0;
    } else if (zenBreathingRhythm === 'coherent') {
        cycleTotal = 10.0;
    }
    const cycleTime = elapsed % cycleTotal;
    
    let breathFactor = 0;
    let breathText = "";
    let breathColor = "rgba(45, 212, 168, 0.4)";
    let textGlowColor = "#2dd4a8";
    let breathPhase = "";
    
    if (zenBreathingRhythm === 'box') {
        if (cycleTime < 4.0) {
            breathFactor = cycleTime / 4.0;
            breathText = "Inhale";
            breathColor = "rgba(45, 212, 168, 0.35)";
            textGlowColor = "#2dd4a8";
            breathPhase = "inhale";
        } else if (cycleTime < 8.0) {
            breathFactor = 1.0;
            breathText = "Hold";
            breathColor = "rgba(251, 191, 36, 0.35)";
            textGlowColor = "#fbbf24";
            breathPhase = "hold-in";
        } else if (cycleTime < 12.0) {
            breathFactor = 1.0 - (cycleTime - 8.0) / 4.0;
            breathText = "Exhale";
            breathColor = "rgba(167, 139, 250, 0.35)";
            textGlowColor = "#a78bfa";
            breathPhase = "exhale";
        } else {
            breathFactor = 0.0;
            breathText = "Hold";
            breathColor = "rgba(244, 63, 94, 0.35)";
            textGlowColor = "#f43f5e";
            breathPhase = "hold-out";
        }
    } else if (zenBreathingRhythm === 'relax') {
        if (cycleTime < 4.0) {
            breathFactor = cycleTime / 4.0;
            breathText = "Inhale";
            breathColor = "rgba(45, 212, 168, 0.35)";
            textGlowColor = "#2dd4a8";
            breathPhase = "inhale";
        } else if (cycleTime < 11.0) {
            breathFactor = 1.0;
            breathText = "Hold";
            breathColor = "rgba(251, 191, 36, 0.35)";
            textGlowColor = "#fbbf24";
            breathPhase = "hold-in";
        } else {
            breathFactor = 1.0 - (cycleTime - 11.0) / 8.0;
            breathText = "Exhale";
            breathColor = "rgba(167, 139, 250, 0.35)";
            textGlowColor = "#a78bfa";
            breathPhase = "exhale";
        }
    } else if (zenBreathingRhythm === 'coherent') {
        if (cycleTime < 5.0) {
            breathFactor = cycleTime / 5.0;
            breathText = "Inhale";
            breathColor = "rgba(45, 212, 168, 0.35)";
            textGlowColor = "#2dd4a8";
            breathPhase = "inhale";
        } else {
            breathFactor = 1.0 - (cycleTime - 5.0) / 5.0;
            breathText = "Exhale";
            breathColor = "rgba(167, 139, 250, 0.35)";
            textGlowColor = "#a78bfa";
            breathPhase = "exhale";
        }
    }

    // Real-time Audio Synth breathing integration
    try {
        if (audioCtx && activeZenSounds.drone) {
            if (zenPadFilter && zenPadGain) {
                const targetFreq = 200 + breathFactor * 450; // sweeps cutoff 200Hz to 650Hz
                zenPadFilter.frequency.setTargetAtTime(targetFreq, audioCtx.currentTime, 0.1);
                
                const targetVol = 0.08 + breathFactor * 0.12;
                zenPadGain.gain.setTargetAtTime(targetVol * zenMasterVolume, audioCtx.currentTime, 0.15);
            }
            if (zenDroneGain) {
                const targetDroneVol = 0.22 + breathFactor * 0.18;
                zenDroneGain.gain.setTargetAtTime(targetDroneVol * zenMasterVolume, audioCtx.currentTime, 0.1);
            }
        }
    } catch (e) {
        console.warn("Web Audio breathing parameters update failed:", e);
    }
    
    if (zenVisualizerMode === 'cosmic') {
        zenCtx.fillStyle = 'rgba(5, 5, 11, 0.18)';
        zenCtx.fillRect(0, 0, w, h);
        
        // Draw cosmic breathing nebula glow
        const nebulaGrad = zenCtx.createRadialGradient(w/2, h/2, 10, w/2, h/2, Math.max(100, (w+h)/4.2 * (0.85 + breathFactor * 0.35)));
        nebulaGrad.addColorStop(0, `rgba(167, 139, 250, ${0.08 + breathFactor * 0.05})`);
        nebulaGrad.addColorStop(0.4, `rgba(45, 212, 168, ${0.04 + breathFactor * 0.03})`);
        nebulaGrad.addColorStop(1, 'transparent');
        zenCtx.fillStyle = nebulaGrad;
        zenCtx.fillRect(0, 0, w, h);
    } else {
        zenCtx.clearRect(0, 0, w, h);
    }
    
    if (zenVisualizerMode === 'forest') {
        drawForestLightBeams(zenCtx, w, h, elapsed, breathFactor);
    } else if (zenVisualizerMode === 'ocean') {
        drawOceanWaves(zenCtx, w, h, elapsed, breathFactor);
    }

    // Trigger visual phase ripple when breathing shifts phases
    if (lastBreathPhase !== breathPhase) {
        let rippleColor = '56, 189, 248';
        if (breathPhase === 'hold-in') rippleColor = '251, 191, 36';
        else if (breathPhase === 'exhale') rippleColor = '167, 139, 250';
        else if (breathPhase === 'hold-out') rippleColor = '244, 63, 94';
        
        zenRipples.push({
            x: w / 2,
            y: h / 2,
            radius: 40,
            maxRadius: Math.max(w, h) * 0.85,
            speed: 2.5,
            alpha: 0.7,
            isBowlPulse: false,
            color: rippleColor
        });
        lastBreathPhase = breathPhase;
    }

    // Draw general expansion ripples in all modes
    zenCtx.save();
    zenRipples.forEach(rip => {
        rip.radius += rip.speed;
        rip.alpha = 1.0 - (rip.radius / rip.maxRadius);
        
        if (rip.alpha <= 0) return;
        
        zenCtx.beginPath();
        zenCtx.arc(rip.x, rip.y, rip.radius, 0, Math.PI * 2);
        if (rip.isBowlPulse) {
            zenCtx.strokeStyle = `rgba(251, 191, 36, ${rip.alpha * 0.65})`;
            zenCtx.lineWidth = 3.5;
        } else if (rip.color) {
            zenCtx.strokeStyle = `rgba(${rip.color}, ${rip.alpha * 0.45})`;
            zenCtx.lineWidth = 2.5;
        } else {
            zenCtx.strokeStyle = `rgba(56, 189, 248, ${rip.alpha * 0.4})`;
            zenCtx.lineWidth = 2;
        }
        zenCtx.stroke();
    });
    zenCtx.restore();

    // Clean up expired ripples
    zenRipples = zenRipples.filter(rip => rip.alpha > 0);

    // Memory clean dead temp particles
    zenParticles = zenParticles.filter(p => !p.isTemp || p.life > 0);
    
    zenParticles.forEach(p => {
        p.update(w, h, breathFactor);
        p.draw(zenCtx);
    });
    
    if (zenVisualizerMode === 'cosmic') {
        for (let i = 0; i < zenParticles.length; i++) {
            if (zenParticles[i].isTemp) continue;
            for (let j = i + 1; j < zenParticles.length; j++) {
                if (zenParticles[j].isTemp) continue;
                const p1 = zenParticles[i];
                const p2 = zenParticles[j];
                const dx = p1.x - p2.x;
                const dy = p1.y - p2.y;
                const distSq = dx * dx + dy * dy;
                
                if (distSq < 3600) {
                    const dist = Math.sqrt(distSq);
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
    }
    
    const breatherBubble = document.getElementById('zen-breather-bubble');
    const breatherText = document.getElementById('zen-breather-text');
    if (breatherBubble && breatherText) {
        const scaleVal = 1 + breathFactor * 0.8;
        breatherBubble.style.transform = `translate(-50%, -50%) scale(${scaleVal})`;
        
        const phases = ["inhale", "hold-in", "exhale", "hold-out"];
        phases.forEach(p => {
            if (p === breathPhase) {
                breatherBubble.classList.add(p);
            } else {
                breatherBubble.classList.remove(p);
            }
        });
        
        breatherText.textContent = breathText;
        breatherText.style.color = textGlowColor;
    }

    // Draw visual lightning flashes overlay
    if (lightningFlashAlpha > 0) {
        zenCtx.save();
        zenCtx.fillStyle = `rgba(255, 255, 255, ${lightningFlashAlpha})`;
        zenCtx.fillRect(0, 0, w, h);
        zenCtx.restore();
        lightningFlashAlpha -= 0.045; // decays over 12 frames
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

// Global App Theme Switcher
function initAppTheme() {
    const savedTheme = localStorage.getItem('mindflow-theme') || 'cosmic';
    setAppTheme(savedTheme, false); // Apply theme on boot without visual toast
}

function setAppTheme(themeName, showNotification = true) {
    // 1. Clean theme body classes
    document.body.classList.remove('theme-cosmic', 'theme-ocean', 'theme-forest', 'theme-light');
    
    // 2. Add current theme class
    document.body.classList.add('theme-' + themeName);
    
    // 3. Save choice in local storage
    localStorage.setItem('mindflow-theme', themeName);
    
    // 4. Highlight active indicator button in the sidebar
    const btns = document.querySelectorAll('.theme-select-btn');
    btns.forEach(btn => {
        if (btn.id === `theme-btn-${themeName}`) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
    
    // 5. Auto-sync Zen visualizer mode for maximum aesthetic immersion
    if (typeof setZenVisualizerMode === 'function') {
        if (themeName === 'cosmic' && typeof zenVisualizerMode !== 'undefined' && zenVisualizerMode !== 'cosmic') {
            setZenVisualizerMode('cosmic');
        } else if (themeName === 'ocean' && typeof zenVisualizerMode !== 'undefined' && zenVisualizerMode !== 'ocean') {
            setZenVisualizerMode('ocean');
        } else if (themeName === 'forest' && typeof zenVisualizerMode !== 'undefined' && zenVisualizerMode !== 'forest') {
            setZenVisualizerMode('forest');
        } else if (themeName === 'light' && typeof zenVisualizerMode !== 'undefined' && zenVisualizerMode !== 'forest') {
            setZenVisualizerMode('forest');
        }
    }
    
    // 6. Show premium transition confirmation toast
    if (showNotification) {
        const themeNamesMap = {
            'cosmic': 'Cosmic Flow',
            'ocean': 'Ocean Waves',
            'forest': 'Forest Light',
            'light': 'Solar Breeze'
        };
        showToast(`Theme switched to ${themeNamesMap[themeName]}! 🎨`);
    }
}

// Focus Timeline Hover Tooltip Helpers
function showTooltipForSegment(seg) {
    const tooltip = document.getElementById('timeline-tooltip');
    if (!tooltip || !seg) return;
    
    const mode = seg.dataset.mode;
    const startTimeStr = seg.dataset.startTime;
    const endTimeStr = seg.dataset.endTime;
    const durationText = seg.dataset.duration;
    const brainDump = seg.dataset.brainDump;
    const leftPct = parseFloat(seg.dataset.leftPct);
    const widthPct = parseFloat(seg.dataset.widthPct);
    
    let modeColorVar = 'var(--neutral-color)';
    let modeLabel = 'Neutral';
    if (mode === 'work') {
        modeColorVar = 'var(--work-color)';
        modeLabel = 'Focus';
    } else if (mode === 'recharge') {
        modeColorVar = 'var(--recharge-color)';
        modeLabel = 'Recharge';
    } else if (mode === 'rest') {
        modeColorVar = 'var(--rest-color)';
        modeLabel = 'Rest';
    }
    
    let tooltipHtml = `
        <strong style="color: ${modeColorVar}; text-transform: uppercase; font-size: 0.8rem; display: block; margin-bottom: 0.25rem; font-weight: 700; letter-spacing: 0.05em;">${modeLabel} Session</strong>
        <span style="display: block; color: var(--text-secondary); margin-bottom: 0.15rem; font-weight: 500;">🕒 ${startTimeStr} - ${endTimeStr} (${durationText})</span>
    `;
    
    if (brainDump) {
        tooltipHtml += `
            <div style="border-top: 1px solid var(--border-color); margin-top: 0.35rem; padding-top: 0.35rem; display: flex; flex-direction: column; gap: 0.1rem;">
                <span style="font-size: 0.68rem; color: var(--text-muted); text-transform: uppercase; font-weight: 600; letter-spacing: 0.03em;">Save-State:</span>
                <span style="color: var(--text-primary); font-style: italic; font-size: 0.72rem; white-space: normal; max-width: 260px; line-height: 1.3;">"${escapeHtml(brainDump)}"</span>
            </div>
        `;
    }
    
    tooltip.innerHTML = tooltipHtml;
    tooltip.style.borderColor = modeColorVar;
    
    // Measure width to clamp position
    const tooltipRect = tooltip.getBoundingClientRect();
    const tooltipWidth = tooltipRect.width || tooltip.offsetWidth || 200;
    
    const outer = document.querySelector('.timeline-track-outer');
    const outerWidth = outer ? outer.getBoundingClientRect().width : window.innerWidth;
    
    const midPx = ((leftPct + (widthPct / 2)) / 100) * outerWidth;
    const halfWidth = tooltipWidth / 2;
    let finalLeftPx = midPx;
    
    if (finalLeftPx - halfWidth < 0) {
        finalLeftPx = halfWidth;
    } else if (finalLeftPx + halfWidth > outerWidth) {
        finalLeftPx = outerWidth - halfWidth;
    }
    
    // Adjust arrow to point directly to segment midpoint
    const shiftPx = midPx - finalLeftPx;
    const arrowPct = 50 + (shiftPx / tooltipWidth) * 100;
    const clampedArrowPct = Math.max(5, Math.min(95, arrowPct));
    
    tooltip.style.setProperty('--arrow-left', `${clampedArrowPct}%`);
    tooltip.style.left = `${finalLeftPx}px`;
    tooltip.style.visibility = 'visible';
    tooltip.style.opacity = '1';
}

function hideTooltip() {
    const tooltip = document.getElementById('timeline-tooltip');
    if (tooltip) {
        tooltip.style.opacity = '0';
        tooltip.style.visibility = 'hidden';
    }
}

// Week Navigation pagination logic for analytics Energy Map
function navigateWeek(offsetChange) {
    weekOffset += offsetChange;
    if (weekOffset < 0) weekOffset = 0;
    if (weekOffset > 12) weekOffset = 12; // Cap at 12 weeks ago
    
    // Show chart loading skeleton again for premium visual response
    const skeleton = document.getElementById('chart-skeleton');
    if (skeleton) {
        skeleton.style.display = 'block';
    }
    
    // Remove the old chart SVG
    const svg = document.querySelector('.svg-chart');
    if (svg) {
        svg.remove();
    }
    
    loadAnalytics();
}

