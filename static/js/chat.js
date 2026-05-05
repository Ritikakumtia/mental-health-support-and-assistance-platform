// Chatbot functionality for MindSarthi AI

document.addEventListener('DOMContentLoaded', function() {
    const chatContainer = document.getElementById('chat-container');
    const messageInput = document.getElementById('message-input');
    const sendButton = document.getElementById('send-button');
    const conversationHistory = [];

    // Function to add message to chat
    function addMessage(content, sender) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}`;
        messageDiv.innerHTML = `<strong>${sender === 'user' ? 'You' : 'MindSarthi AI'}:</strong> ${content}`;
        chatContainer.appendChild(messageDiv);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    // Function to load chat history
    async function loadChatHistory() {
        try {
            const response = await fetch('/api/chatbot/history', {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' }
            });
            if (response.ok) {
                const data = await response.json();
                data.history.forEach(chat => {
                    addMessage(chat.user_message, 'user');
                    addMessage(chat.bot_reply, 'bot');
                    conversationHistory.push({ role: 'user', content: chat.user_message });
                    conversationHistory.push({ role: 'assistant', content: chat.bot_reply });
                });
            }
        } catch (error) {
            console.log('No previous chat history found');
        }
    }

    // Function to send message
    async function sendMessage() {
        const message = messageInput.value.trim();
        if (!message) return;

        addMessage(message, 'user');
        conversationHistory.push({ role: 'user', content: message });
        messageInput.value = '';

        addMessage('Thinking...', 'bot');
        const botMessageDiv = chatContainer.lastChild;

        try {
            const response = await fetch('/api/chatbot', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message,
                    history: conversationHistory.slice(-8)
                })
            });
            const data = await response.json();
            botMessageDiv.innerHTML = `<strong>MindSarthi AI:</strong> ${data.reply || 'Sorry, I could not process that. Please try again.'}`;
            conversationHistory.push({ role: 'assistant', content: data.reply });
        } catch (error) {
            botMessageDiv.innerHTML = `<strong>MindSarthi AI:</strong> Sorry, I am unable to connect right now. Please try again later.`;
            console.error(error);
        }
    }

    // Load chat history on page load
    loadChatHistory();

    // Event listeners
    sendButton.addEventListener('click', sendMessage);
    messageInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });

    // Initial greeting
    setTimeout(() => {
        const welcomeMessage = "Hello! I'm MindSarthi AI, your mental health companion. How can I help you today?";
        addMessage(welcomeMessage, 'bot');
        conversationHistory.push({ role: 'assistant', content: welcomeMessage });
    }, 500);
});