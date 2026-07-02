import axios from "axios";
import { auth } from "./Firebase";

const getBaseURL = () => {
  const envBaseUrl = import.meta.env.VITE_API_BASE_URL;
  return envBaseUrl || "http://127.0.0.1:5000";
};

export const API_BASE_URL = getBaseURL();

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,
  headers: {
    "Content-Type": "application/json",
  },
});

api.interceptors.request.use(
  async (config) => {
    try {
      const token = await auth.currentUser?.getIdToken();
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    } catch (error) {
      console.warn("Error attaching auth token:", error);
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

  clearHistory: async (confirmation) => {
    const response = await api.post("/clear", { confirmation });
    return response.data;
  },
};
export const VoiceAPI = {
  
};
export const ConvertTextAPI = {
  convertFileToText: async (file) => {
    const formData = new FormData();
    formData.append("file", file);
    const response = await api.post("/cv/upload", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    });
    return response.data;
  },
  ReviewCV: async (target_role) => {
    const response = await api.post("/cv/review", { target_role });
    return response.data;
  },
  RewriteCV: async (target_role) => {
    const response = await api.post("/cv/rewrite", { target_role },
      {
        timeout: 60000,
        responseType: 'blob'
      }
    );
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
  addEvent: async (summary, dueDate) => {
    // Backend reads the field as "end" (ISO 8601); userId comes from the auth token
    const response = await api.post("/calendar/add", {
      summary,
      end: dueDate,
    });
    return response.data;
  },

  deleteEvent: async (eventId) => {
    const response = await api.delete("/calendar/delete", {
      data: { eventId },
    });
    return response.data;
  },

  fetchEvents: async () => {
    const response = await api.post("/calendar/get", {});
    const payload = response.data;
    const events = Array.isArray(payload?.events)
      ? payload.events
      : payload?.events?.events;
    return events || [];
  },
};
