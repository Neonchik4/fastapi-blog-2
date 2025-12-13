// Liked posts page functionality - handles unlike animation and card removal
(function() {
    function setupLikedPostsPage() {
        const likedPostsList = document.querySelector('.articles-list');
        const noMessage = document.querySelector('.no-liked-message');
        
        if (!likedPostsList) return;
        
        // Override click handler for like buttons on this page
        likedPostsList.addEventListener('click', async (e) => {
            const button = e.target.closest('.like-button');
            if (!button) return;
            
            e.preventDefault();
            e.stopPropagation();
            
            // Check if button is already processing
            if (button.disabled) return;
            
            const postId = parseInt(button.getAttribute('data-post-id'));
            const userId = window.likesManager?.getCurrentUserId();
            
            if (!userId || isNaN(postId)) return;
            
            button.disabled = true;
            
            try {
                const response = await fetch('/api/likes/toggle', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        post_id: postId,
                        liked: true
                    })
                });
                
                if (!response.ok) throw new Error('Failed to toggle like');
                
                const result = await response.json();
                
                if (!result.liked) {
                    // Animate and remove card when unliked
                    const card = button.closest('.article-card');
                    if (card) {
                        card.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
                        card.style.opacity = '0';
                        card.style.transform = 'scale(0.95)';
                        
                        setTimeout(() => {
                            card.remove();
                            
                            // Check if there are no more cards
                            const remainingCards = likedPostsList.querySelectorAll('.article-card');
                            if (remainingCards.length === 0) {
                                // Reload the page to show empty message and update pagination
                                window.location.reload();
                            }
                        }, 300);
                    }
                } else {
                    button.disabled = false;
                }
            } catch (error) {
                console.error('Error toggling like:', error);
                button.disabled = false;
                alert('Произошла ошибка при обновлении лайка');
            }
        }, true); // Use capture to intercept before likes.js
    }
    
    // Initialize on page load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setupLikedPostsPage);
    } else {
        setupLikedPostsPage();
    }
})();
