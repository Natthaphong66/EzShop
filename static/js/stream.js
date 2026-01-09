
/**
 * StreamManager handles all logic for the live stream (Agora, UI, Chat)
 */
class StreamManager {
    constructor(config) {
        this.config = config;
        this.client = AgoraRTC.createClient({ mode: "rtc", codec: "vp8" });
        this.localTracks = {
            videoTrack: null,
            audioTrack: null
        };
        this.previewTracks = {
            videoTrack: null,
            audioTrack: null
        };
        this.audioLevelInterval = null;
        this.cameraEnabled = true;
        this.micEnabled = true;

        this.init();
    }

    init() {
        console.log("StreamManager Init:", this.config);
        
        // Handle Autoplay policy
        AgoraRTC.onAudioAutoplayFailed = () => {
             this.showAutoplayButton();
        };

        if (this.config.isHost) {
            this.initHost();
        } else {
            this.initViewer();
        }

        this.setupChat();
    }

    /* ===============================
       Host Logic
    ================================ */
    async initHost() {
        await this.loadDevices();
        this.setupDeviceModalListeners();
    }

    async loadDevices() {
        try {
            // Request permissions
            const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
            stream.getTracks().forEach(track => track.stop());

            const devices = await AgoraRTC.getDevices();
            const cameras = devices.filter(d => d.kind === "videoinput");
            const mics = devices.filter(d => d.kind === "audioinput");

            this.populateSelect("camera-select", cameras, "Camera");
            this.populateSelect("mic-select", mics, "Microphone");

            if (cameras.length > 0 && mics.length > 0) {
                await this.startPreview(cameras[0].deviceId, mics[0].deviceId);
            }
        } catch (err) {
            console.error("Error loading devices:", err);
            alert("❌ ไม่สามารถเข้าถึงกล้องหรือไมค์ได้ กรุณาอนุญาตการใช้งาน");
        }
    }

    populateSelect(elementId, devices, labelPrefix) {
        const select = document.getElementById(elementId);
        if (!select) return;
        select.innerHTML = "";
        devices.forEach((dev, i) => {
            const option = document.createElement("option");
            option.value = dev.deviceId;
            option.textContent = dev.label || `${labelPrefix} ${i + 1}`;
            select.appendChild(option);
        });
    }

    setupDeviceModalListeners() {
        const cameraSelect = document.getElementById("camera-select");
        const micSelect = document.getElementById("mic-select");
        const startBtn = document.getElementById("btn-start-stream");

        if (cameraSelect) {
            cameraSelect.addEventListener("change", () => this.updatePreview());
        }
        if (micSelect) {
            micSelect.addEventListener("change", () => this.updatePreview());
        }
        if (startBtn) {
            startBtn.addEventListener("click", () => this.startStream());
        }
        
        // Host Controls
        document.getElementById("btn-camera")?.addEventListener("click", () => this.toggleCamera());
        document.getElementById("btn-mic")?.addEventListener("click", () => this.toggleMic());
    }

    async updatePreview() {
        const cameraId = document.getElementById("camera-select").value;
        const micId = document.getElementById("mic-select").value;
        await this.startPreview(cameraId, micId);
    }

    async startPreview(cameraId, micId) {
        try {
            this.stopPreviewTracks();

            this.previewTracks.videoTrack = await AgoraRTC.createCameraVideoTrack({
                cameraId,
                encoderConfig: "720p_1"
            });

            this.previewTracks.audioTrack = await AgoraRTC.createMicrophoneAudioTrack({
                microphoneId: micId
            });

            document.getElementById("preview-loading")?.classList.add("hidden");
            this.previewTracks.videoTrack.play("preview-player");
            
            this.startAudioLevelMonitor(this.previewTracks.audioTrack);
            
            const startBtn = document.getElementById("btn-start-stream");
            if(startBtn) startBtn.disabled = false;

        } catch (err) {
            console.error("Preview error:", err);
        }
    }

    stopPreviewTracks() {
        if (this.previewTracks.videoTrack) {
            this.previewTracks.videoTrack.stop();
            this.previewTracks.videoTrack.close();
            this.previewTracks.videoTrack = null;
        }
        if (this.previewTracks.audioTrack) {
            this.previewTracks.audioTrack.stop();
            this.previewTracks.audioTrack.close();
            this.previewTracks.audioTrack = null;
        }
    }

    startAudioLevelMonitor(audioTrack) {
        if (this.audioLevelInterval) clearInterval(this.audioLevelInterval);
        
        this.audioLevelInterval = setInterval(() => {
            if (audioTrack) {
                const level = audioTrack.getVolumeLevel();
                const fill = document.getElementById("audio-level-fill");
                if (fill) {
                    fill.style.width = `${level * 100}%`;
                }
            }
        }, 100);
    }

    async startStream() {
        console.log("🚀 Starting stream...");
        document.getElementById("device-modal")?.classList.add("hidden");
        document.getElementById("loading-overlay")?.classList.remove("hidden");

        try {
            const tokenData = await this.fetchToken();
            
            await this.client.join(
                tokenData.app_id,
                this.config.channelName,
                tokenData.token,
                this.config.userUid
            );

            // Move tracks from preview to local
            this.localTracks.videoTrack = this.previewTracks.videoTrack;
            this.localTracks.audioTrack = this.previewTracks.audioTrack;
            
            // Clear preview references so stopPreviewTracks doesn't kill them
            this.previewTracks.videoTrack = null;
            this.previewTracks.audioTrack = null;

            if(this.audioLevelInterval) clearInterval(this.audioLevelInterval);
            
            await this.client.publish([this.localTracks.audioTrack, this.localTracks.videoTrack]);
            
            this.localTracks.videoTrack.play("local-player");
            document.getElementById("loading-overlay")?.classList.add("hidden");

        } catch (err) {
            console.error("Stream error:", err);
            alert(err.message || "Error starting stream");
            document.getElementById("device-modal")?.classList.remove("hidden");
            document.getElementById("loading-overlay")?.classList.add("hidden");
        }
    }

    /* ===============================
       Viewer Logic
    ================================ */
    async initViewer() {
        console.log("👀 Initializing viewer...");
        try {
            const tokenData = await this.fetchToken();
            
            this.client.on("user-published", async (user, mediaType) => {
                await this.client.subscribe(user, mediaType);
                if (mediaType === "video") {
                    user.videoTrack.play("local-player");
                    document.getElementById("loading-overlay")?.classList.add("hidden");
                }
                if (mediaType === "audio") {
                    user.audioTrack.play();
                }
            });

            this.client.on("user-unpublished", (user) => {
                console.log("User unpublished:", user.uid);
            });

            await this.client.join(
                tokenData.app_id,
                this.config.channelName,
                tokenData.token,
                this.config.userUid
            );

            console.log("✅ Viewer joined");

        } catch (err) {
            console.error("Viewer error:", err);
            this.showConnectionError();
        }
    }

    /* ===============================
       Shared Logic
    ================================ */
    async fetchToken() {
        const res = await fetch(this.config.urls.token, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": this.config.csrfToken
            },
            body: JSON.stringify({
                channel_name: this.config.channelName,
                uid: this.config.userUid,
                role: this.config.isHost ? 1 : 2
            })
        });

        if (!res.ok) throw new Error("Token API error");
        return res.json();
    }

    toggleCamera() {
        if (this.localTracks.videoTrack) {
            this.cameraEnabled = !this.cameraEnabled;
            this.localTracks.videoTrack.setEnabled(this.cameraEnabled);
            this.updateControlUI("camera", this.cameraEnabled);
        }
    }

    toggleMic() {
        if (this.localTracks.audioTrack) {
            this.micEnabled = !this.micEnabled;
            this.localTracks.audioTrack.setEnabled(this.micEnabled);
            this.updateControlUI("mic", this.micEnabled);
        }
    }

    updateControlUI(type, isEnabled) {
        const btn = document.getElementById(`btn-${type}`);
        const iconOn = document.getElementById(`icon-${type}-on`);
        const iconOff = document.getElementById(`icon-${type}-off`);
        
        if (!btn || !iconOn || !iconOff) return;

        if (isEnabled) {
            btn.classList.remove("bg-red-500");
            btn.classList.add("bg-white/20");
            iconOn.classList.remove("hidden");
            iconOff.classList.add("hidden");
        } else {
            btn.classList.add("bg-red-500");
            btn.classList.remove("bg-white/20");
            iconOn.classList.add("hidden");
            iconOff.classList.remove("hidden");
        }
    }

    showAutoplayButton() {
        const container = document.querySelector("#local-player");
        if(document.getElementById("autoplay-btn")) return;

        const btn = document.createElement("button");
        btn.id = "autoplay-btn";
        btn.innerHTML = `
            <svg class="w-6 h-6 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z"/>
            </svg>
            คลิกเพื่อเปิดเสียง
        `;
        btn.className = "absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 z-30 px-6 py-3 bg-red-600 hover:bg-red-700 text-white font-semibold rounded-lg flex items-center transition-colors";
        
        container.appendChild(btn);
        
        btn.onclick = () => {
            this.client.remoteUsers.forEach(user => {
                if (user.audioTrack) user.audioTrack.play();
            });
            btn.remove();
        };
    }

    showConnectionError() {
        const overlay = document.getElementById("loading-overlay");
        if(overlay) {
            overlay.classList.remove("hidden");
            overlay.innerHTML = `
                <svg class="w-16 h-16 text-red-500 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
                </svg>
                <p class="text-white text-lg font-medium">ไม่สามารถเชื่อมต่อได้</p>
                <p class="text-slate-400 text-sm mt-2">กรุณาลองใหม่อีกครั้ง</p>
            `;
        }
    }

    /* ===============================
       Chat Logic
    ================================ */
    setupChat() {
        const input = document.getElementById("chat-input");
        const btn = document.querySelector("#chat-input + button"); // Send button

        if (input) {
            input.addEventListener("keypress", (e) => {
                if (e.key === "Enter") this.sendMessage();
            });
        }
        if (btn) {
            btn.addEventListener("click", () => this.sendMessage());
        }
    }

    sendMessage() {
        const input = document.getElementById("chat-input");
        const message = input.value.trim();
        
        if (message) {
            this.addChatMessage(this.config.currentUsername, message);
            input.value = "";
            // TODO: Here you would emit the message to other users via WebSocket or Agora RTM
        }
    }

    addChatMessage(username, text) {
        const chatMessages = document.getElementById("chat-messages");
        
        // Remove welcome message
        const welcomeMsg = chatMessages.querySelector(".text-center");
        if (welcomeMsg) welcomeMsg.remove();
        
        const now = new Date();
        const time = now.getHours().toString().padStart(2, '0') + ':' + 
                    now.getMinutes().toString().padStart(2, '0');
        
        const msgEl = document.createElement("div");
        msgEl.className = "flex items-start gap-2 text-sm";
        msgEl.innerHTML = `
            <span class="text-slate-400 text-xs">${time}</span>
            <span class="font-semibold text-red-600">${username}:</span>
            <span class="text-slate-700">${text}</span>
        `;
        
        chatMessages.appendChild(msgEl);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}
