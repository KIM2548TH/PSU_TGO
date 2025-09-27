// Shared JavaScript functions for form management

let inputFieldCount = 0;
let currentFormula = '';
let currentFormula2 = '';
let isFormInitialized = false;

// Calculator Toggle Functions
function toggleFormulaCalculator() {
    const calculator = document.getElementById('formula-calculator');
    const formula2Calculator = document.getElementById('formula2-calculator');
    if (formula2Calculator) {
        formula2Calculator.classList.add('hidden');
    }
    calculator.classList.toggle('hidden');
    if (!calculator.classList.contains('hidden')) {
        currentFormula = document.getElementById('formula').value;
        updateFormulaButtons();
        setTimeout(() => feather.replace(), 10);
    }
}

function toggleFormula2Calculator() {
    const calculator = document.getElementById('formula2-calculator');
    const formulaCalculator = document.getElementById('formula-calculator');
    
    formulaCalculator.classList.add('hidden');
    calculator.classList.toggle('hidden');
    
    if (!calculator.classList.contains('hidden')) {
        currentFormula2 = document.getElementById('formula2').value;
        updateFormula2Buttons();
        setTimeout(() => feather.replace(), 10);
    }
}

function closeFormulaCalculator() {
    document.getElementById('formula-calculator').classList.add('hidden');
}

function closeFormula2Calculator() {
    document.getElementById('formula2-calculator').classList.add('hidden');
}

function applyFormula(event) {
    updatePreview();
    closeFormulaCalculator();
}

function applyFormula2(event) {
    updatePreview();
    closeFormula2Calculator();
}

// Close calculators when clicking outside
function setupCalculatorCloseHandlers() {
    document.addEventListener('click', function(event) {
        const formulaInput = document.getElementById('formula');
        const formula2Input = document.getElementById('formula2');
        const formulaCalculator = document.getElementById('formula-calculator');
        const formula2Calculator = document.getElementById('formula2-calculator');
        const formulaButton = document.getElementById('formula-dropdown-btn');
        const formula2Button = document.getElementById('formula2-dropdown-btn');
        
        if (formulaInput && formulaCalculator && formulaButton &&
            !formulaInput.contains(event.target) && 
            !formulaCalculator.contains(event.target) &&
            !formulaButton.contains(event.target)) {
            closeFormulaCalculator();
        }
        
        if (formula2Input && formula2Calculator && formula2Button &&
            !formula2Input.contains(event.target) && 
            !formula2Calculator.contains(event.target) &&
            !formula2Button.contains(event.target)) {
            closeFormula2Calculator();
        }
    });
}

function addInputField(fieldData = {}) {
    const container = document.getElementById("input-fields-container");
    if (!container) {
        console.error("Container element with ID 'input-fields-container' not found.");
        return;
    }

    const fieldId = `input-${inputFieldCount++}`;
    const fieldNumber = container.children.length + 1;

    const html = `
    <div class="border border-gray-300 rounded-xl p-4 bg-gray-50 shadow-sm" data-index="${fieldId}">
        <div class="flex justify-between items-center mb-3">
            <h4 class="text-md font-semibold text-gray-600">Field #${fieldNumber}</h4>
            <button type="button" class="btn btn-sm btn-error" onclick="removeField(this)">✕</button>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <input 
                name="field" 
                class="input input-bordered w-full" 
                placeholder="Field" 
                value="${fieldData.field || ''}" 
                onchange="updatePreview(); updateFormulaButtons();" 
                required
            >
            <input 
                name="label" 
                class="input input-bordered w-full" 
                placeholder="Label" 
                value="${fieldData.label || ''}" 
                onchange="updatePreview(); updateFormulaButtons();"
            >
            <select 
                name="input_type" 
                class="select select-bordered w-full" 
                onchange="updatePreview(); updateFormulaButtons();"
            >
                <option value="number" ${fieldData.input_type === 'number' ? 'selected' : ''}>Number</option>
                <option value="text" ${fieldData.input_type === 'text' ? 'selected' : ''}>Text</option>
                <option value="select" ${fieldData.input_type === 'select' ? 'selected' : ''}>Select</option>
            </select>
            <input 
                name="unit" 
                class="input input-bordered w-full" 
                placeholder="Unit" 
                value="${fieldData.unit || ''}" 
                onchange="updatePreview(); updateFormulaButtons();"
            >
        </div>
    </div>`;

    container.insertAdjacentHTML("beforeend", html);
}

function removeField(button) {
    button.closest("[data-index]").remove();
    updatePreview();
    updateFormulaButtons();
}

function updateFormulaButtons() {
    const container = document.getElementById("input-fields-container");
    const variablesButtons = document.getElementById("variables-buttons");
    const numbersButtons = document.getElementById("numbers-buttons");
    const operatorsButtons = document.getElementById("operators-buttons");

    if (!variablesButtons || !numbersButtons || !operatorsButtons) return;

    variablesButtons.innerHTML = "";
    numbersButtons.innerHTML = "";
    operatorsButtons.innerHTML = "";

    // ตรวจสอบว่าเป็นฟอร์มลิงก์หรือไม่
    const formType = document.querySelector('input[name="form_type"]:checked')?.value;
    
    if (formType === 'linked' && window.linkedMaterialData && window.linkedMaterialData.input_types) {
        // ใช้ตัวแปรจาก linked material
        window.linkedMaterialData.input_types.forEach(field => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "btn btn-xs btn-outline bg-pink-100 text-pink-800";
            button.textContent = field.field;
            button.onclick = () => addToFormula(field.field);
            variablesButtons.appendChild(button);
        });
    } else {
        // ใช้ตัวแปรจากฟอร์มปกติ
        const fields = container.querySelectorAll("[data-index]");
        fields.forEach((row) => {
            const field = row.querySelector("input[name='field']").value;
            if (field) {
                const button = document.createElement("button");
                button.type = "button";
                button.className = "btn btn-xs btn-outline bg-pink-100 text-pink-800";
                button.textContent = field;
                button.onclick = () => addToFormula(field);
                variablesButtons.appendChild(button);
            }
        });
    }

    // สร้างปุ่มตัวเลข
    for (let i = 0; i <= 9; i++) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "btn btn-xs btn-outline";
        button.textContent = i;
        button.onclick = () => addToFormula(i);
        numbersButtons.appendChild(button);
    }

    // สร้างปุ่ม operators
    const operators = ["+", "-", "*", "/", "^", "(", ")", ".", "⌫", "C"];
    operators.forEach(op => {
        const button = document.createElement("button");
        button.type = "button";
        
        if (op === "⌫") {
            button.className = "btn btn-xs btn-error";
            button.onclick = () => removeLastCharacter();
        } else if (op === "C") {
            button.className = "btn btn-xs btn-warning";
            button.onclick = () => clearFormula();
        } else {
            button.className = "btn btn-xs btn-outline";
            button.onclick = () => addToFormula(op);
        }
        
        button.textContent = op;
        operatorsButtons.appendChild(button);
    });
}

function updateFormula2Buttons() {
    const constantsButtons = document.getElementById("constants-buttons");
    const numbers2Buttons = document.getElementById("numbers2-buttons");
    const operators2Buttons = document.getElementById("operators2-buttons");

    if (!constantsButtons || !numbers2Buttons || !operators2Buttons) return;

    constantsButtons.innerHTML = "";
    numbers2Buttons.innerHTML = "";
    operators2Buttons.innerHTML = "";

    const constants = [
        { name: "CO2", label: "Carbon Dioxide", color: "bg-blue-100 text-blue-800" },
        { name: "Fossil_CH4", label: "Fossil Methane", color: "bg-orange-100 text-orange-800" },
        { name: "CH4", label: "Methane", color: "bg-green-100 text-green-800" },
        { name: "N2O", label: "Nitrous Oxide", color: "bg-red-100 text-red-800" },
        { name: "SF6", label: "Sulfur Hexafluoride", color: "bg-purple-100 text-purple-800" },
        { name: "NF3", label: "Nitrogen Trifluoride", color: "bg-teal-100 text-teal-800" }
    ];

    constants.forEach(constant => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = `btn btn-xs btn-outline ${constant.color}`;
        button.textContent = constant.name;
        button.title = constant.label;
        button.onclick = () => addToFormula2(constant.name);
        constantsButtons.appendChild(button);
    });

    for (let i = 0; i <= 9; i++) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "btn btn-xs btn-outline";
        button.textContent = i;
        button.onclick = () => addToFormula2(i);
        numbers2Buttons.appendChild(button);
    }

    const operators = ["+", "-", "*", "/", "^", "(", ")", ".", "⌫", "C"];
    operators.forEach(op => {
        const button = document.createElement("button");
        button.type = "button";
        
        if (op === "⌫") {
            button.className = "btn btn-xs btn-error";
            button.onclick = () => removeLastCharacter2();
        } else if (op === "C") {
            button.className = "btn btn-xs btn-warning";
            button.onclick = () => clearFormula2();
        } else {
            button.className = "btn btn-xs btn-outline";
            button.onclick = () => addToFormula2(op);
        }
        
        button.textContent = op;
        operators2Buttons.appendChild(button);
    });
}

function addToFormula(value) {
    const formulaInput = document.getElementById("formula");
    formulaInput.value += value;
}

function addToFormula2(value) {
    const formula2Input = document.getElementById("formula2");
    formula2Input.value += value;
}

function removeLastCharacter() {
    const formulaInput = document.getElementById("formula");
    formulaInput.value = formulaInput.value.slice(0, -1);
}

function removeLastCharacter2() {
    const formula2Input = document.getElementById("formula2");
    formula2Input.value = formula2Input.value.slice(0, -1);
}

function clearFormula() {
    const formulaInput = document.getElementById("formula");
    formulaInput.value = "";
}

function clearFormula2() {
    const formula2Input = document.getElementById("formula2");  
    formula2Input.value = "";
}

// HTMX Configuration
function setupHTMXHandlers() {
    document.addEventListener('htmx:configRequest', function(evt) {
        console.log("HTMX configRequest:", evt.detail.path);
        
        if (evt.detail.path.includes('/get-sub-scopes/')) {
            const mainScope = document.getElementById('main-scope')?.value;
            if (mainScope && evt.detail.path === '/form-management/get-sub-scopes/') {
                evt.detail.path = `/form-management/get-sub-scopes/${mainScope}`;
                console.log("Updated path to:", evt.detail.path);
            }
        }
    });

    document.addEventListener('htmx:beforeSwap', function(evt) {
        console.log("HTMX beforeSwap:", evt.detail.target.id);
        
        // Reset form state before loading new content
        if (evt.detail.target.id === 'modal-content') {
            resetFormState();
        }
    });

    document.addEventListener('htmx:afterSettle', function(evt) {
        console.log("HTMX afterSettle:", evt.detail.target.id || evt.detail.target.tagName);
        
        // Handle sub-scope container updates
        if (evt.detail.target.id === 'sub-scope-container' || 
            evt.detail.target.closest('#sub-scope-container') ||
            evt.detail.target.querySelector('select[name="sup_scope"]')) {
            console.log("Sub scope updated, refreshing preview");
            setTimeout(() => {
                if (typeof updatePreview === 'function') {
                    updatePreview();
                }
                feather.replace();
            }, 50);
        }
        
        // Handle modal content loading
        if (evt.detail.target.id === 'modal-content') {
            console.log("Modal content loaded");
            feather.replace();
            
            window.formInitTimeout = setTimeout(() => {
                // Check if it's add form or edit form
                if (document.querySelector('input[name="form_id"]')) {
                    console.log("Edit form detected - let edit script handle initialization");
                } else {
                    console.log("Add form detected - initializing");
                    if (typeof initializeForm === 'function') {
                        initializeForm();
                        setTimeout(triggerSubScopeLoad, 200);
                    }
                }
            }, 100);
        }
    });

    document.addEventListener("htmx:afterRequest", function(evt) {
        feather.replace();
    });
}

function triggerSubScopeLoad() {
    const mainScope = document.getElementById('main-scope');
    if (mainScope && mainScope.value) {
        console.log("Triggering sub scope load for scope:", mainScope.value);
        // สำหรับ add form ให้ trigger change
        if (!document.querySelector('input[name="form_id"]')) {
            htmx.trigger(mainScope, 'change');
        }
    }
}

// Initialize everything when DOM is ready
function initializeSharedFormFunctions() {
    setupCalculatorCloseHandlers();
    setupHTMXHandlers();
    feather.replace();
}

// Auto-initialize when script loads
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeSharedFormFunctions);
} else {
    initializeSharedFormFunctions();
}

// เพิ่มใน form-calculator.js
function resetFormState() {
    console.log("Resetting form state...");
    isFormInitialized = false;
    inputFieldCount = 0;
    currentFormula = '';
    currentFormula2 = '';
    
    // Clear any existing timeouts
    if (window.formInitTimeout) {
        clearTimeout(window.formInitTimeout);
    }
}