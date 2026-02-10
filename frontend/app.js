// Configuration
const API_BASE_URL = window.location.protocol === 'file:' ? 'http://localhost:8000' : window.location.origin;
let conversationId = null;
let username = null;
let feedbackReasonCodes = {}; // Will be loaded from API

// DOM Elements
const usernameModal = document.getElementById('username-modal');
const usernameForm = document.getElementById('username-form');
const usernameInput = document.getElementById('username-input');
const mainContainer = document.getElementById('main-container');
const userInfo = document.getElementById('user-info');
const chatForm = document.getElementById('chat-form');
const messageInput = document.getElementById('message-input');
const chatMessages = document.getElementById('chat-messages');
const sendButton = document.getElementById('send-button');
const loadingIndicator = document.getElementById('loading-indicator');
const feedbackModal = document.getElementById('feedback-modal');
const feedbackReasonForm = document.getElementById('feedback-reason-form');
const feedbackCancelBtn = document.getElementById('feedback-cancel-btn');
const reasonCodesContainer = document.getElementById('reason-codes-container');
let currentFeedbackRecordId = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Check if username is stored
    const storedUsername = localStorage.getItem('helpdesk_username');
    if (storedUsername) {
        username = storedUsername;
        showMainInterface();
    } else {
        showUsernameModal();
    }
    
    // Username form handler
    usernameForm.addEventListener('submit', handleUsernameSubmit);
    
    // Chat form handler
    chatForm.addEventListener('submit', handleSubmit);
    messageInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit(e);
        }
    });
    
    // Feedback form handlers
    feedbackReasonForm.addEventListener('submit', handleFeedbackSubmit);
    feedbackCancelBtn.addEventListener('click', closeFeedbackModal);
    
    // Load feedback reason codes
    loadFeedbackReasonCodes();
});

// Handle username submission
function handleUsernameSubmit(e) {
    e.preventDefault();
    const inputUsername = usernameInput.value.trim();
    if (inputUsername) {
        username = inputUsername;
        localStorage.setItem('helpdesk_username', username);
        showMainInterface();
    }
}

// Show main interface
function showMainInterface() {
    usernameModal.style.display = 'none';
    mainContainer.style.display = 'flex';
    userInfo.textContent = `Logged in as: ${username}`;
    messageInput.focus();
}

// Show username modal
function showUsernameModal() {
    usernameModal.style.display = 'flex';
    mainContainer.style.display = 'none';
    usernameInput.focus();
}

// Handle form submission
async function handleSubmit(e) {
    e.preventDefault();
    
    const message = messageInput.value.trim();
    if (!message) return;
    
    // Add user message to UI
    addMessageToUI('user', message);
    messageInput.value = '';
    
    // Show loading indicator
    showLoading(true);
    sendButton.disabled = true;
    
    try {
        // Prepare request
        const requestBody = {
            message: message,
            username: username,
            conversation_id: conversationId,
            history: getConversationHistory()
        };
        
        // Call API
        const response = await fetch(`${API_BASE_URL}/api/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestBody)
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Failed to get response');
        }
        
        const data = await response.json();
        
        // Update conversation ID
        conversationId = data.conversation_id;
        
        // Add assistant response to UI
        addMessageToUI('assistant', data.response, {
            confidence: data.confidence,
            source: data.source,
            requiresEscalation: data.requires_escalation,
            conversationRecordId: data.conversation_record_id
        });
        
    } catch (error) {
        console.error('Error:', error);
        addMessageToUI('assistant', 
            `I'm sorry, I encountered an error: ${error.message}. Please try again or contact support.`,
            { error: true }
        );
    } finally {
        showLoading(false);
        sendButton.disabled = false;
        messageInput.focus();
    }
}

// Add message to UI
function addMessageToUI(role, content, metadata = {}) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    
    // Store conversation record ID for feedback
    if (metadata.conversationRecordId) {
        messageDiv.setAttribute('data-conversation-id', metadata.conversationRecordId);
    }
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    const p = document.createElement('p');
    p.textContent = content;
    contentDiv.appendChild(p);
    
    messageDiv.appendChild(contentDiv);
    
    // Add timestamp
    const timeDiv = document.createElement('div');
    timeDiv.className = 'message-time';
    timeDiv.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    messageDiv.appendChild(timeDiv);
    
    // Add metadata badge for assistant messages
    if (role === 'assistant' && metadata.source) {
        const badge = document.createElement('div');
        badge.style.cssText = 'font-size: 10px; color: #667eea; margin-top: 4px; padding: 0 4px;';
        badge.textContent = `Source: ${metadata.source}${metadata.requiresEscalation ? ' | Escalation recommended' : ''}`;
        messageDiv.appendChild(badge);
    }
    
    // Add feedback buttons for assistant messages
    if (role === 'assistant' && metadata.conversationRecordId) {
        const feedbackContainer = document.createElement('div');
        feedbackContainer.className = 'feedback-container';
        feedbackContainer.style.cssText = 'display: flex; gap: 8px; margin-top: 8px; align-items: center;';
        
        const thumbsUpBtn = document.createElement('button');
        thumbsUpBtn.className = 'feedback-btn feedback-thumbs-up';
        thumbsUpBtn.innerHTML = '👍';
        thumbsUpBtn.title = 'This was helpful';
        thumbsUpBtn.onclick = () => submitFeedback(metadata.conversationRecordId, 'thumbs_up');
        
        const thumbsDownBtn = document.createElement('button');
        thumbsDownBtn.className = 'feedback-btn feedback-thumbs-down';
        thumbsDownBtn.innerHTML = '👎';
        thumbsDownBtn.title = 'This was not helpful';
        thumbsDownBtn.onclick = () => showFeedbackModal(metadata.conversationRecordId);
        
        feedbackContainer.appendChild(thumbsUpBtn);
        feedbackContainer.appendChild(thumbsDownBtn);
        messageDiv.appendChild(feedbackContainer);
    }
    
    chatMessages.appendChild(messageDiv);
    
    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Get conversation history from UI
function getConversationHistory() {
    const messages = [];
    const messageElements = chatMessages.querySelectorAll('.message');
    
    messageElements.forEach((element) => {
        const role = element.classList.contains('user') ? 'user' : 'assistant';
        const content = element.querySelector('.message-content p').textContent;
        
        // Skip the initial greeting message
        if (messages.length === 0 && role === 'assistant' && content.includes('Hello!')) {
            return;
        }
        
        messages.push({
            role: role,
            content: content
        });
    });
    
    return messages;
}

// Show/hide loading indicator
function showLoading(show) {
    loadingIndicator.style.display = show ? 'flex' : 'none';
}

// Health check on load
async function checkAPIHealth() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/health`);
        if (!response.ok) {
            console.warn('API health check failed');
            addMessageToUI('assistant', 
                'Warning: Unable to connect to the backend API. Please ensure the server is running on http://localhost:8000',
                { error: true }
            );
        }
    } catch (error) {
        console.error('Health check error:', error);
        addMessageToUI('assistant', 
            'Warning: Unable to connect to the backend API. Please ensure the server is running on http://localhost:8000',
            { error: true }
        );
    }
}

// Check API health when page loads
window.addEventListener('load', () => {
    setTimeout(checkAPIHealth, 1000);
});

// Load feedback reason codes from API
async function loadFeedbackReasonCodes() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/feedback/reason-codes`);
        if (response.ok) {
            const data = await response.json();
            feedbackReasonCodes = data.reason_codes;
            populateReasonCodes();
        }
    } catch (error) {
        console.error('Error loading feedback reason codes:', error);
    }
}

// Populate reason codes in modal
function populateReasonCodes() {
    reasonCodesContainer.innerHTML = '';
    for (const [code, label] of Object.entries(feedbackReasonCodes)) {
        const labelElement = document.createElement('label');
        labelElement.style.cssText = 'display: flex; align-items: center; padding: 12px; border: 2px solid #e0e0e0; border-radius: 8px; margin-bottom: 8px; cursor: pointer; transition: all 0.2s;';
        labelElement.onmouseover = () => labelElement.style.borderColor = '#667eea';
        labelElement.onmouseout = () => {
            if (!labelElement.querySelector('input').checked) {
                labelElement.style.borderColor = '#e0e0e0';
            }
        };
        
        const radio = document.createElement('input');
        radio.type = 'radio';
        radio.name = 'reason_code';
        radio.value = code;
        radio.required = true;
        radio.onchange = () => {
            document.querySelectorAll('#reason-codes-container label').forEach(l => {
                if (l.querySelector('input').checked) {
                    l.style.borderColor = '#667eea';
                    l.style.background = '#f0f4ff';
                } else {
                    l.style.borderColor = '#e0e0e0';
                    l.style.background = 'white';
                }
            });
        };
        
        const span = document.createElement('span');
        span.textContent = label;
        span.style.marginLeft = '8px';
        
        labelElement.appendChild(radio);
        labelElement.appendChild(span);
        reasonCodesContainer.appendChild(labelElement);
    }
}

// Show feedback modal for thumbs down
function showFeedbackModal(recordId) {
    currentFeedbackRecordId = recordId;
    feedbackModal.style.display = 'flex';
    feedbackReasonForm.reset();
    document.querySelectorAll('#reason-codes-container label').forEach(l => {
        l.style.borderColor = '#e0e0e0';
        l.style.background = 'white';
    });
}

// Close feedback modal
function closeFeedbackModal() {
    feedbackModal.style.display = 'none';
    currentFeedbackRecordId = null;
    feedbackReasonForm.reset();
}

// Handle feedback form submission
async function handleFeedbackSubmit(e) {
    e.preventDefault();
    
    const formData = new FormData(feedbackReasonForm);
    const reasonCode = formData.get('reason_code');
    const notes = document.getElementById('feedback-notes').value.trim();
    
    if (!reasonCode) {
        alert('Please select a reason');
        return;
    }
    
    await submitFeedback(currentFeedbackRecordId, 'thumbs_down', reasonCode, notes);
    closeFeedbackModal();
}

// Submit feedback to backend
async function submitFeedback(recordId, rating, reasonCode = null, notes = null) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/feedback`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                conversation_record_id: recordId,
                rating: rating,
                reason_code: reasonCode,
                notes: notes
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Failed to submit feedback');
        }
        
        const data = await response.json();
        
        // Update UI to show feedback was submitted
        const messageDiv = document.querySelector(`[data-conversation-id="${recordId}"]`);
        if (messageDiv) {
            const feedbackContainer = messageDiv.querySelector('.feedback-container');
            if (feedbackContainer) {
                feedbackContainer.innerHTML = '';
                const feedbackBadge = document.createElement('span');
                feedbackBadge.style.cssText = 'font-size: 12px; color: #4caf50; margin-top: 8px;';
                feedbackBadge.textContent = rating === 'thumbs_up' ? '✓ Thank you for your feedback!' : '✓ Feedback submitted. Thank you!';
                feedbackContainer.appendChild(feedbackBadge);
                
                // Disable feedback buttons
                const buttons = messageDiv.querySelectorAll('.feedback-btn');
                buttons.forEach(btn => {
                    btn.disabled = true;
                    btn.style.opacity = '0.5';
                    btn.style.cursor = 'not-allowed';
                });
            }
        }
        
        console.log('Feedback submitted:', data);
    } catch (error) {
        console.error('Error submitting feedback:', error);
        alert('Failed to submit feedback. Please try again.');
    }
}
