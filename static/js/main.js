/**
 * AuctionHub - Main JavaScript File
 */

// Helper Functions
function formatCurrency(amount) {
    return '$' + parseFloat(amount).toFixed(2).replace(/\d(?=(\d{3})+\.)/g, '$&,');
}

function calculateTimeLeft(endTime) {
    const now = new Date();
    const end = new Date(endTime);
    const diff = end - now;
    
    if (diff <= 0) {
        return 'Ended';
    }
    
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
    
    let result = '';
    if (days > 0) {
        result += days + 'd ';
    }
    if (hours > 0 || days > 0) {
        result += hours + 'h ';
    }
    result += minutes + 'm';
    
    return result;
}

// Countdown Timer for Auctions
function updateAuctionTimers() {
    const timers = document.querySelectorAll('.auction-timer');
    
    timers.forEach(timer => {
        const endTime = timer.getAttribute('data-end-time');
        if (endTime) {
            const timeLeft = calculateTimeLeft(endTime);
            timer.textContent = timeLeft;
            
            // Apply styling based on time left
            if (timeLeft === 'Ended') {
                timer.classList.add('text-red-600');
                timer.closest('.auction-card')?.classList.add('opacity-70');
            } else if (timeLeft.includes('h') && !timeLeft.includes('d')) {
                timer.classList.add('text-yellow-600');
            }
        }
    });
}

// Setup Toggleable Password Fields
function setupPasswordToggles() {
    const toggles = document.querySelectorAll('.password-toggle');
    
    toggles.forEach(toggle => {
        toggle.addEventListener('click', function() {
            const input = document.getElementById(this.getAttribute('data-target'));
            
            if (input.type === 'password') {
                input.type = 'text';
                this.innerHTML = '<i class="fas fa-eye-slash"></i>';
            } else {
                input.type = 'password';
                this.innerHTML = '<i class="fas fa-eye"></i>';
            }
        });
    });
}

// Setup Notifications Dropdown
function setupNotifications() {
    const trigger = document.getElementById('notifications-toggle');
    const dropdown = document.getElementById('notifications-dropdown');
    
    if (trigger && dropdown) {
        trigger.addEventListener('click', function(e) {
            e.stopPropagation();
            dropdown.classList.toggle('hidden');
        });
        
        document.addEventListener('click', function(e) {
            if (!dropdown.contains(e.target) && e.target !== trigger) {
                dropdown.classList.add('hidden');
            }
        });
    }
}

// Setup Profile Dropdown
function setupProfileDropdown() {
    const trigger = document.getElementById('profile-dropdown-toggle');
    const dropdown = document.getElementById('profile-dropdown');
    
    if (trigger && dropdown) {
        trigger.addEventListener('click', function(e) {
            e.stopPropagation();
            dropdown.classList.toggle('hidden');
        });
        
        document.addEventListener('click', function(e) {
            if (!dropdown.contains(e.target) && e.target !== trigger) {
                dropdown.classList.add('hidden');
            }
        });
    }
}

// Real-time Bid Updates with WebSockets (placeholder)
function setupLiveBidding() {
    // This would typically connect to a WebSocket server
    // For demonstration, we're just using a mock function
    console.log('Setting up live bidding...');
    
    // Simulate receiving a bid update
    setTimeout(() => {
        console.log('Received bid update');
        const randomProducts = document.querySelectorAll('.auction-card');
        if (randomProducts.length > 0) {
            const randomProduct = randomProducts[Math.floor(Math.random() * randomProducts.length)];
            const bidElement = randomProduct.querySelector('.current-bid');
            
            if (bidElement) {
                const currentBid = parseFloat(bidElement.getAttribute('data-amount') || 0);
                const newBid = currentBid + Math.floor(Math.random() * 50) + 10;
                
                bidElement.setAttribute('data-amount', newBid);
                bidElement.textContent = formatCurrency(newBid);
                
                // Flash animation
                bidElement.classList.add('text-green-600', 'font-bold');
                setTimeout(() => {
                    bidElement.classList.remove('text-green-600', 'font-bold');
                }, 2000);
            }
        }
    }, 10000);
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Initialize auction timers and update every minute
    updateAuctionTimers();
    setInterval(updateAuctionTimers, 60000);
    
    // Setup password toggles
    setupPasswordToggles();
    
    // Setup dropdowns
    setupNotifications();
    setupProfileDropdown();
    
    // Setup sidebar toggle for mobile
    const sidebarToggle = document.getElementById('sidebar-toggle');
    const sidebar = document.getElementById('sidebar');
    
    if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener('click', function() {
            sidebar.classList.toggle('hidden');
        });
    }
    
    // Set up live bidding (if applicable)
    if (document.querySelector('.auction-card')) {
        setupLiveBidding();
    }
    
    // Set active navigation items based on URL
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.sidebar-item');
    
    navLinks.forEach(link => {
        const href = link.getAttribute('href');
        if (href && currentPath.includes(href) && href !== '/') {
            link.classList.add('active');
        } else if (href === '/' && currentPath === '/') {
            link.classList.add('active');
        }
    });
}); 