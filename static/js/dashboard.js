// MIND-FLOW Dashboard Logic

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
const activeProfileName = document.getElementById('active-profile-name');
const portalSphere = document.getElementById('portal-sphere');
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
    currentTab = tabId;
    document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(btn => btn.classList.remove('active'));
    
    document.getElementById(`tab-${tabId}`).classList.add('active');
    document.getElementById(`nav-btn-${tabId}`).classList.add('active');
    updateNavIndicator();
    
    // Smooth scroll the content area back to top on tab switch
    const mainContent = document.querySelector('.main-content');
    if (mainContent) {
        mainContent.scrollTop = 0;
    }
    window.scrollTo({ top: 0, behavior: 'smooth' });
    
    if (tabId === 'analytics') {
        loadAnalytics();
    } else if (tabId === 'settings') {
        loadSettings();
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

// Animate BG glow slightly based on mouse move to feel organic
document.addEventListener('mousemove', (e) => {
    const x = e.clientX / window.innerWidth;
    const y = e.clientY / window.innerHeight;
    
    glow1.style.transform = `translate(${x * 30}px, ${y * 30}px)`;
    glow2.style.transform = `translate(${-x * 40}px, ${-y * 40}px)`;
});

// 3D Card Tilt Effect
document.querySelectorAll('.card').forEach(card => {
    card.addEventListener('mouseenter', () => {
        card.style.transition = 'transform 0.1s ease-out, border-color 0.3s ease, box-shadow 0.4s ease';
    });
    card.addEventListener('mousemove', (e) => {
        const rect = card.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        const centerX = rect.width / 2;
        const centerY = rect.height / 2;
        const rotateX = ((y - centerY) / centerY) * -3;
        const rotateY = ((x - centerX) / centerX) * 3;
        card.style.transform = `perspective(800px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateY(-4px)`;
    });
    card.addEventListener('mouseleave', () => {
        card.style.transition = '';
        card.style.transform = '';
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
        
        // 1. Update Body classes for mode specific glows
        bodyEl.className = '';
        bodyEl.classList.add(`mode-${status.current_mode}`);
        updateNavIndicator();
        
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
        let profileName = 'Neutral State (No Portal)';
        
        if (status.current_mode === 'work') {
            emoji = '💻';
            profileName = 'Work Mode (Work Files Loaded)';
        } else if (status.current_mode === 'recharge') {
            emoji = '🎮';
            profileName = 'Recharge Mode (Games & Shortcuts Loaded)';
        } else if (status.current_mode === 'rest') {
            emoji = '💤';
            profileName = 'Rest Mode (Desktop Cleaned)';
        }
        statusIcon.textContent = emoji;
        activeProfileName.textContent = profileName;
        
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

// Load Settings from Backend
async function loadSettings() {
    try {
        const res = await fetch('/api/settings');
        const settings = await res.json();
        
        document.getElementById('work-limit-input').value = settings.work_duration_minutes;
        document.getElementById('idle-timeout-input').value = settings.idle_timeout_seconds;
        document.getElementById('work-keywords-input').value = settings.work_keywords.join(', ');
        document.getElementById('recharge-keywords-input').value = settings.recharge_keywords.join(', ');
        document.getElementById('autopilot-input').checked = settings.adaptive_timers_enabled !== false;
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
        work_keywords: document.getElementById('work-keywords-input').value.split(',').map(k => k.trim()),
        recharge_keywords: document.getElementById('recharge-keywords-input').value.split(',').map(k => k.trim()),
        adaptive_timers_enabled: document.getElementById('autopilot-input').checked
    };
    
    try {
        const res = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });
        if (res.ok) {
            showToast("Settings Applied Successfully!");
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
function triggerParticleBurst(e) {
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
        
        let color = '#a78bfa';
        if (bodyEl.classList.contains('mode-recharge')) color = '#2dd4a8';
        else if (bodyEl.classList.contains('mode-rest')) color = '#fbbf24';
        
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
    
    // Filter data based on selection
    let filteredData = [];
    const todayStr = new Date().toISOString().split('T')[0];
    
    if (appStatsFilter === 'today') {
        // Find entries matching today's date
        filteredData = appStatsData.filter(entry => entry.date === todayStr);
    } else {
        // Last 7 days including today
        const cutoffDate = new Date();
        cutoffDate.setDate(cutoffDate.getDate() - 7);
        const cutoffStr = cutoffDate.toISOString().split('T')[0];
        
        // Group by process and category to show cumulative totals
        const cumulative = {};
        appStatsData.forEach(entry => {
            if (entry.date >= cutoffStr) {
                const key = entry.process;
                if (!cumulative[key]) {
                    cumulative[key] = {
                        process: entry.process,
                        title: entry.title,
                        duration: 0,
                        category: entry.category
                    };
                }
                cumulative[key].duration += entry.duration;
                // Prefer non-empty title or the latest title
                if (entry.title && entry.title !== "None") {
                    cumulative[key].title = entry.title;
                }
            }
        });
        filteredData = Object.values(cumulative);
    }
    
    // Sort by duration descending
    filteredData.sort((a, b) => b.duration - a.duration);
    
    if (filteredData.length === 0) {
        listEl.innerHTML = `<div style="text-align: center; color: var(--text-muted); font-size: 0.85rem; padding: 2rem 0;">No application activity tracked for this period.</div>`;
        return;
    }
    
    // Calculate total duration for percentages
    const totalDuration = filteredData.reduce((sum, item) => sum + item.duration, 0);
    
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
    
    filteredData.forEach(item => {
        const pct = totalDuration > 0 ? (item.duration / totalDuration) * 100 : 0;
        const emoji = getAppEmoji(item.process);
        const durationText = formatAppDuration(item.duration);
        
        const appItem = document.createElement('div');
        appItem.className = 'app-item';
        appItem.innerHTML = `
            <div class="app-item-top">
                <div class="app-item-details">
                    <span class="app-item-icon">${emoji}</span>
                    <div class="app-item-meta">
                        <span class="app-name">${escapeHtml(item.process)}</span>
                        <span class="app-title-sub" title="${escapeHtml(item.title)}">${escapeHtml(item.title)}</span>
                    </div>
                </div>
                <span class="app-duration-badge">${durationText}</span>
            </div>
            <div class="app-progress-container">
                <div class="app-progress-bar ${item.category}" style="width: 0%;"></div>
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
        text.textContent = val;
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

    // Crosshair hover tracking event listeners
    overlay.addEventListener('mousemove', (e) => {
        const rect = svg.getBoundingClientRect();
        const localX = (e.clientX - rect.left) * (width / rect.width);
        
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
            
        tooltipEl.innerHTML = `
            <h4>${dayName} Analysis</h4>
            <div class="chart-tooltip-metric">
                <span>⚡ Avg Energy: <strong style="color: var(--recharge-color);">${avgEnergy.toFixed(1)}/5</strong></span>
                <span>🧱 Avg Friction: <strong style="color: var(--work-color);">${avgFriction.toFixed(1)}/5</strong></span>
            </div>
            <div class="chart-tooltip-summary">
                ${summariesText}
            </div>
        `;
        
        tooltipEl.style.opacity = '1';
        const tooltipRect = tooltipEl.getBoundingClientRect();
        const maxLeft = window.innerWidth - (tooltipRect.width || 200) - 20;
        const maxTop = window.innerHeight - (tooltipRect.height || 100) - 20;
        tooltipEl.style.top = `${Math.min(e.pageY - 20, maxTop + window.scrollY)}px`;
        tooltipEl.style.left = `${Math.min(e.pageX + 15, maxLeft + window.scrollX)}px`;
    });

    overlay.addEventListener('mouseleave', () => {
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

