// Configuration
const API_BASE_URL = 'http://localhost:8000';
let conversationId = null;
let username = null;

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
            requiresEscalation: data.requires_escalation
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
