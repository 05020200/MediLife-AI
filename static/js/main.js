/**
 * MediLife AI - Main JavaScript Entrypoint
 */

document.addEventListener('DOMContentLoaded', () => {
    // 0. Calculate spacing based on navbar height
    const adjustNavbarSpacing = () => {
        const navbar = document.querySelector('.custom-navbar');
        if (navbar) {
            const height = navbar.offsetHeight;
            document.documentElement.style.setProperty('--navbar-height', height + 'px');
        }
    };
    adjustNavbarSpacing();
    window.addEventListener('resize', adjustNavbarSpacing);

    // 1. Navigation scroll state handler and page specific setups
    const navbar = document.querySelector('.custom-navbar');
    const heroSection = document.querySelector('.hero-section');
    
    if (navbar) {
        const handleScroll = () => {
            if (!heroSection) {
                // If there's no hero section (like login/register/dashboard), keep it solid
                navbar.classList.add('navbar-solid');
            } else {
                navbar.classList.remove('navbar-solid');
                if (window.scrollY > 50) {
                    navbar.classList.add('scrolled');
                } else {
                    navbar.classList.remove('scrolled');
                }
            }
        };
        
        handleScroll();
        window.addEventListener('scroll', handleScroll);
    }

    // Scroll Active Link Highlighting
    const navLinks = document.querySelectorAll('.custom-navbar .nav-link');
    const sections = document.querySelectorAll('section[id]');
    
    const highlightNavbar = () => {
        let scrollY = window.pageYOffset;
        sections.forEach(current => {
            const sectionHeight = current.offsetHeight;
            const sectionTop = current.offsetTop - 120;
            const sectionId = current.getAttribute('id');
            
            if (scrollY > sectionTop && scrollY <= sectionTop + sectionHeight) {
                document.querySelectorAll('.custom-navbar .nav-link[href*=' + sectionId + ']').forEach(el => {
                    el.classList.add('active');
                });
            } else {
                document.querySelectorAll('.custom-navbar .nav-link[href*=' + sectionId + ']').forEach(el => {
                    el.classList.remove('active');
                });
            }
        });
    };
    if (sections.length > 0) {
        window.addEventListener('scroll', highlightNavbar);
    }

    // Lightweight Scroll Reveal/Fade-in
    const animatedElements = document.querySelectorAll('.animate-on-scroll');
    const checkScrollReveal = () => {
        animatedElements.forEach(el => {
            const rect = el.getBoundingClientRect();
            const isVisible = (rect.top <= window.innerHeight * 0.85);
            if (isVisible) {
                el.classList.add('appear');
            }
        });
    };
    if (animatedElements.length > 0) {
        window.addEventListener('scroll', checkScrollReveal);
        checkScrollReveal(); // Initial call
    }

    // Animated Numbers Counter
    const statsSection = document.getElementById('stats-section');
    const counters = document.querySelectorAll('.stat-counter-number');
    let countTriggered = false;
    
    const startCounting = () => {
        counters.forEach(counter => {
            const target = parseInt(counter.getAttribute('data-target'));
            const duration = 2000; // ms
            const stepTime = Math.max(Math.floor(duration / target), 15);
            let current = 0;
            
            const timer = setInterval(() => {
                current += Math.ceil(target / (duration / stepTime));
                if (current >= target) {
                    counter.innerText = target + (counter.getAttribute('data-suffix') || '');
                    clearInterval(timer);
                } else {
                    counter.innerText = current;
                }
            }, stepTime);
        });
    };

    const checkStatsScroll = () => {
        if (!statsSection || countTriggered) return;
        const rect = statsSection.getBoundingClientRect();
        const isVisible = (rect.top <= window.innerHeight * 0.85);
        if (isVisible) {
            countTriggered = true;
            startCounting();
        }
    };
    if (statsSection) {
        window.addEventListener('scroll', checkStatsScroll);
        checkStatsScroll();
    }

    // 2. Initialize Bootstrap Tooltips (if any exist)
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map((tooltipTriggerEl) => {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // 3. Initialize Bootstrap Popovers (if any exist)
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map((popoverTriggerEl) => {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // 4. Contact Form Simulation Validation
    const contactForm = document.getElementById('contactForm');
    if (contactForm) {
        contactForm.addEventListener('submit', (e) => {
            e.preventDefault();
            
            // Extract values
            const name = document.getElementById('contactName').value;
            const email = document.getElementById('contactEmail').value;
            
            // Client side mock feedback - clean modal/toast alert
            alert(`Thank you, ${name}! Your inquiry has been logged. We will contact you at ${email} shortly.`);
            
            // Reset form
            contactForm.reset();
        });
    }

    // 5. Toast Auto-fade handler
    document.querySelectorAll('.toast').forEach(function(toastEl) {
        setTimeout(function() {
            // Check if bootstrap is defined and toast instance exists/can be created
            if (typeof bootstrap !== 'undefined') {
                const toast = bootstrap.Toast.getOrCreateInstance(toastEl);
                if (toast) {
                    toast.hide();
                }
            }
        }, 5000);
    });

    // 6. Global Submit Spinner Loader
    document.addEventListener('submit', function(e) {
        const form = e.target;
        // Skip for simulation forms or specific non-redirect operations
        if (form.id === 'contactForm') return;

        const submitBtn = form.querySelector('button[type="submit"]');
        if (submitBtn) {
            // Let HTML5 browser validation execute first
            setTimeout(() => {
                if (form.checkValidity()) {
                    submitBtn.disabled = true;
                    // Retain icon if possible or show standard spinner
                    submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin me-2"></i> Processing...';
                }
            }, 30);
        }
    });

    // 7. Global Bootstrap Modal Backdrop & Scroll Lock Cleanup
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('hidden.bs.modal', () => {
            document.body.classList.remove('modal-open');
            document.body.style.removeProperty('padding-right');
            document.body.style.removeProperty('overflow');
            document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
        });
    });

    // 8. Verify script activation
    console.log('%cMediLife AI client engine active.', 'color: #1e3a8a; font-weight: bold;');
});
