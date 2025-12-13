// Theme toggle functionality
(function() {
    const themeToggle = document.getElementById('theme-toggle');
    const themeIcon = document.getElementById('theme-icon');
    const html = document.documentElement;
    
    // Get saved theme or default to light
    const savedTheme = localStorage.getItem('theme') || 'light';
    
    // Apply saved theme
    function applyTheme(theme) {
        html.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
        
        // Update icon
        if (themeIcon) {
            if (theme === 'dark') {
                themeIcon.innerHTML = '☀️'; // Sun icon for dark mode (click to switch to light)
            } else {
                themeIcon.innerHTML = '🌙'; // Moon icon for light mode (click to switch to dark)
            }
        }
    }
    
    // Initialize theme on page load
    applyTheme(savedTheme);
    
    // Toggle theme on button click
    if (themeToggle) {
        themeToggle.addEventListener('click', function() {
            const currentTheme = html.getAttribute('data-theme') || 'light';
            const newTheme = currentTheme === 'light' ? 'dark' : 'light';
            applyTheme(newTheme);
        });
    }
})();

