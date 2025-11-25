/**
 * EduLog - Base Template JavaScript
 * Handles sidebar, mobile menu, and other base template functionality
 */

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Initialize Lucide icons
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }

    // Mobile menu toggle function
    window.toggleMobileMenu = function() {
        const mobileMenu = document.getElementById("mobileMenu");
        if (mobileMenu) {
            mobileMenu.classList.toggle("d-none");
        }
    };

    // Sidebar and overlay elements
    const sidebar = document.getElementById("sidebar");
    const overlay = document.getElementById("overlay");
    const openSidebarBtn = document.getElementById("openSidebarBtn");
    const closeSidebarBtn = document.getElementById("closeSidebarBtn");

    // Check if we're on mobile
    function isMobile() {
        return window.innerWidth < 768;
    }
    
    // Check if we're on tablet
    function isTablet() {
        return window.innerWidth >= 768 && window.innerWidth < 992;
    }
    
    // Check if we're on desktop
    function isDesktop() {
        return window.innerWidth >= 992;
    }

    // Only allow sidebar toggle on mobile (if sidebar exists)
    if (sidebar && openSidebarBtn) {
        openSidebarBtn.onclick = () => {
            if (isMobile()) {
                sidebar.style.transform = "translateX(0)";
                if (overlay) overlay.style.display = "block";
            }
        };
    }

    if (sidebar && closeSidebarBtn) {
        closeSidebarBtn.onclick = () => {
            if (isMobile()) {
                sidebar.style.transform = "translateX(-100%)";
                if (overlay) overlay.style.display = "none";
            }
        };
    }

    if (sidebar && overlay) {
        overlay.onclick = () => {
            if (isMobile()) {
                sidebar.style.transform = "translateX(-100%)";
                overlay.style.display = "none";
            }
        };
    }

    // Handle window resize - ensure sidebar behaves correctly (if sidebar exists)
    if (sidebar) {
        function handleResize() {
            const width = window.innerWidth;
            if (width >= 768) {
                // Tablet and Desktop: Remove inline transform style to let CSS take over
                sidebar.style.removeProperty('transform');
                if (overlay) overlay.style.display = "none";
            } else {
                // Mobile: Ensure sidebar is hidden if not explicitly opened
                if (!sidebar.classList.contains('open')) {
                    sidebar.style.transform = "translateX(-100%)";
                }
                if (overlay) overlay.style.display = sidebar.classList.contains('open') ? "block" : "none";
            }
        }
        
        window.addEventListener('resize', handleResize);

        // Ensure sidebar behaves correctly on page load
        const width = window.innerWidth;
        if (width >= 768) {
            // Tablet and Desktop: Remove any inline transform style to let CSS !important rule take over
            sidebar.style.removeProperty('transform');
            if (overlay) overlay.style.display = "none";
        } else {
            // Mobile: Ensure sidebar starts hidden
            sidebar.style.transform = "translateX(-100%)";
            if (overlay) overlay.style.display = "none";
        }
    }
});
