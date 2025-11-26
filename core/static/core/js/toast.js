/**
 * EduLog - Toast Notification System
 * Handles all toast notifications including loading toasts
 */

// Loading Toast Management - DISABLED
// Loading toast functionality has been removed

// Show loading toast - DISABLED (no-op function)
window.showLoadingToast = function(message = 'Loading...', persistent = false) {
    // Loading toast functionality has been disabled
    return null;
};

// Hide loading toast - DISABLED (no-op function)
window.hideLoadingToast = function() {
    // Loading toast functionality has been disabled
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

// Utility function to wrap async operations with loading toast - DISABLED
window.withLoadingToast = async function(asyncFunction, loadingMessage = 'Loading...') {
    // Loading toast functionality has been disabled, just execute the function
    return await asyncFunction();
};

// Auto-integrate loading toasts with form submissions and fetch requests - DISABLED
function initFormLoadingToasts() {
    // Loading toast functionality has been disabled
    // This function does nothing now
}
