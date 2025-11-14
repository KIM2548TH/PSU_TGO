document.addEventListener('DOMContentLoaded', function() {
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
        } else if (e.key === 'ArrowRight' && nextBtn && !nextBtn.classList.contains('opacity-50')) {
            e.preventDefault();
            nextBtn.click();
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
});

// Add CSS animation for loading spinner
const style = document.createElement('style');
style.textContent = `
    @keyframes spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
`;
document.head.appendChild(style);
