/**
 * EduLog - Main JavaScript File
 * Contains all custom JavaScript functionality for the application
 */

// ========================================
// Mobile Menu Icon Toggle (Base - Navbar)
// ========================================
document.addEventListener('DOMContentLoaded', function() {
    const mobileNav = document.getElementById('mobileNav');
    const mobileMenuIcon = document.getElementById('mobileMenuIcon');
    
    if (mobileNav && mobileMenuIcon) {
        mobileNav.addEventListener('show.bs.collapse', function() {
            mobileMenuIcon.classList.remove('bi-list');
            mobileMenuIcon.classList.add('bi-x');
        });
        
        mobileNav.addEventListener('hide.bs.collapse', function() {
            mobileMenuIcon.classList.remove('bi-x');
            mobileMenuIcon.classList.add('bi-list');
        });
    }
});

// ========================================
// Smooth Scroll for Anchor Links (Index Page)
// ========================================
document.addEventListener('DOMContentLoaded', function() {
    // Smooth scroll for "Learn More" button
    document.querySelectorAll('a[href="#features"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
});

// Note: Alert messages are now handled by Bootstrap Toasts in base.html

// ========================================
// Signup Form - Role-specific Field Management
// ========================================

// Make updateFormFields available globally so it can be called from onclick handlers
window.updateFormFields = function(role) {
    // Hide all role-specific fields
    var teacherFields = document.getElementById('teacher-specific');
    var studentFields = document.querySelectorAll('.student-specific-field');
    var parentFields = document.getElementById('parent-specific');
    
    // Hide all first
    if (teacherFields) teacherFields.style.display = 'none';
    if (studentFields) {
        studentFields.forEach(function(field) {
            field.style.display = 'none';
        });
    }
    if (parentFields) parentFields.style.display = 'none';
    
    // Show relevant fields based on role
    if (role === 'teacher' && teacherFields) {
        teacherFields.style.display = 'block';
    } else if (role === 'student' && studentFields) {
        studentFields.forEach(function(field) {
            field.style.display = 'block';
        });
    } else if (role === 'parent' && parentFields) {
        parentFields.style.display = 'block';
    }
};

// Initialize signup form on page load
document.addEventListener('DOMContentLoaded', function() {
    // Check if we're on the signup page by looking for the roleTabs element
    const roleTabs = document.getElementById('roleTabs');
    if (roleTabs) {
        // Show teacher fields by default since teacher tab is active
        updateFormFields('teacher');
        
        // Listen for tab changes
        var tabButtons = document.querySelectorAll('#roleTabs button');
        tabButtons.forEach(function(button) {
            button.addEventListener('shown.bs.tab', function(event) {
                var targetId = event.target.getAttribute('data-bs-target');
                if (targetId === '#teacher') {
                    updateFormFields('teacher');
                } else if (targetId === '#student') {
                    updateFormFields('student');
                } else if (targetId === '#parent') {
                    updateFormFields('parent');
                }
            });
        });
    }
});

