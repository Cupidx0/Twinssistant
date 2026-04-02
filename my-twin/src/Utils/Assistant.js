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
  fetchFit :async (fit)=> {
    try{
        const response = await api.post("/outfit",{ fit });
          return response.data;
    }catch(error){
        throw error;
    }
  },
};
export const WeatherAPI = {
  fetchWeather : async ()=>{
                try{
                        const res = await api.post("/weather", {
                                location: "London"
                        });
                        return res.data;
                }catch(error){
                    throw error;
        
                }
        },
};
export const CalendarAPI = {
    addEvent: async (summary, dueDate, user) => {
    try {
        await api.post("/calendar/add", {
        summary,
        dueDate,
        userId: user?.uid || user?.email,
        });
        // Refresh events after adding
        const refreshed = await fetch("/calendar/get", {
          body: JSON.stringify({ userId: user?.uid || user?.email }),
        });
        if (!refreshed.ok) {
          const errorData = await refreshed.json().catch(() => ({}));
          throw new Error(`HTTP error! status: ${refreshed.status}, message: ${errorData.error || 'Unknown error'}`);
        }
    } catch (error) {
        console.error("Error adding event:", error);
        toast.error("Failed to add task",error);
    }
    fetchEvents(); // Refresh events after adding
  },
  fetchEvents: async () => {
    try{
        const response = await api.post("/calendar/get");
        if (!response || !response.data) {
            throw new Error("No data received from server");
        }
        const payload = response.data;
        // Backend returns: { events: { events: [...], total_duration: "..." } }
        const events = Array.isArray(payload?.events)
          ? payload.events
          : payload?.events?.events;
        return events || [];
    }catch(error){
        console.error("Error fetching assistant response:", error);
        throw error;
    }
  },
};
