// SecureVote Frontend Logic & Interactions

// Keep track of blockchain data globally on the results page
let globalBlockchainData = [];

// --- Page Setup & Routing Logic ---
document.addEventListener("DOMContentLoaded", () => {
    // If we are on the results page, load the data immediately
    if (document.getElementById("blockchain-chain-container")) {
        loadResultsData();
    }
});

// --- Voting Page Interactions ---

// Select Candidate Card
function selectCandidate(card, candidateName) {
    // Remove selected class from all cards
    const cards = document.querySelectorAll(".candidate-card");
    cards.forEach(c => c.classList.remove("selected"));
    
    // Add selected class to the clicked card
    card.classList.add("selected");
    
    // Set hidden input value
    const input = document.getElementById("selected-candidate-input");
    input.value = candidateName;
    
    // Visual validation update
    validateFormFields();
}

// Validate DNI in real-time
function validateDniInput(input) {
    // Clean input: only numbers allowed
    input.value = input.value.replace(/\D/g, '');
    
    const valMsg = document.getElementById("dni-validation-message");
    
    if (input.value.length === 0) {
        valMsg.textContent = "";
        valMsg.className = "input-validation-msg";
        return false;
    }
    
    if (input.value.length < 8) {
        valMsg.textContent = "El DNI debe tener exactamente 8 dígitos.";
        valMsg.className = "input-validation-msg error";
        return false;
    }

    if (input.value.length > 8) {
        valMsg.textContent = "El DNI debe tener exactamente 8 dígitos (sobran caracteres).";
        valMsg.className = "input-validation-msg error";
        return false;
    }
    
    valMsg.textContent = "DNI válido para consulta.";
    valMsg.className = "input-validation-msg success";
    return true;
}

// Validate all form fields prior to enabling submit
function validateFormFields() {
    const candidate = document.getElementById("selected-candidate-input").value;
    const dni = document.getElementById("dni-input").value;
    const btn = document.getElementById("btn-votar");
    
    if (candidate && dni.length === 8) {
        btn.disabled = false;
        return true;
    }
    return false;
}

// Handle Form Submission (AJAX/Fetch)
async function submitVote(event) {
    event.preventDefault();
    
    const dni = document.getElementById("dni-input").value.trim();
    const candidate = document.getElementById("selected-candidate-input").value;
    const btn = document.getElementById("btn-votar");
    const loader = document.getElementById("btn-loader");
    
    if (!dni || !candidate) {
        showStatusModal(false, "Campos Incompletos", "Por favor, selecciona un candidato e ingresa tu DNI.");
        return;
    }
    
    // Show loading state
    btn.disabled = true;
    loader.classList.remove("hidden");
    
    try {
        const response = await fetch('/api/votar', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ dni: dni, candidato: candidate })
        });
        
        const result = await response.json();
        
        // Hide loading state
        loader.classList.add("hidden");
        
        if (result.success) {
            // Usamos el hash REAL devuelto por el servidor (el que quedó
            // efectivamente guardado en votos_blockchain), no uno inventado
            // en el cliente, para que el hash mostrado sea verificable.
            showStatusModal(true, "¡Voto Registrado!", result.message, result.hash || "");
        } else {
            showStatusModal(false, "Error al Votar", result.message);
        }
        
    } catch (error) {
        loader.classList.add("hidden");
        btn.disabled = false;
        showStatusModal(false, "Fallo de Conexión", "No se pudo comunicar con el servidor SecureVote. Revisa tu conexión.");
    }
}

// --- Results Page API Interactions ---

// Fetch data from Flask backend API and populate the dashboard
async function loadResultsData() {
    const barChartContainer = document.getElementById("bar-chart-container");
    const chainContainer = document.getElementById("blockchain-chain-container");
    const tableBody = document.getElementById("audit-log-table-body");
    
    try {
        const response = await fetch('/api/blockchain');
        const data = await response.json();
        
        if (!data.success) {
            throw new Error(data.message);
        }
        
        globalBlockchainData = data.blockchain;
        
        // 1. Update Statistics Counters
        document.getElementById("stat-registered-count").textContent = data.stats.total_registered;
        document.getElementById("stat-voted-count").textContent = data.stats.total_voted;
        document.getElementById("stat-participation-rate").textContent = data.stats.participation_rate + "%";
        
        // 2. Render Custom Interactive Chart
        // NOTA: el denominador de cada porcentaje debe ser la suma real de
        // votos registrados en la blockchain (bloques), no data.stats.total_voted
        // (que cuenta ha_votado=1 en la tabla votantes). Ambos números pueden
        // desincronizarse si se reinicia el estado de un votante para pruebas
        // después de que ya generó un bloque de voto real.
        const totalVotosBlockchain = data.candidates.reduce((sum, c) => sum + c.votos, 0);
        renderChart(data.candidates, totalVotosBlockchain);
        
        // 3. Render Blockchain Visual Ledger
        renderBlockchain(data.blockchain);
        
        // 4. Render Audit Logs Table
        renderAuditLogs(data.audit);
        
    } catch (error) {
        console.error("Error loading results data:", error);
        
        const errorHtml = `<div class="chart-loading text-center py-4"><span style="color: var(--color-error)">❌ Error al cargar datos: ${error.message}</span></div>`;
        if (barChartContainer) barChartContainer.innerHTML = errorHtml;
        if (chainContainer) chainContainer.innerHTML = errorHtml;
        if (tableBody) tableBody.innerHTML = `<tr><td colspan="3" class="text-center py-4" style="color: var(--color-error)">Error al cargar registros.</td></tr>`;
    }
}

// Render Candidates Custom Bar Chart
function renderChart(candidates, totalVotes) {
    const container = document.getElementById("bar-chart-container");
    if (!container) return;
    
    if (candidates.length === 0) {
        container.innerHTML = `<div class="chart-loading"><p>No hay votos registrados aún en este escrutinio.</p></div>`;
        return;
    }
    
    container.innerHTML = "";
    
    candidates.forEach(cand => {
        const percentage = totalVotes > 0 ? ((cand.votos / totalVotes) * 100).toFixed(1) : 0;
        
        const row = document.createElement("div");
        row.className = "chart-row";
        row.innerHTML = `
            <div class="chart-row-header">
                <div class="chart-candidate-info">
                    <div class="chart-avatar">${cand.nombre[0]}</div>
                    <div>
                        <strong>${cand.nombre}</strong>
                        <span class="chart-party-tag">${cand.partido}</span>
                    </div>
                </div>
                <div>
                    <span class="chart-votes-val">${cand.votos} voto${cand.votos !== 1 ? 's' : ''}</span>
                    <span class="chart-votes-pct">(${percentage}%)</span>
                </div>
            </div>
            <div class="chart-bar-bg">
                <div class="chart-bar-fill" id="bar-fill-${cand.id_candidato}"></div>
            </div>
        `;
        
        container.appendChild(row);
        
        // Set the width in a micro-task to trigger the CSS transition slide effect beautifully
        setTimeout(() => {
            const bar = document.getElementById(`bar-fill-${cand.id_candidato}`);
            if (bar) bar.style.width = `${percentage}%`;
        }, 100);
    });
}

// Render Blockchain Visual Ledger in Horizontal Scroller
function renderBlockchain(blockchain) {
    const container = document.getElementById("blockchain-chain-container");
    if (!container) return;
    
    if (blockchain.length === 0) {
        container.innerHTML = `
            <div class="blockchain-loading">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <rect x="2" y="2" width="20" height="20" rx="4" ry="4"/>
                    <path d="M12 2v20M2 12h20"/>
                </svg>
                <p>La Blockchain está vacía. Emite el primer voto seguro para crear el bloque génesis.</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = "";
    
    blockchain.forEach((block, index) => {
        // Create block card
        const card = document.createElement("div");
        card.className = "block-card";
        card.id = `block-card-${block.id_voto}`;
        card.setAttribute("onclick", `inspectBlock(${block.id_voto})`);
        card.innerHTML = `
            <div class="block-card-header">
                <span class="block-number">Bloque #${block.id_voto}</span>
                <span class="block-chain-status" id="block-status-dot-${block.id_voto}"></span>
            </div>
            <div class="block-card-body">
                <div class="block-recipient">
                    <span class="recipient-label">Candidato</span>
                    <span class="recipient-name">${block.candidato_nombre}</span>
                </div>
                <div class="block-hash-preview" title="Firma: ${block.hash_voto}">
                    <span>Hash: ${block.hash_voto.substring(0, 16)}...</span>
                </div>
            </div>
            <div class="block-card-footer">
                <span>PostgreSQL DB</span>
                <span>${block.timestamp ? block.timestamp.substring(11, 19) : ''}</span>
            </div>
        `;
        
        container.appendChild(card);
        
        // Add connector arrow if not the last block
        if (index < blockchain.length - 1) {
            const arrow = document.createElement("div");
            arrow.className = "chain-link";
            arrow.id = `chain-link-${block.id_voto}`;
            arrow.innerHTML = `
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="5" y1="12" x2="19" y2="12"></line>
                    <polyline points="12 5 19 12 12 19"></polyline>
                </svg>
            `;
            container.appendChild(arrow);
        }
    });
}

// Render Audit Logs Table
function renderAuditLogs(logs) {
    const tableBody = document.getElementById("audit-log-table-body");
    const badge = document.getElementById("audit-log-badge");
    if (!tableBody) return;
    
    if (logs.length === 0) {
        tableBody.innerHTML = `<tr><td colspan="3" class="text-center py-4">No hay registros de auditoría disponibles.</td></tr>`;
        badge.textContent = "0 Registros";
        return;
    }
    
    tableBody.innerHTML = "";
    badge.textContent = `${logs.length} Registro${logs.length !== 1 ? 's' : ''}`;
    
    logs.forEach(log => {
        const row = document.createElement("tr");
        row.innerHTML = `
            <td class="col-id">${log.id_log}</td>
            <td>${escapeHtml(log.accion)}</td>
            <td class="col-date">${log.fecha}</td>
        `;
        tableBody.appendChild(row);
    });
}

// --- Blockchain Front-End Integrity Validator ---
async function runLedgerValidation() {
    if (globalBlockchainData.length === 0) return;
    
    const btn = document.getElementById("btn-validate-blockchain");
    const seal = document.getElementById("validator-seal");
    const statusText = document.getElementById("validator-status-text");
    const statusDesc = document.getElementById("validator-status-desc");
    const metricsBox = document.getElementById("validator-metrics-box");
    const metricsCount = document.getElementById("validation-blocks-count");
    
    btn.disabled = true;
    statusText.textContent = "Auditando Ledger...";
    statusDesc.textContent = "Validando matemáticamente el encadenamiento del ledger block por block...";
    
    // Clear previous verification styles
    const blocks = document.querySelectorAll(".block-card");
    const arrows = document.querySelectorAll(".chain-link");
    blocks.forEach(b => b.classList.remove("valid", "invalid"));
    arrows.forEach(a => a.classList.remove("verified"));
    seal.className = "validator-seal-container";
    
    let isValid = true;
    let verifiedCount = 0;
    
    // Step by step verification scan animation
    for (let i = 0; i < globalBlockchainData.length; i++) {
        const currentBlock = globalBlockchainData[i];
        const blockCard = document.getElementById(`block-card-${currentBlock.id_voto}`);
        const statusDot = document.getElementById(`block-status-dot-${currentBlock.id_voto}`);
        
        await sleep(250); // Scan lag effect for futuristic high-fidelity styling!
        
        let blockValid = true;
        
        if (i > 0) {
            const prevBlock = globalBlockchainData[i - 1];
            // Check if current block's hash_anterior strictly matches previous block's hash_voto
            if (currentBlock.hash_anterior !== prevBlock.hash_voto) {
                blockValid = false;
                isValid = false;
            }
        }
        
        if (blockValid) {
            if (blockCard) blockCard.classList.add("valid");
            verifiedCount++;
            metricsCount.textContent = `${verifiedCount} Bloques Verificados`;
            metricsBox.classList.remove("hidden");
            
            // Light up the connecting arrow
            if (i > 0) {
                const prevBlock = globalBlockchainData[i - 1];
                const arrow = document.getElementById(`chain-link-${prevBlock.id_voto}`);
                if (arrow) arrow.classList.add("verified");
            }
        } else {
            if (blockCard) blockCard.classList.add("invalid");
            break; // Stop at first corrupt block
        }
    }
    
    // Show final status
    if (isValid) {
        seal.className = "validator-seal-container valid";
        statusText.textContent = "Estructura Válida";
        statusText.style.color = "var(--color-success)";
        statusDesc.textContent = "¡Verificación Exitosa! La cadena inmutable está al 100% íntegra. Las firmas criptográficas encadenan de forma secuencial perfecta.";
    } else {
        seal.className = "validator-seal-container error";
        statusText.textContent = "Cadena Corrupta";
        statusText.style.color = "var(--color-error)";
        statusDesc.textContent = "¡ALERTA DE SEGURIDAD! Se detectó una ruptura de enlace en la inmutabilidad de la base de datos.";
    }
    
    btn.disabled = false;
}

// Inspect specific block in detail inside a modal
function inspectBlock(blockId) {
    const block = globalBlockchainData.find(b => b.id_voto === blockId);
    if (!block) return;
    
    document.getElementById("block-modal-title").textContent = `Bloque de Voto #${block.id_voto}`;
    document.getElementById("block-det-candidate").textContent = block.candidato_nombre;
    document.getElementById("block-det-party").textContent = block.candidato_partido;
    document.getElementById("block-det-time").textContent = block.timestamp;
    document.getElementById("block-det-hash-actual").textContent = block.hash_voto;
    document.getElementById("block-det-hash-prev").textContent = block.hash_anterior ? block.hash_anterior : "Ninguno (Bloque Génesis - NULL)";
    
    // Set status badge based on whether it is génesis or regular verified
    const badge = document.getElementById("block-det-status-badge");
    if (!block.hash_anterior) {
        badge.innerHTML = `
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polygon points="12 2 22 8.5 22 15.5 12 22 2 15.5 2 8.5 12 2"/>
            </svg>
            <span>Bloque Génesis de la Cadena</span>
        `;
        badge.style.borderColor = "var(--color-secondary)";
        badge.style.color = "hsl(190, 70%, 75%)";
    } else {
        badge.innerHTML = `
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="20 6 9 17 4 12"/>
            </svg>
            <span>Enlace Criptográfico Verificado</span>
        `;
        badge.style.borderColor = "var(--color-success)";
        badge.style.color = "hsl(142, 70%, 75%)";
    }
    
    document.getElementById("block-modal").classList.remove("hidden");
}

function closeBlockModal() {
    document.getElementById("block-modal").classList.add("hidden");
}

// --- Utilities & UI Helpers ---

// Show Alert Status Overlay Modal
function showStatusModal(isSuccess, title, message, hash = "") {
    const modal = document.getElementById("result-modal");
    const iconContainer = document.getElementById("modal-icon-container");
    const titleText = document.getElementById("modal-title-text");
    const msgText = document.getElementById("modal-msg-text");
    const detailsBox = document.getElementById("modal-details-box");
    const voteHash = document.getElementById("modal-vote-hash");
    const btnAction = document.getElementById("modal-btn-action");
    
    titleText.textContent = title;
    msgText.textContent = message;
    
    if (isSuccess) {
        iconContainer.className = "modal-status-icon success";
        iconContainer.innerHTML = `
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <polyline points="20 6 9 17 4 12"/>
            </svg>
        `;
        
        if (hash) {
            voteHash.textContent = hash;
            detailsBox.classList.remove("hidden");
        } else {
            detailsBox.classList.add("hidden");
        }
        
        btnAction.textContent = "Ver Escrutinio & Ledger";
        btnAction.onclick = () => {
            window.location.href = "/results";
        };
    } else {
        iconContainer.className = "modal-status-icon error";
        iconContainer.innerHTML = `
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <line x1="18" y1="6" x2="6" y2="18"/>
                <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
        `;
        detailsBox.classList.add("hidden");
        
        btnAction.textContent = "Reintentar";
        btnAction.onclick = () => {
            modal.classList.add("hidden");
            document.getElementById("btn-votar").disabled = false;
        };
    }
    
    modal.classList.remove("hidden");
}

function closeModalAndRedirect() {
    document.getElementById("result-modal").classList.add("hidden");
}

// Helpers
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function escapeHtml(str) {
    return str.replace(/&/g, "&amp;")
              .replace(/</g, "&lt;")
              .replace(/>/g, "&gt;")
              .replace(/"/g, "&quot;")
              .replace(/'/g, "&#039;");
}

