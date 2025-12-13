// Likes functionality with API
(function() {
    // Get current user ID (if available)
    function getCurrentUserId() {
        // Try to get from meta tag or data attribute
        const userMeta = document.querySelector('meta[name="user-id"]');
        if (!userMeta || !userMeta.content || userMeta.content.trim() === '') {
            return null;
        }
        const userId = parseInt(userMeta.content);
        return isNaN(userId) ? null : userId;
    }
    
    // Check if post is liked by current user
    async function isLiked(postId, userId) {
        if (!userId) return false;
        try {
            const response = await fetch(`/api/likes/user/${userId}/post/${postId}`);
            if (!response.ok) {
                console.error('Error checking like status:', await response.text());
                return false;
            }
            return await response.json();
        } catch (error) {
            console.error('Error checking like status:', error);
            return false;
        }
    }
    
    // Toggle like status
    async function toggleLike(postId, userId, button = null) {
        if (!userId) {
            alert('Пожалуйста, войдите в систему, чтобы ставить лайки');
            return false;
        }
        
        try {
            // Show loading state if button is provided
            let originalContent = null;
            if (button) {
                // Store the entire button content structure
                originalContent = {
                    icon: button.querySelector('.like-icon')?.cloneNode(true),
                    text: button.querySelector('.like-text')?.cloneNode(true)
                };
                button.disabled = true;
                button.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>';
            }
            
            // Toggle the like status
            const response = await fetch('/api/likes/toggle', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    post_id: postId,
                    liked: true  // Always send true, the server will toggle it
                })
            });
            
            if (!response.ok) {
                throw new Error('Failed to toggle like');
            }
            
            const result = await response.json();
            
            // Update UI if button is provided
            if (button) {
                // Reconstruct the button content
                button.innerHTML = '';
                if (originalContent.icon) {
                    button.appendChild(originalContent.icon);
                }
                if (originalContent.text) {
                    button.appendChild(originalContent.text);
                }
                
                // Update the button state
                updateLikeButton(button, result.liked);
                button.disabled = false;
            }
            
            return result.liked;
            
        } catch (error) {
            console.error('Error toggling like:', error);
            alert('Произошла ошибка при обновлении лайка');
            if (button) {
                button.disabled = false;
                // Restore original content if available
                const icon = button.querySelector('.like-icon');
                const text = button.querySelector('.like-text');
                if (icon && text) {
                    button.innerHTML = '';
                    button.appendChild(icon);
                    button.appendChild(text);
                }
            }
            return false;
        }
    }
    
    // Get liked posts for current user
    async function getLikedPosts(userId) {
        if (!userId) return [];
        try {
            const response = await fetch(`/api/likes/user/${userId}`);
            if (!response.ok) {
                console.error('Error fetching liked posts:', await response.text());
                return [];
            }
            const likes = await response.json();
            return likes.map(like => like.post_id);
        } catch (error) {
            console.error('Error fetching liked posts:', error);
            return [];
        }
    }
    
    // Update like button appearance
    function updateLikeButton(button, isLiked) {
        if (!button) return;
        
        const icon = button.querySelector('.like-icon');
        const text = button.querySelector('.like-text');
        
        if (isLiked) {
            button.classList.add('liked');
            if (icon) {
                icon.style.fill = '#e91e63';
                icon.style.stroke = '#e91e63';
            }
            if (text) text.textContent = 'Лайкнуто';
        } else {
            button.classList.remove('liked');
            if (icon) {
                icon.style.fill = 'none';
                icon.style.stroke = '';
            }
            if (text) text.textContent = 'Лайк';
        }
    }
    
    // Initialize likes on page load
    async function initializeLikes() {
        const userId = getCurrentUserId();
        
        if (!userId) {
            // If user is not logged in, ensure all like buttons are in default state
            document.querySelectorAll('.like-button[data-post-id]').forEach(button => {
                updateLikeButton(button, false);
            });
            return;
        }
        
        // Update like buttons for all posts on the page
        const buttons = document.querySelectorAll('.like-button[data-post-id]');
        const promises = [];
        
        buttons.forEach(button => {
            const postId = parseInt(button.getAttribute('data-post-id'));
            if (!isNaN(postId)) {
                promises.push(
                    isLiked(postId, userId).then(isLiked => {
                        updateLikeButton(button, isLiked);
                    }).catch(error => {
                        console.error('Error initializing like button:', error);
                        updateLikeButton(button, false);
                    })
                );
            }
        });
        
        // Wait for all like status checks to complete
        await Promise.all(promises);
    }
    
    // Handle like button clicks
    function setupLikeButtons() {
        // Use event delegation with proper event handling
        document.addEventListener('click', async (e) => {
            const button = e.target.closest('.like-button');
            if (!button) return;
            
            // Prevent default behavior and stop propagation
            e.preventDefault();
            e.stopPropagation();
            
            // Check if button is already processing
            if (button.disabled) return;
            
            const postId = parseInt(button.getAttribute('data-post-id'));
            const userId = getCurrentUserId();
            
            if (isNaN(postId)) {
                console.error('Invalid post ID');
                return;
            }
            
            // Toggle like with proper error handling
            try {
                await toggleLike(postId, userId, button);
            } catch (error) {
                console.error('Error toggling like:', error);
                // Re-enable button if error occurred
                button.disabled = false;
            }
        });
    }
    
    // Export functions for use in other scripts
    window.likesManager = {
        getLikedPosts: getLikedPosts,
        isLiked: isLiked,
        toggleLike: toggleLike,
        getCurrentUserId: getCurrentUserId,
        initializeLikes: initializeLikes,
        updateLikeButton: updateLikeButton
    };
    
    // Initialize on page load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', async () => {
            await initializeLikes();
            setupLikeButtons();
        });
    } else {
        (async () => {
            await initializeLikes();
            setupLikeButtons();
        })();
    }
    
    // Re-initialize when content is dynamically loaded
    const observer = new MutationObserver((mutations) => {
        const shouldReinitialize = mutations.some(mutation => {
            return Array.from(mutation.addedNodes).some(node => {
                return node.nodeType === 1 && (
                    node.classList.contains('article-card') ||
                    node.querySelector('.article-card') ||
                    node.querySelector('.like-button')
                );
            });
        });
        
        if (shouldReinitialize) {
            setTimeout(async () => {
                await initializeLikes();
            }, 100);
        }
    });
    
    // Start observing the document body for changes
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
})();
