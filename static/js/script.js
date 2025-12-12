document.addEventListener('DOMContentLoaded', function() {
    // Smooth scrolling for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
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
    // Auto-dismiss alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });
    // Course card hover effects
    const courseCards = document.querySelectorAll('.course-card');
    courseCards.forEach(card => {
        card.addEventListener('mouseenter', () => {
            card.style.transform = 'translateY(-5px)';
            card.style.boxShadow = '0 8px 25px rgba(0, 0, 0, 0.15)';
        });
        card.addEventListener('mouseleave', () => {
            card.style.transform = 'translateY(0)';
            card.style.boxShadow = '0 4px 6px rgba(0, 0, 0, 0.1)';
        });
    });

    // Progress bar animation
    const progressBars = document.querySelectorAll('.progress-bar');
    progressBars.forEach(bar => {
        const width = bar.getAttribute('aria-valuenow');
        if (width) {
            bar.style.width = '0%';
            setTimeout(() => {
                bar.style.width = width + '%';
            }, 100);
        }
    });
    // Form validation enhancement and loading state
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const submitBtn = this.querySelector('button[type="submit"]');
            if (submitBtn && !this.classList.contains('no-loading')) {
                submitBtn.classList.add('loading');
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Processing...';
            }
        });
    });

     // Responsive navigation (Bootstrap collapse)
    const navbarToggler = document.querySelector('.navbar-toggler');
    const navbarCollapse = document.querySelector('.navbar-collapse');
    if (navbarToggler && navbarCollapse) {
        navbarToggler.addEventListener('click', () => {
            navbarCollapse.classList.toggle('show');
        });
    }
    // Back to top button
    const backToTop = document.createElement('button');
    backToTop.innerHTML = '<i class="fas fa-arrow-up"></i>';
    backToTop.className = 'btn btn-primary back-to-top d-none';
    backToTop.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        z-index: 1000;
        border-radius: 50%;
        width: 50px;
        height: 50px;
        border: none;
        box-shadow: 0 2px 10px rgba(0,0,0,0.2);
    `;
    document.body.appendChild(backToTop);
    backToTop.addEventListener('click', () => {
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });

     window.addEventListener('scroll', () => {
        if (window.pageYOffset > 300) {
            backToTop.classList.remove('d-none');
        } else {
            backToTop.classList.add('d-none');
        }
    });
    // Image lazy loading
    const images = document.querySelectorAll('img[data-src]');
    const imageObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                img.src = img.dataset.src;
                img.classList.remove('lazy');
                imageObserver.unobserve(img);
            }
        });
    });
    images.forEach(img => imageObserver.observe(img));

    // Enhanced dropdown menus (hover on desktop)
    const dropdowns = document.querySelectorAll('.dropdown');
    dropdowns.forEach(dropdown => {
        const dropdownMenu = dropdown.querySelector('.dropdown-menu');
        if (dropdownMenu) {
            dropdown.addEventListener('mouseenter', () => {
                dropdownMenu.classList.add('show');
            });
            dropdown.addEventListener('mouseleave', () => {
                dropdownMenu.classList.remove('show');
            });
        }
    });

    // Course filter functionality (auto-submit on change)
    const filterForm = document.querySelector('form[action*="course_list"]');
    if (filterForm) {
        const selects = filterForm.querySelectorAll('select');
        const searchInput = filterForm.querySelector('input[name="search"]');
        selects.forEach(select => {
            select.addEventListener('change', () => {
                filterForm.submit();
            });
        });
        if (searchInput) {
            searchInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    filterForm.submit();
                }
            });
        }
    }

    // Lesson completion tracking (example: mark lesson as complete on button click)
    const lessonCompleteButtons = document.querySelectorAll('.lesson-complete-btn');
    lessonCompleteButtons.forEach(button => {
        button.addEventListener('click', async (e) => {
            e.preventDefault();
            const lessonId = button.dataset.lessonId;
            const progressBar = document.querySelector(`#progress-${lessonId}`);
            
            // Simulate API call to mark as complete (replace with actual AJAX/Fetch)
            try {
                // Example: Fetch to update progress
                const response = await fetch(`/api/lessons/${lessonId}/complete/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                    }
                });
                 if (response.ok) {
                    button.innerHTML = '<i class="fas fa-check text-success"></i> Completed';
                    button.classList.add('btn-success');
                    button.disabled = true;
                    
                    // Update progress bar
                    if (progressBar) {
                        const currentWidth = parseInt(progressBar.style.width) || 0;
                        progressBar.style.width = Math.min(100, currentWidth + 10) + '%';
                    }
                    
                    // Show success message
                    const alert = document.createElement('div');
                    alert.className = 'alert alert-success alert-dismissible fade show position-fixed';
                    alert.style.cssText = 'top: 20px; right: 20px; z-index: 1050; min-width: 250px;';
                    alert.innerHTML = `
                        <i class="fas fa-check-circle me-2"></i>Lesson completed!
                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                    `;
                    document.body.appendChild(alert);
                    setTimeout(() => alert.remove(), 3000);
                }
            } catch (error) {
                console.error('Error marking lesson complete:', error);
                alert('Error completing lesson. Please try again.');
            }
        });
    });
    // Quiz timer (if quiz pages exist)
    const quizTimers = document.querySelectorAll('.quiz-timer');
    quizTimers.forEach(timer => {
        const timeLimit = parseInt(timer.dataset.timeLimit) * 60; // Convert minutes to seconds
        let timeLeft = timeLimit;
        const updateTimer = () => {
            const minutes = Math.floor(timeLeft / 60);
            const seconds = timeLeft % 60;
            timer.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
            if (timeLeft > 0) {
                timeLeft--;
                setTimeout(updateTimer, 1000);
            } else {
                // Submit quiz automatically when time's up
                const quizForm = document.querySelector('#quiz-form');
                if (quizForm) {
                    quizForm.submit();
                }
            }
        };
        updateTimer();
    });
    // Discussion reply threading (toggle replies)
    const replyButtons = document.querySelectorAll('.reply-btn');
    replyButtons.forEach(button => {
        button.addEventListener('click', () => {
            const replyForm = button.nextElementSibling;
            if (replyForm) {
                replyForm.classList.toggle('d-none');
            }
        });
    });
});