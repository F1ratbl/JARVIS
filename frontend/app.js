document.addEventListener('DOMContentLoaded', () => {
    // Top Bar & Global Elements
    const headerStatusIndicator = document.getElementById('header-status-indicator');
    const headerStatusText = document.getElementById('header-status-text');
    
    // Sidebar Elements
    const ramPercentage = document.getElementById('ram-percentage');
    const ramFill = document.getElementById('ram-fill');
    const ramDetails = document.getElementById('ram-details');
    const chatSessionsList = document.getElementById('chat-sessions-list');
    const btnNewChat = document.getElementById('btn-new-chat');
    const btnClearChats = document.getElementById('btn-clear-chats');

    // Bottom Mic / Orb Elements
    const orbContainer = document.getElementById('orb-container');
    const micStatusText = document.getElementById('mic-status-text');
    
    // Chat History & Input
    const chatHistory = document.getElementById('chat-history');
    const chatInput = document.getElementById('chat-input');
    const btnSendChat = document.getElementById('btn-send-chat');

    // Setup Modal Elements
    const setupModal = document.getElementById('setup-modal');
    const setupModalContent = document.getElementById('setup-modal-content');
    const modalRamTotal = document.getElementById('modal-ram-total');
    const modalRamAvail = document.getElementById('modal-ram-avail');
    const modalRecWhisper = document.getElementById('modal-rec-whisper');
    const modalRecLlm = document.getElementById('modal-rec-llm');
    const modelRecommendationText = document.getElementById('model-recommendation-text');
    const modelOptions = document.getElementById('model-options');
    const btnAcceptModels = document.getElementById('btn-accept-models');
    
    const mainApp = document.getElementById('main-app');
    let selectedSetupModel = '';
    let latestModelSetup = null;
    const SETUP_VERSION = 'model-picker-v1';
    const CHAT_STORE_KEY = 'jarvis.chat.sessions.v1';
    const ACTIVE_CHAT_KEY = 'jarvis.chat.active.v1';
    const chatTemplate = chatHistory ? chatHistory.innerHTML : '';
    let chatSessions = [];
    let activeChatId = '';

    function formatStatus(text) {
        const value = String(text || '').trim();
        if (!value) return 'Hazırlanıyor';
        if (value.includes('Dinlemeye Hazır')) return 'Dinlemeye hazır';
        if (value.includes('Hazır ve Bekliyor')) return 'Hazır';
        return value;
    }

    function escapeHtml(value) {
        return String(value)
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;')
            .replaceAll("'", '&#039;');
    }

    function createChatSession(title = 'Yeni sohbet') {
        const now = Date.now();
        return {
            id: `chat-${now}-${Math.random().toString(16).slice(2)}`,
            title,
            createdAt: now,
            updatedAt: now,
            messages: [],
        };
    }

    function loadChatSessions() {
        try {
            const stored = JSON.parse(localStorage.getItem(CHAT_STORE_KEY) || '[]');
            chatSessions = Array.isArray(stored) ? stored : [];
        } catch {
            chatSessions = [];
        }

        if (!chatSessions.length) {
            const firstSession = createChatSession();
            chatSessions = [firstSession];
            activeChatId = firstSession.id;
            saveChatSessions();
            return;
        }

        activeChatId = localStorage.getItem(ACTIVE_CHAT_KEY) || chatSessions[0].id;
        if (!chatSessions.some(session => session.id === activeChatId)) {
            activeChatId = chatSessions[0].id;
        }
    }

    function saveChatSessions() {
        localStorage.setItem(CHAT_STORE_KEY, JSON.stringify(chatSessions));
        if (activeChatId) {
            localStorage.setItem(ACTIVE_CHAT_KEY, activeChatId);
        }
    }

    function currentChatSession() {
        return chatSessions.find(session => session.id === activeChatId) || chatSessions[0];
    }

    function sendClearHistoryToServer() {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ action: 'clear_history' }));
        }
    }

    function startNewChat() {
        const session = createChatSession();
        chatSessions.unshift(session);
        activeChatId = session.id;
        saveChatSessions();
        renderChatSessions();
        renderActiveChat();
        sendClearHistoryToServer();
        chatInput?.focus();
    }

    function clearAllChats() {
        if (!window.confirm('Tüm sohbet geçmişi silinsin mi?')) return;
        const session = createChatSession();
        chatSessions = [session];
        activeChatId = session.id;
        saveChatSessions();
        renderChatSessions();
        renderActiveChat();
        sendClearHistoryToServer();
    }

    function deleteChatSession(sessionId) {
        const session = chatSessions.find(item => item.id === sessionId);
        if (!session) return;

        if (!window.confirm(`"${session.title || 'Yeni sohbet'}" sohbeti silinsin mi?`)) return;

        const deletedWasActive = activeChatId === sessionId;
        chatSessions = chatSessions.filter(item => item.id !== sessionId);
        if (!chatSessions.length) {
            const replacement = createChatSession();
            chatSessions = [replacement];
            activeChatId = replacement.id;
        } else if (deletedWasActive) {
            activeChatId = chatSessions[0].id;
        }

        saveChatSessions();
        renderChatSessions();
        renderActiveChat();
        if (deletedWasActive) {
            sendClearHistoryToServer();
        }
    }

    function switchChatSession(sessionId) {
        if (sessionId === activeChatId) return;
        activeChatId = sessionId;
        saveChatSessions();
        renderChatSessions();
        renderActiveChat();
        sendClearHistoryToServer();
    }

    function persistChatMessage(role, message, isError, timestamp) {
        const session = currentChatSession();
        if (!session) return;

        session.messages.push({ role, message, isError, timestamp });
        session.updatedAt = timestamp;
        if (role === 'USER' && (!session.title || session.title === 'Yeni sohbet')) {
            session.title = message.length > 42 ? `${message.slice(0, 39)}...` : message;
        }

        chatSessions = [
            session,
            ...chatSessions.filter(item => item.id !== session.id)
        ];
        activeChatId = session.id;
        saveChatSessions();
        renderChatSessions();
    }

    function renderChatSessions() {
        if (!chatSessionsList) return;
        chatSessionsList.innerHTML = '';

        if (!chatSessions.length) {
            chatSessionsList.innerHTML = '<li class="text-on-surface-variant/50">Henüz sohbet yok.</li>';
            return;
        }

        chatSessions.forEach(session => {
            const li = document.createElement('li');
            const button = document.createElement('button');
            const menu = document.createElement('div');
            const menuButton = document.createElement('button');
            const deleteButton = document.createElement('button');
            const lastMessage = session.messages[session.messages.length - 1];
            const time = new Date(session.updatedAt || session.createdAt).toLocaleTimeString('tr-TR', {
                hour: '2-digit',
                minute: '2-digit',
            });

            li.className = 'chat-session-item';

            button.type = 'button';
            button.className = `chat-session-button ${session.id === activeChatId ? 'chat-session-active' : ''}`;
            button.innerHTML = `
                <span class="chat-session-title">${escapeHtml(session.title || 'Yeni sohbet')}</span>
                <span class="chat-session-meta">${lastMessage ? escapeHtml(lastMessage.message) : 'Boş sohbet'} · ${time}</span>
            `;
            button.addEventListener('click', () => switchChatSession(session.id));

            menu.className = 'chat-session-menu';
            menuButton.type = 'button';
            menuButton.className = 'chat-session-menu-button';
            menuButton.title = 'Sohbet seçenekleri';
            menuButton.innerHTML = '<span class="material-symbols-outlined text-[16px]" data-icon="more_horiz">more_horiz</span>';
            menuButton.addEventListener('click', (event) => {
                event.stopPropagation();
                document.querySelectorAll('.chat-session-menu-open').forEach(item => {
                    if (item !== menu) item.classList.remove('chat-session-menu-open');
                });
                menu.classList.toggle('chat-session-menu-open');
            });

            deleteButton.type = 'button';
            deleteButton.className = 'chat-session-delete-button';
            deleteButton.textContent = 'Sohbeti sil';
            deleteButton.addEventListener('click', (event) => {
                event.stopPropagation();
                menu.classList.remove('chat-session-menu-open');
                deleteChatSession(session.id);
            });

            menu.appendChild(menuButton);
            menu.appendChild(deleteButton);
            li.appendChild(button);
            li.appendChild(menu);
            chatSessionsList.appendChild(li);
        });
    }

    function renderActiveChat() {
        if (!chatHistory) return;
        chatHistory.innerHTML = chatTemplate;
        const session = currentChatSession();
        if (!session) return;
        session.messages.forEach(item => {
            addMessageToChat(item.role, item.message, item.isError, {
                persist: false,
                timestamp: item.timestamp,
            });
        });
    }

    loadChatSessions();
    renderChatSessions();

    // Setup Check on Load
    if (sessionStorage.getItem('setupCompleted') === SETUP_VERSION) {
        hideSetupModal();
    }

    function hideSetupModal() {
        if(setupModal) {
            setupModal.classList.remove('opacity-100');
            setupModal.classList.add('opacity-0', 'pointer-events-none');
            setupModalContent.classList.remove('scale-100');
            setupModalContent.classList.add('scale-95');
        }
        if(mainApp) {
            mainApp.classList.remove('opacity-0', 'pointer-events-none');
            mainApp.classList.add('opacity-100');
        }
    }

    if (btnAcceptModels) {
        btnAcceptModels.addEventListener('click', () => {
            if (ws && ws.readyState === WebSocket.OPEN) {
                const selectedModelInfo = latestModelSetup?.models?.find(model => model.name === selectedSetupModel);
                ws.send(JSON.stringify({
                    action: 'start_setup',
                    llm_model: selectedSetupModel || modalRecLlm.textContent
                }));
                
                btnAcceptModels.disabled = true;
                btnAcceptModels.classList.add('opacity-50', 'cursor-not-allowed');
                btnAcceptModels.textContent = selectedModelInfo?.installed ? "Seçiliyor..." : "İndiriliyor...";
                
                // Reset progress bar in case of previous error
                const progressText = document.getElementById('download-progress-text');
                const progressFill = document.getElementById('download-progress-fill');
                if (progressText && progressFill) {
                    progressText.style.color = "inherit";
                    progressFill.classList.remove('bg-error');
                    progressFill.classList.add('bg-primary');
                    progressFill.style.width = "0%";
                    progressText.textContent = "Jarvis hazırlanıyor...";
                }
                
                document.getElementById('download-progress-container').style.display = 'block';
            } else {
                hideSetupModal();
                sessionStorage.setItem('setupCompleted', SETUP_VERSION);
            }
        });
    }

    // WebSocket Kurulumu
    let ws;
    let reconnectInterval = 2000;
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    function connectWebSocket() {
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            updateHeaderStatus("Bağlandı", "success");
            console.log("WebSocket connected.");
            
            // Update the static welcome message upon connection
            const welcomeText = document.getElementById('welcome-text');
            const welcomeTime = document.getElementById('welcome-time');
            if (welcomeText) welcomeText.textContent = "Jarvis hazır. Sesli komut bekliyor; istersen yazılı komut da gönderebilirsin.";
            if (welcomeTime) {
                const now = new Date();
                welcomeTime.textContent = `JARVIS // ${now.toLocaleTimeString('tr-TR', { hour12: false })}`;
            }
        };

        ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            handleServerMessage(msg);
        };

        ws.onclose = () => {
            updateHeaderStatus("Bağlantı Koptu", "error");
            console.log("WebSocket disconnected. Reconnecting...");
            setTimeout(connectWebSocket, reconnectInterval);
        };

        ws.onerror = (error) => {
            console.error("WebSocket error:", error);
        };
    }

    // Chat Input Logic
    function sendChatMessage() {
        if (!chatInput || !ws || ws.readyState !== WebSocket.OPEN) return;
        const text = chatInput.value.trim();
        if (text) {
            ws.send(JSON.stringify({
                action: 'chat',
                text: text
            }));
            chatInput.value = '';
            // addMessageToChat('USER', text); // Sunucudan 'transcript' mesajı geldiğinde eklenecek, çift olmaması için burada eklemiyoruz.
        }
    }

    if (btnSendChat) {
        btnSendChat.addEventListener('click', sendChatMessage);
    }
    if (btnNewChat) {
        btnNewChat.addEventListener('click', startNewChat);
    }
    if (btnClearChats) {
        btnClearChats.addEventListener('click', clearAllChats);
    }
    if (chatInput) {
        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                sendChatMessage();
            }
        });
    }
    document.addEventListener('click', (event) => {
        if (!event.target.closest('.chat-session-menu')) {
            document.querySelectorAll('.chat-session-menu-open').forEach(item => {
                item.classList.remove('chat-session-menu-open');
            });
        }
    });

    function handleServerMessage(msg) {
        if (msg.type === 'status') {
            const friendlyStatus = formatStatus(msg.data);
            updateOrbState(msg.data);
            updateHeaderStatus(friendlyStatus, "info");
            micStatusText.textContent = friendlyStatus;
        } 
        else if (msg.type === 'transcript') {
            addMessageToChat('USER', msg.data);
        } 
        else if (msg.type === 'response') {
            addMessageToChat('SYSTEM', msg.data);
        } 
        else if (msg.type === 'error') {
            updateHeaderStatus("Hata", "error");
            addMessageToChat('SYSTEM', `[HATA] ${msg.data}`, true);
        }
        else if (msg.type === 'system_info') {
            updateSystemInfo(msg.data);
        }
        else if (msg.type === 'download_progress') {
            const data = msg.data;
            const progressFill = document.getElementById('download-progress-fill');
            const progressText = document.getElementById('download-progress-text');
            
            if (data.status === 'success') {
                hideSetupModal();
                sessionStorage.setItem('setupCompleted', SETUP_VERSION);
            } else if (data.percent === -1) {
                progressText.textContent = data.status;
                progressText.classList.add('text-error');
                progressFill.classList.remove('bg-primary');
                progressFill.classList.add('bg-error');
                
                btnAcceptModels.disabled = false;
                btnAcceptModels.classList.remove('opacity-50', 'cursor-not-allowed');
                btnAcceptModels.textContent = "Tekrar dene";
            } else {
                progressFill.style.width = `${data.percent}%`;
                progressText.textContent = `${data.status} (%${data.percent})`;
            }
        }
        else if (msg.type === 'latency') {
            console.log("Latency metrics:", msg.data);
        }
    }

    function updateOrbState(state) {
        if(!orbContainer) return;
        
        orbContainer.classList.remove('mic-listening', 'mic-recording', 'mic-processing', 'mic-speaking');
        
        const s = state.toLowerCase();
        if (s.includes('dinliyor')) {
            orbContainer.classList.add('mic-recording');
        } else if (s.includes('dinlemeye hazır')) {
            orbContainer.classList.add('mic-listening');
        } else if (s.includes('düşünüyor')) {
            orbContainer.classList.add('mic-processing');
        } else if (s.includes('uyguluyor') || s.includes('hazır')) {
            orbContainer.classList.add('mic-speaking');
        }
    }

    function updateHeaderStatus(text, type) {
        if(!headerStatusText || !headerStatusIndicator) return;
        headerStatusText.textContent = text;
        
        headerStatusIndicator.className = 'w-2 h-2 rounded-full';
        if(type === 'success') {
            headerStatusIndicator.classList.add('bg-primary-fixed', 'drop-shadow-[0_0_5px_rgba(180,235,255,0.8)]');
        } else if(type === 'error') {
            headerStatusIndicator.classList.add('bg-error', 'drop-shadow-[0_0_5px_rgba(255,180,171,0.8)]');
        } else {
            headerStatusIndicator.classList.add('bg-primary', 'drop-shadow-[0_0_5px_rgba(0,212,255,0.8)]');
        }
    }

    function updateSystemInfo(data) {
        // RAM Güncelle
        if (data.recommendations) {
            const recs = data.recommendations;
            const total = recs.total_ram_mb;
            const available = recs.available_ram_mb;
            const used = total - available;
            
            let percent = 0;
            if (total > 0) percent = Math.round((used / total) * 100);
            
            if(ramPercentage) ramPercentage.textContent = `${percent}%`;
            if(ramFill) ramFill.style.width = `${percent}%`;
            if(ramDetails) ramDetails.textContent = `Kullanılan: ${(used/1024).toFixed(1)} GB / Toplam: ${(total/1024).toFixed(1)} GB`;

            // RAM renk uyarısı
            if(ramFill) {
                ramFill.classList.remove('bg-primary', 'bg-tertiary-container', 'bg-error');
                if(recs.pressure === 'high') ramFill.classList.add('bg-error');
                else if(recs.pressure === 'medium') ramFill.classList.add('bg-tertiary-container');
                else ramFill.classList.add('bg-primary');
            }

            // Setup Modal'ı İlk Kez Göster
            if (sessionStorage.getItem('setupCompleted') !== SETUP_VERSION && setupModal) {
                modalRamTotal.textContent = `${total} MB`;
                modalRamAvail.textContent = `${available} MB`;
                modalRecWhisper.textContent = recs.whisper_model;
                modalRecLlm.textContent = recs.llm_model;
            }
        }

        if (data.model_setup) {
            latestModelSetup = data.model_setup;
            renderModelOptions(data.model_setup);
        }
    }

    function renderModelOptions(setup) {
        if (!modelOptions) return;
        const models = setup.models || [];
        if (!models.length) {
            modelOptions.innerHTML = '<div class="bg-surface-container/50 border border-outline-variant/30 rounded-xl p-4 text-on-surface-variant font-mono-data text-[12px]">Model listesi alınamadı.</div>';
            return;
        }

        if (!selectedSetupModel || !models.some(model => model.name === selectedSetupModel)) {
            selectedSetupModel = setup.current_model && setup.current_model !== 'auto'
                ? setup.current_model
                : setup.recommended_model;
        }

        if (!models.some(model => model.name === selectedSetupModel)) {
            selectedSetupModel = setup.recommended_model || models[0].name;
        }

        const selectedModel = models.find(model => model.name === selectedSetupModel);
        if (modalRecLlm) {
            modalRecLlm.textContent = setup.recommended_model || selectedSetupModel;
        }
        if (modelRecommendationText) {
            modelRecommendationText.textContent = setup.recommendation_reason || 'RAM durumuna göre öneri hazırlanıyor.';
        }
        if (btnAcceptModels && selectedModel && !btnAcceptModels.disabled) {
            btnAcceptModels.textContent = selectedModel.installed ? 'Bu modeli kullan' : 'Seçili modeli indir';
        }

        modelOptions.innerHTML = '';
        models.forEach(model => {
            const isSelected = model.name === selectedSetupModel;
            const card = document.createElement('button');
            card.type = 'button';
            card.className = [
                'model-option',
                isSelected ? 'model-option-selected' : '',
                model.recommended ? 'model-option-recommended' : ''
            ].filter(Boolean).join(' ');
            card.dataset.model = model.name;

            const installIcon = model.installed ? 'check_circle' : 'download';
            const installText = model.installed ? 'Yüklü' : 'İndirilecek';
            const ramText = model.min_ram_mb >= 1024 ? `${Math.round(model.min_ram_mb / 1024)} GB+ RAM` : `${model.min_ram_mb} MB+ RAM`;
            const recommendedBadge = model.recommended ? '<span class="model-badge model-badge-recommended">RAM önerisi</span>' : '';
            const currentBadge = model.current ? '<span class="model-badge">Seçili ayar</span>' : '';

            card.innerHTML = `
                <div class="flex items-start justify-between gap-3">
                    <div class="min-w-0">
                        <div class="flex flex-wrap items-center gap-2 mb-2">
                            <span class="font-headline-md text-[16px] text-on-surface">${escapeHtml(model.label)}</span>
                            ${recommendedBadge}
                            ${currentBadge}
                        </div>
                        <p class="font-mono-data text-[12px] text-on-surface-variant/80 leading-relaxed">${escapeHtml(model.description)}</p>
                    </div>
                    <span class="material-symbols-outlined model-option-icon" data-icon="${installIcon}">${installIcon}</span>
                </div>
                <div class="mt-4 flex flex-wrap items-center gap-2 font-mono-data text-[11px] text-on-surface-variant">
                    <span class="model-chip">${escapeHtml(model.name)}</span>
                    <span class="model-chip">${escapeHtml(model.size)}</span>
                    <span class="model-chip">${ramText}</span>
                    <span class="model-chip">${escapeHtml(model.tone)}</span>
                    <span class="model-chip ${model.installed ? 'model-chip-installed' : ''}">${installText}</span>
                </div>
            `;

            card.addEventListener('click', () => {
                selectedSetupModel = model.name;
                renderModelOptions(setup);
            });
            modelOptions.appendChild(card);
        });
    }

    function addMessageToChat(role, message, isError = false, options = {}) {
        if(!chatHistory) return;
        
        const timestamp = options.timestamp || Date.now();
        const now = new Date(timestamp);
        const timeStr = now.toLocaleTimeString('tr-TR', { hour12: false });
        const wrapper = document.createElement('div');

        if (role === 'USER') {
            wrapper.className = 'self-end max-w-[70%] flex flex-col gap-1 mt-4';
            wrapper.innerHTML = `
                <div class="border-r border-secondary/40 bg-gradient-to-l from-secondary/5 to-transparent p-5 rounded-l-xl rounded-tr-sm shadow-[inset_-2px_0_10px_rgba(209,188,255,0.05)] text-on-surface">
                    <p>${escapeHtml(message)}</p>
                </div>
                <span class="self-end font-mono-data text-mono-data text-[10px] text-on-surface-variant/50 px-2">SEN // ${timeStr}</span>
            `;
        } else {
            // SYSTEM
            wrapper.className = 'self-start max-w-[80%] flex flex-col gap-1 mt-4';
            const icon = isError ? 'warning' : 'neurology';
            const titleColor = isError ? 'text-error' : 'text-primary';
            const shadowColor = isError ? 'rgba(255,180,171,0.5)' : 'rgba(0,212,255,0.5)';
            const msgColor = isError ? 'text-error' : 'text-on-surface/90';
            const borderColor = isError ? 'border-error/50' : 'border-primary/50';
            const gradientFrom = isError ? 'from-error/10' : 'from-primary/10';

            wrapper.innerHTML = `
                <div class="border-l ${borderColor} bg-gradient-to-r ${gradientFrom} to-transparent p-5 rounded-r-xl rounded-tl-sm shadow-[inset_2px_0_15px_rgba(0,0,0,0.1)] backdrop-blur-sm">
                    <div class="flex items-center gap-2 mb-3">
                        <span class="material-symbols-outlined ${titleColor} text-[16px]" data-icon="${icon}">${icon}</span>
                        <span class="font-headline-md text-headline-md text-[14px] ${titleColor} tracking-widest drop-shadow-[0_0_5px_${shadowColor}]">Jarvis</span>
                    </div>
                    <p class="${msgColor} leading-relaxed font-mono-data text-mono-data text-[13px]">
                        ${escapeHtml(message)}
                    </p>
                </div>
                <span class="self-start font-mono-data text-mono-data text-[10px] ${titleColor}/50 px-2">JARVIS // ${timeStr}</span>
            `;
        }

        chatHistory.appendChild(wrapper);
        chatHistory.scrollTop = chatHistory.scrollHeight;

        if (options.persist !== false) {
            persistChatMessage(role, message, isError, timestamp);
        }
    }

    // Başlat
    renderActiveChat();
    connectWebSocket();
});
