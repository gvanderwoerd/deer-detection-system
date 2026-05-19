/**
 * Shared API client utility for making HTTP requests
 * Used by app.js, cameras.js, and other pages
 */

async function apiCall(endpoint, method = 'GET', data = null) {
    try {
        const options = {
            method: method,
            headers: {
                'Content-Type': 'application/json'
            }
        };

        if (data && method !== 'GET') {
            options.body = JSON.stringify(data);
        }

        const response = await fetch(`/api${endpoint}`, options);
        const result = await response.json();

        return result;
    } catch (error) {
        console.error('API call failed:', error);
        return { success: false, error: error.message };
    }
}
