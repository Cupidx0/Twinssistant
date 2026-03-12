import axios from 'axios';

// Update this to your backend server URL
// For iOS simulator: http://localhost:5000
// For Android emulator: http://10.0.2.2:5000
// For physical device: http://YOUR_COMPUTER_IP:5000
const getBaseURL = () => {
  // Change this to your actual IP for physical device testing
  return 'http://127.0.0.1:5000'; // Change to http://192.168.x.x:5000 for physical device
};

export const API_BASE_URL = getBaseURL();

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for adding auth token
api.interceptors.request.use(
  async (config) => {
    try {
      const userData = await AsyncStorage.getItem('userData');
      if (userData) {
        const user = JSON.parse(userData);
        if (user.user_id) {
          config.headers['X-User-ID'] = user.user_id;
        }
      }
    } catch (error) {
      console.warn('Error retrieving user data:', error);
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      // Unauthorized - clear user data and redirect to login
      await AsyncStorage.removeItem('userData');
    }
    return Promise.reject(error);
  }
)
export const ChatAPI = {
  fetchAssistantResponse: async (question) => {
    try {
      // axios.post takes (url, data, config). We only need to send the JSON body.
      const response = await api.post('/api/chat', { question });
      return response.data;
    } catch (error) {
      throw error;
    }
  },
};
