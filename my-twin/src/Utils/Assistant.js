import axios from "axios";

const getBaseURL = () => {
  const envBaseUrl = import.meta.env.VITE_API_BASE_URL;
  return envBaseUrl || "http://127.0.0.1:5000";
};

export const API_BASE_URL = getBaseURL();

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    "Content-Type": "application/json",
  },
});

api.interceptors.request.use(
  (config) => {
    try {
      const userData = localStorage.getItem("userData");
      if (userData) {
        const user = JSON.parse(userData);
        if (user?.user_id) {
          config.headers["X-User-ID"] = user.user_id;
        }
      }
    } catch (error) {
      console.warn("Error retrieving user data:", error);
    }
    return config;
  },
  (error) => Promise.reject(error)
);

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      try {
        localStorage.removeItem("userData");
      } catch (storageError) {
        console.warn("Error clearing user data:", storageError);
      }
    }
    return Promise.reject(error);
  }
);

export const ChatAPI = {
  fetchAssistantResponse: async (question) => {
    const response = await api.post("/api/chat", { question });
    return response.data;
  },

  fetchFit: async (fit) => {
    const response = await api.post("/outfit", { fit });
    return response.data;
  },
};
export const ConvertTextAPI = {
  convertFileToText: async (file) => {
    const formData = new FormData();
    formData.append("file", file);
    const response = await api.post("/convertText", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    });
    return response.data;
  },
};
export const WeatherAPI = {
  fetchWeather: async () => {
    const response = await api.post("/weather", {
      location: "London",
    });
    return response.data;
  },

  fetchSeason: async (season) => {
    const response = await api.post("/holiday_season", { season });
    return response.data;
  },
};

export const CalendarAPI = {
  addEvent: async (summary, dueDate, user) => {
    const response = await api.post("/calendar/add", {
      summary,
      dueDate,
      userId: user?.uid || user?.email,
    });
    return response.data;
  },

  fetchEvents: async () => {
    const response = await api.post("/calendar/get");
    const payload = response.data;
    const events = Array.isArray(payload?.events)
      ? payload.events
      : payload?.events?.events;
    return events || [];
  },
};
