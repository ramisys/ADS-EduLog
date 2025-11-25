/**
 * EduLog - Toast Notification System
 * Handles all toast notifications including loading toasts
 */

// Loading Toast Management
let loadingToastId = null;
let loadingToastInstance = null;

// Hide loading toast helper (defined first)
function hideLoadingToastInternal() {
    if (loadingToastId && loadingToastInstance) {
        const toastElement = document.getElementById(loadingToastId);
        if (toastElement && typeof bootstrap !== 'undefined') {
            try {
                loadingToastInstance.hide();
                toastElement.addEventListener('hidden.bs.toast', function() {
                    if (toastElement && toastElement.parentNode) {
                        toastElement.remove();
                    }
                    loadingToastId = null;
                    loadingToastInstance = null;
                }, { once: true });
            } catch (e) {
                console.error('Error hiding loading toast:', e);
                // Fallback: remove directly
                if (toastElement && toastElement.parentNode) {
                    toastElement.remove();
                }
                loadingToastId = null;
                loadingToastInstance = null;
            }
        } else if (toastElement) {
            // Bootstrap not available, remove directly
            if (toastElement.parentNode) {
                toastElement.remove();
            }
            loadingToastId = null;
            loadingToastInstance = null;
        }
    }
}

// Show loading toast
window.showLoadingToast = function(message = 'Loading...', persistent = false) {
    const toastContainer = document.getElementById('toastContainer');
    if (!toastContainer) {
        console.error('Toast container not found. Make sure toastContainer div exists in the DOM.');
        return null;
    }

    // Check if Bootstrap is available - wait a bit if not
    if (typeof bootstrap === 'undefined') {
        console.warn('Bootstrap is not loaded yet, retrying in 100ms...');
        setTimeout(function() {
            if (typeof bootstrap !== 'undefined') {
                showLoadingToast(message, persistent);
            } else {
                console.error('Bootstrap failed to load. Cannot show loading toast.');
            }
        }, 100);
        return null;
    }

    // Hide any existing loading toast
    if (loadingToastId) {
        hideLoadingToastInternal();
        // Wait a bit for cleanup
        setTimeout(function() {
            createLoadingToast(message, persistent);
        }, 150);
        return loadingToastId;
    }

    const result = createLoadingToast(message, persistent);
    if (!result) {
        console.error('Failed to create loading toast');
    }
    return result;
};

function createLoadingToast(message, persistent) {
    const toastContainer = document.getElementById('toastContainer');
    
    // Create unique toast ID
    loadingToastId = 'loading-toast-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);

    // Create loading toast HTML with spinner
    const toastHTML = `
        <div id="${loadingToastId}" class="toast bg-primary text-white" role="status" aria-live="polite" aria-atomic="true" data-bs-autohide="false">
            <div class="toast-header bg-primary text-white border-0">
                <div class="spinner-border spinner-border-sm me-2" role="status" style="width: 1rem; height: 1rem; border-width: 0.15em;">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <strong class="me-auto text-white">Loading</strong>
                ${persistent ? '' : '<button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast" aria-label="Close"></button>'}
            </div>
            <div class="toast-body text-white">
                ${message}
            </div>
        </div>
    `;

    // Insert toast
    toastContainer.insertAdjacentHTML('beforeend', toastHTML);

    // Initialize and show toast
    const toastElement = document.getElementById(loadingToastId);
    if (toastElement && typeof bootstrap !== 'undefined') {
        try {
            loadingToastInstance = new bootstrap.Toast(toastElement, {
                autohide: false
            });
            
            // Use requestAnimationFrame to ensure DOM is ready
            requestAnimationFrame(function() {
                if (loadingToastInstance && toastElement) {
                    loadingToastInstance.show();
                }
            });
            
            return loadingToastId;
        } catch (e) {
            console.error('Error showing loading toast:', e);
            // Fallback: show immediately
            if (toastElement) {
                toastElement.classList.add('show');
            }
            return loadingToastId;
        }
    }
    return null;
}

// Hide loading toast
window.hideLoadingToast = function() {
    hideLoadingToastInternal();
};

// Bootstrap Toast Notification System - Global Function
window.showToast = function(message, type = 'info', duration = 5000) {
    const toastContainer = document.getElementById('toastContainer');
    if (!toastContainer) return;

    // Map message types to Bootstrap toast classes
    const toastClasses = {
        'success': 'bg-success text-white',
        'error': 'bg-danger text-white',
        'warning': 'bg-warning text-dark',
        'info': 'bg-info text-white',
        'debug': 'bg-secondary text-white'
    };

    // Map message types to icons
    const toastIcons = {
        'success': '<i class="bi bi-check-circle-fill me-2"></i>',
        'error': '<i class="bi bi-exclamation-triangle-fill me-2"></i>',
        'warning': '<i class="bi bi-exclamation-circle-fill me-2"></i>',
        'info': '<i class="bi bi-info-circle-fill me-2"></i>',
        'debug': '<i class="bi bi-bug-fill me-2"></i>'
    };

    // Normalize type (Django uses 'error', Bootstrap uses 'danger')
    const normalizedType = type === 'error' ? 'error' : type;
    const toastClass = toastClasses[normalizedType] || toastClasses['info'];
    const toastIcon = toastIcons[normalizedType] || toastIcons['info'];

    // Create unique toast ID
    const toastId = 'toast-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);

    // Create toast HTML
    const toastHTML = `
        <div id="${toastId}" class="toast ${toastClass}" role="alert" aria-live="assertive" aria-atomic="true" data-bs-autohide="true" data-bs-delay="${duration}">
            <div class="toast-header ${toastClass} border-0">
                ${toastIcon}
                <strong class="me-auto">${type.charAt(0).toUpperCase() + type.slice(1)}</strong>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
            <div class="toast-body">
                ${message}
            </div>
        </div>
    `;

    // Insert toast
    toastContainer.insertAdjacentHTML('beforeend', toastHTML);

    // Initialize and show toast
    const toastElement = document.getElementById(toastId);
    const toast = new bootstrap.Toast(toastElement, {
        autohide: true,
        delay: duration
    });

    toast.show();

    // Remove toast element from DOM after it's hidden
    toastElement.addEventListener('hidden.bs.toast', function() {
        toastElement.remove();
    });
};

// Utility function to wrap async operations with loading toast
window.withLoadingToast = async function(asyncFunction, loadingMessage = 'Loading...') {
    if (typeof showLoadingToast !== 'function') {
        console.warn('showLoadingToast not available');
        return await asyncFunction();
    }
    
    const loadingId = showLoadingToast(loadingMessage);
    try {
        const result = await asyncFunction();
        if (typeof hideLoadingToast === 'function') {
            hideLoadingToast();
        }
        return result;
    } catch (error) {
        if (typeof hideLoadingToast === 'function') {
            hideLoadingToast();
        }
        throw error;
    }
};

// Auto-integrate loading toasts with form submissions and fetch requests
function initFormLoadingToasts() {
    // Wait for Bootstrap to be fully loaded
    if (typeof bootstrap === 'undefined' || typeof showLoadingToast !== 'function') {
        // Retry after a short delay
        setTimeout(initFormLoadingToasts, 100);
        return;
    }

    // Handle all form submissions
    document.querySelectorAll('form').forEach(function(form) {
        form.addEventListener('submit', function(e) {
            // Don't show loading for forms with data-no-loading attribute
            if (form.hasAttribute('data-no-loading')) {
                return;
            }

            // Get submit button to disable it
            const submitButtons = form.querySelectorAll('button[type="submit"], input[type="submit"]');
            
            // Show loading toast (persistent until page changes or form error)
            const loadingId = showLoadingToast('Processing your request...', true);
            
            if (!loadingId) {
                console.warn('Failed to show loading toast');
            }

            // Disable submit buttons and add spinner
            submitButtons.forEach(function(btn) {
                btn.disabled = true;
                if (!btn.dataset.originalText) {
                    btn.dataset.originalText = btn.innerHTML || btn.value || 'Submit';
                }
                if (btn.tagName === 'BUTTON') {
                    const originalContent = btn.innerHTML;
                    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Processing...';
                    btn.dataset.originalContent = originalContent;
                } else if (btn.tagName === 'INPUT') {
                    btn.dataset.originalValue = btn.value;
                    btn.value = 'Processing...';
                }
            });

            // Store form reference for cleanup
            form.dataset.loadingId = loadingId;

            // Re-enable buttons and hide loading if form validation fails
            form.addEventListener('invalid', function(e) {
                if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT' || e.target.tagName === 'TEXTAREA') {
                    hideLoadingToast();
                    submitButtons.forEach(function(btn) {
                        btn.disabled = false;
                        if (btn.tagName === 'BUTTON') {
                            btn.innerHTML = btn.dataset.originalText || 'Submit';
                        } else if (btn.tagName === 'INPUT') {
                            btn.value = btn.dataset.originalValue || 'Submit';
                        }
                    });
                    form.removeAttribute('data-loading-id');
                }
            }, true); // Use capture phase

            // Cleanup on page unload/navigation
            const cleanup = function() {
                hideLoadingToast();
                submitButtons.forEach(function(btn) {
                    btn.disabled = false;
                    if (btn.tagName === 'BUTTON') {
                        btn.innerHTML = btn.dataset.originalText || 'Submit';
                    } else if (btn.tagName === 'INPUT') {
                        btn.value = btn.dataset.originalValue || 'Submit';
                    }
                });
                form.removeAttribute('data-loading-id');
            };

            window.addEventListener('beforeunload', cleanup, { once: true });
            
            // Also cleanup after a timeout as fallback (in case form doesn't navigate)
            setTimeout(function() {
                if (form.dataset.loadingId) {
                    cleanup();
                }
            }, 30000); // 30 seconds max
        });
    });

    // Wrapper for fetch with automatic loading toast
    const originalFetch = window.fetch;
    window.fetch = function(...args) {
        // Check if this fetch should show loading
        // Skip loading if 'X-No-Loading' header is set or 'noLoading' option is true
        const options = args[1] || {};
        const headers = options.headers || {};
        const shouldShowLoading = !options.noLoading && 
            !(headers['X-No-Loading'] || headers['x-no-loading']);

        let loadingId = null;
        if (shouldShowLoading && typeof showLoadingToast === 'function') {
            loadingId = showLoadingToast(options.loadingMessage || 'Loading...', false);
        }

        // Call original fetch
        const fetchPromise = originalFetch.apply(this, args);
        
        // Hide loading when fetch completes (success or error)
        fetchPromise
            .then(function(response) {
                if (loadingId && typeof hideLoadingToast === 'function') {
                    // Small delay to ensure the toast was visible
                    setTimeout(function() {
                        hideLoadingToast();
                    }, 300);
                }
                return response;
            })
            .catch(function(error) {
                if (loadingId && typeof hideLoadingToast === 'function') {
                    setTimeout(function() {
                        hideLoadingToast();
                    }, 300);
                }
                throw error;
            });

        return fetchPromise;
    };
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initFormLoadingToasts);
} else {
    // DOM already loaded
    initFormLoadingToasts();
}
