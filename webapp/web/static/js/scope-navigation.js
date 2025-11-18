// Global applyZoom function to ensure it's always available
window.applyZoom = function(zoomLevel) {
  // ตั้งค่า zoom สำหรับ body
  document.body.style.zoom = zoomLevel;
  
  // คำนวณความกว้างของ sidebar ตาม zoom
  const baseSidebarWidth = 256; // 16rem * 16px = 256px (w-64)
  const newSidebarWidth = baseSidebarWidth * zoomLevel;
  
  // ปรับความกว้างของ sidebar
  const sidebar = document.getElementById('sidebar');
  if (sidebar) {
    sidebar.style.width = newSidebarWidth + 'px';
  }
  
  // ปรับ margin-left ของ main content ขึ้นกับสถานะ sidebar-toggle
  const mainContent = document.getElementById('main-content');
  if (mainContent) {
    const sidebarToggle = document.getElementById('sidebar-toggle');
    // ถ้าไม่มี checkbox ให้ถือว่า sidebar เปิดอยู่
    const sidebarOpen = sidebarToggle ? !sidebarToggle.checked : true;
    mainContent.style.marginLeft = sidebarOpen ? (newSidebarWidth + 'px') : '0px';
  }
  
  // ปรับขนาดตัวอักษรให้ขยายมากขึ้นตาม zoom
  const baseFontSize = 16; // 16px (1rem)
  const newFontSize = baseFontSize * zoomLevel;
  document.documentElement.style.fontSize = newFontSize + 'px';
  
  // บันทึกค่า zoom ใน localStorage
  localStorage.setItem('pageZoom', zoomLevel);
};

// Global function to load saved zoom
window.loadSavedZoom = function() {
  const savedZoom = localStorage.getItem('pageZoom');
  if (savedZoom) {
    window.applyZoom(parseFloat(savedZoom));
  }
};

// Global function to adjust main content margin
window.adjustMainContentMargin = function() {
  const mainContent = document.getElementById('main-content');
  const sidebarToggle = document.getElementById('sidebar-toggle');
  
  if (mainContent && sidebarToggle) {
    const sidebarOpen = !sidebarToggle.checked;
    const currentZoom = parseFloat(document.body.style.zoom || 1);
    const baseSidebarWidth = 256; // 16rem * 16px = 256px (w-64)
    const newSidebarWidth = baseSidebarWidth * currentZoom;
    
    mainContent.style.marginLeft = sidebarOpen ? (newSidebarWidth + 'px') : '0px';
  }
};

document.addEventListener('DOMContentLoaded', function() {
    // Load saved zoom when page loads
    window.loadSavedZoom();
    
    // Add event listener for sidebar toggle
    const sidebarToggle = document.getElementById('sidebar-toggle');
    if (sidebarToggle) {
        sidebarToggle.addEventListener('change', window.adjustMainContentMargin);
    }
    
    // Handle scope navigation with keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Only handle arrow keys when not typing in input fields
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
            return;
        }
        
        const prevBtn = document.getElementById('prev-scope-btn');
        const nextBtn = document.getElementById('next-scope-btn');
        
        if (e.key === 'ArrowLeft' && prevBtn && !prevBtn.classList.contains('opacity-50')) {
            e.preventDefault();
            prevBtn.click();
            // Sync zoom/layout after scope change
            setTimeout(() => window.loadSavedZoom(), 100);
        } else if (e.key === 'ArrowRight' && nextBtn && !nextBtn.classList.contains('opacity-50')) {
            e.preventDefault();
            nextBtn.click();
            // Sync zoom/layout after scope change
            setTimeout(() => window.loadSavedZoom(), 100);
        }
    });
    
    // Add hover effects for scope indicators
    const scopeIndicators = document.querySelectorAll('.scope-indicator');
    scopeIndicators.forEach(indicator => {
        indicator.addEventListener('mouseenter', function() {
            if (!this.classList.contains('scale-125')) {
                this.style.transform = 'scale(1.1)';
            }
        });
        
        indicator.addEventListener('mouseleave', function() {
            if (!this.classList.contains('scale-125')) {
                this.style.transform = 'scale(1)';
            }
        });
    });
    
    // Add smooth transitions for scope navigation
    const scopeNavContainer = document.querySelector('[class*="bg-white rounded-full shadow-lg"]');
    if (scopeNavContainer) {
        scopeNavContainer.style.transition = 'all 0.3s ease';
    }
    
    // Handle loading states for scope navigation
    const scopeButtons = document.querySelectorAll('[hx-post*="view_emissions"]');
    scopeButtons.forEach(button => {
        button.addEventListener('htmx:beforeRequest', function() {
            // Add loading state
            if (this.id === 'prev-scope-btn' || this.id === 'next-scope-btn') {
                this.querySelector('i').style.animation = 'spin 1s linear infinite';
            } else if (this.classList.contains('scope-indicator')) {
                this.style.opacity = '0.5';
            }
        });
        
        button.addEventListener('htmx:afterRequest', function() {
            // Remove loading state
            if (this.id === 'prev-scope-btn' || this.id === 'next-scope-btn') {
                this.querySelector('i').style.animation = '';
            } else if (this.classList.contains('scope-indicator')) {
                this.style.opacity = '';
            }
        });
    });
    
    // Add click event listeners for scope buttons to sync zoom/layout
    ['prev-scope-btn', 'next-scope-btn'].forEach(btnId => {
        const btn = document.getElementById(btnId);
        if (btn) {
            btn.addEventListener('click', function() {
                setTimeout(() => window.loadSavedZoom(), 100);
            });
        }
    });
});

// State management for emissions page
window.EmissionsState = {
    saveState: function(scopeId, subScopeId, year, page) {
        const state = {
            scopeId: scopeId,
            subScopeId: subScopeId,
            year: year,
            page: page,
            timestamp: new Date().getTime()
        };
        localStorage.setItem('emissionsState', JSON.stringify(state));
    },
    
    loadState: function() {
        try {
            const saved = localStorage.getItem('emissionsState');
            if (saved) {
                return JSON.parse(saved);
            }
        } catch (e) {
            console.warn('Failed to load emissions state:', e);
        }
        return null;
    },
    
    clearState: function() {
        localStorage.removeItem('emissionsState');
    }
};

// HTMX afterSwap event to ensure zoom functionality is preserved
document.addEventListener('htmx:afterSwap', function() {
    // Re-apply saved zoom after content is swapped
    setTimeout(() => {
        // Force reload saved zoom to ensure it's applied after pagination
        window.loadSavedZoom();
        
        // Restore emissions state if applicable
        restoreEmissionsState();
        
        // Re-add sidebar toggle event listener
        const sidebarToggle = document.getElementById('sidebar-toggle');
        if (sidebarToggle) {
            sidebarToggle.removeEventListener('change', window.adjustMainContentMargin);
            sidebarToggle.addEventListener('change', window.adjustMainContentMargin);
        }
        
        // Re-initialize feather icons
        if (typeof feather !== 'undefined') {
            feather.replace();
        }
        
        // Re-initialize zoom slider if it was removed
        const existingZoomContainer = document.getElementById('zoom-slider-container');
        if (!existingZoomContainer) {
            // If zoom slider container doesn't exist, create it
            const zoomSliderHTML = `
                <div id="zoom-slider-container" class="fixed z-50 hidden" style="bottom: 20px; right: 20px;">
                  <div id="zoom-slider-content" class="bg-white rounded-lg shadow-xl border border-gray-300 transition-all duration-300">
                    
                    <!-- Full State -->
                    <div id="full-content" class="p-3">
                      <!-- Header -->
                      <div class="flex justify-between items-center mb-2">
                        <div class="text-sm font-medium text-gray-700">Zoom</div>
                        <button 
                          id="minimize-btn" 
                          onclick="toggleMinimize()"
                          class="p-1 hover:bg-gray-100 rounded transition-colors"
                          title="ย่อ"
                        >
                          <i data-feather="minus" class="w-4 h-4 text-gray-600"></i>
                        </button>
                      </div>
                      
                      <!-- Quick Buttons -->
                      <div class="flex gap-1 mb-2">
                        <button onclick="decreaseZoom()" class="bg-gray-100 hover:bg-gray-200 rounded px-2 py-1 text-sm" title="ลด 5%">
                          <i data-feather="minus" class="w-3 h-3"></i>
                        </button>
                        <button onclick="resetZoom()" class="bg-gray-100 hover:bg-gray-200 rounded px-2 py-1 text-sm" title="100%">
                          <i data-feather="maximize-2" class="w-3 h-3"></i>
                        </button>
                        <button onclick="increaseZoom()" class="bg-gray-100 hover:bg-gray-200 rounded px-2 py-1 text-sm" title="เพิ่ม 5%">
                          <i data-feather="plus" class="w-3 h-3"></i>
                        </button>
                      </div>
                      
                      <!-- Slider -->
                      <input 
                        type="range" 
                        id="zoom-slider" 
                        min="0.5" 
                        max="2.0" 
                        step="0.05" 
                        value="1.0"
                        class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                        style="background: linear-gradient(to right, #003366 0%, #003366 33.33%, #e5e7eb 33.33%, #e5e7eb 100%);"
                      >
                    </div>
                    
                    <!-- Minimized State -->
                    <div id="minimized-content" class="hidden p-2">
                      <!-- Expand Button -->
                      <div class="flex justify-between items-center">
                        <div class="text-xs font-medium text-gray-600">Zoom</div>
                        <button 
                          onclick="toggleMinimize()" 
                          class="p-1 hover:bg-gray-100 rounded transition-colors"
                          title="ขยาย"
                        >
                          <i data-feather="maximize-2" class="w-3 h-3 text-gray-600"></i>
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
            `;
            
            // Add the zoom slider to the body
            document.body.insertAdjacentHTML('beforeend', zoomSliderHTML);
            
            // Re-initialize zoom slider functionality
            initializeZoomSlider();
        }
        
        // Ensure zoom slider is visible on large screens
        const zoomContainer = document.getElementById('zoom-slider-container');
        if (zoomContainer && window.innerWidth >= 1024) {
            zoomContainer.classList.remove('hidden');
        }
        
        // Additional delay to ensure zoom is applied after all content is loaded
        setTimeout(() => {
            window.loadSavedZoom();
        }, 100);
    });
});

// Function to restore emissions state
function restoreEmissionsState() {
    const yearSelect = document.getElementById('year-select');
    if (yearSelect) {
        const savedState = window.EmissionsState.loadState();
        if (savedState && savedState.year) {
            yearSelect.value = savedState.year;
        }
    }
}

// Function to save current emissions state
function saveCurrentEmissionsState() {
    const yearSelect = document.getElementById('year-select');
    const currentPageElement = document.querySelector('[data-current-page]');
    
    if (yearSelect) {
        const year = yearSelect.value;
        const page = currentPageElement ? parseInt(currentPageElement.getAttribute('data-current-page')) : 1;
        
        // Get current scope info from URL or from hidden inputs
        const urlParams = new URLSearchParams(window.location.search);
        const scopeId = urlParams.get('scope_id') || document.querySelector('input[name="scope_id"]')?.value;
        const subScopeId = urlParams.get('sub_scope_id') || document.querySelector('input[name="sub_scope_id"]')?.value;
        
        if (scopeId && subScopeId) {
            window.EmissionsState.saveState(scopeId, subScopeId, year, page);
        }
    }
}

// Add event listeners for emissions state management
document.addEventListener('DOMContentLoaded', function() {
    // Save state when year changes
    const yearSelect = document.getElementById('year-select');
    if (yearSelect) {
        yearSelect.addEventListener('change', function() {
            saveCurrentEmissionsState();
        });
    }
    
    // Save state when pagination changes
    document.addEventListener('click', function(e) {
        if (e.target.closest('button[hx-get*="page="]')) {
            setTimeout(() => {
                saveCurrentEmissionsState();
            }, 100);
        }
    });
    
    // Save state when navigating between scopes
    document.addEventListener('click', function(e) {
        if (e.target.closest('[hx-post*="view_emissions"]')) {
            const button = e.target.closest('[hx-post*="view_emissions"]');
            if (button) {
                const hxVals = button.getAttribute('hx-vals');
                if (hxVals) {
                    try {
                        const vals = JSON.parse(hxVals.replace(/'/g, '"'));
                        if (vals.scope_id && vals.sub_scope_id) {
                            const yearSelect = document.getElementById('year-select');
                            const year = yearSelect ? yearSelect.value : new Date().getFullYear();
                            window.EmissionsState.saveState(vals.scope_id, vals.sub_scope_id, year, 1);
                        }
                    } catch (e) {
                        console.warn('Failed to parse hx-vals:', e);
                    }
                }
            }
        }
    });
});

// Function to initialize zoom slider
function initializeZoomSlider() {
    const container = document.getElementById('zoom-slider-container');
    if (!container) return;

    // Show on large screens only
    if (window.innerWidth >= 1024) {
        container.classList.remove('hidden');
    }

    // Setup slider value only
    const slider = document.getElementById('zoom-slider');
    if (slider) {
        const savedZoom = localStorage.getItem('pageZoom');
        const zoomValue = savedZoom ? parseFloat(savedZoom) : 1.0;
        slider.value = zoomValue;
    }
}

// Global zoom functions
window.toggleMinimize = function() {
  const fullContent = document.getElementById('full-content');
  const minimizedContent = document.getElementById('minimized-content');
  const content = document.getElementById('zoom-slider-content');
  
  let isMinimized = false;
  if (minimizedContent.classList.contains('hidden')) {
    isMinimized = true;
  }
  
  if (isMinimized) {
    fullContent.classList.add('hidden');
    minimizedContent.classList.remove('hidden');
    content.style.width = '80px';
  } else {
    fullContent.classList.remove('hidden');
    minimizedContent.classList.add('hidden');
    content.style.width = '200px';
  }
  
  // Save state
  localStorage.setItem('zoomSliderMinimized', isMinimized.toString());
  if (typeof feather !== 'undefined') {
    setTimeout(() => feather.replace(), 50);
  }
};

window.setZoom = function(zoomLevel) {
  const slider = document.getElementById('zoom-slider');
  if (slider) slider.value = zoomLevel;
  updateZoom(zoomLevel);
};

window.increaseZoom = function() {
  const slider = document.getElementById('zoom-slider');
  if (slider) {
    const newZoom = Math.min(2.0, parseFloat(slider.value) + 0.05);
    slider.value = newZoom;
    updateZoom(newZoom);
  }
};

window.decreaseZoom = function() {
  const slider = document.getElementById('zoom-slider');
  if (slider) {
    const newZoom = Math.max(0.5, parseFloat(slider.value) - 0.05);
    slider.value = newZoom;
    updateZoom(newZoom);
  }
};

window.resetZoom = function() {
  setZoom(1.0);
};

// Update zoom function
function updateZoom(zoomLevel) {
  // Update slider background
  const percentage = ((zoomLevel - 0.5) / 1.5) * 100;
  const gradient = `linear-gradient(to right, #003366 0%, #003366 ${percentage}%, #e5e7eb ${percentage}%, #e5e7eb 100%)`;
  
  const slider = document.getElementById('zoom-slider');
  if (slider) slider.style.background = gradient;
  
  // Apply zoom using global function
  if (typeof window.applyZoom === 'function') {
    window.applyZoom(zoomLevel);
  }

  // ปรับขนาดคอมโพเนนต์แบบกลับค่า zoom
  const container = document.getElementById('zoom-slider-container');
  if (container) {
    container.style.transform = `scale(${1 / zoomLevel})`;
    container.style.transformOrigin = 'bottom right';
  }

  // Save zoom level
  localStorage.setItem('pageZoom', zoomLevel.toString());
}

// Add CSS animation for loading spinner
if (!document.getElementById('zoom-spin-keyframes')) {
    const style = document.createElement('style');
    style.id = 'zoom-spin-keyframes';
    style.textContent = `
        @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }
    `;
    document.head.appendChild(style);
}
