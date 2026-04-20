import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Button,
  colors,
  Divider,
  FormControl,
  FormControlLabel,
  MenuItem,
  Select,
  Switch,
  TextField,
  Typography,
} from "@mui/material";
import toast from "react-hot-toast";
import { useAuth } from "./AuthContext";
import { auth } from "../Utils/Firebase";
import { sendPasswordResetEmail, signOut, updateProfile } from "firebase/auth";

const SETTINGS_STORAGE_KEY = "twin:settings:v1";

const defaultSettings = {
  theme: "system",
  language: "en-GB",
  timezone: "auto",
  weekStartsOnMonday: true,
  notifications: {
    inApp: true,
    email: false,
    sms: false,
    dailyDigest: true,
  },
  privacy: {
    locationAccess: true,
    shareUsage: false,
    lockOnIdle: false,
  },
  personalization: {
    smartReplies: true,
    autoOutfit: true,
    calendarSync: true,
  },
};

const readSettings = () => {
  try {
    const raw = localStorage.getItem(SETTINGS_STORAGE_KEY);
    if (!raw) return defaultSettings;
    const parsed = JSON.parse(raw);
    return {
      ...defaultSettings,
      ...parsed,
      notifications: { ...defaultSettings.notifications, ...parsed.notifications },
      privacy: { ...defaultSettings.privacy, ...parsed.privacy },
      personalization: {
        ...defaultSettings.personalization,
        ...parsed.personalization,
      },
    };
  } catch (error) {
    console.warn("Failed to read settings, using defaults", error);
    return defaultSettings;
  }
};

function Settings() {
  const navigate = useNavigate();
  const { isLoggedIn, user } = useAuth();
  const [settings, setSettings] = useState(readSettings);
  const [displayName, setDisplayName] = useState("");

  useEffect(() => {
    setDisplayName(user?.displayName || "");
  }, [user]);

  useEffect(() => {
    localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(settings));
  }, [settings]);

  const updateGroupSetting = (group, key, value) => {
    setSettings((prev) => ({
      ...prev,
      [group]: {
        ...prev[group],
        [key]: value,
      },
    }));
  };

  const handleLogout = async () => {
    try {
      await signOut(auth);
      toast.success("Logged out");
      navigate("/login");
    } catch (error) {
      console.error("Logout failed:", error);
      toast.error("Failed to log out");
    }
  };

  const handleResetPassword = async () => {
    if (!user?.email) {
      toast.error("No email available for password reset");
      return;
    }
    try {
      await sendPasswordResetEmail(auth, user.email);
      toast.success("Password reset email sent");
    } catch (error) {
      console.error("Password reset failed:", error);
      toast.error("Failed to send password reset email");
    }
  };

  const handleSaveProfile = async () => {
    if (!auth.currentUser) {
      toast.error("Please log in to update your profile");
      return;
    }
    try {
      await updateProfile(auth.currentUser, { displayName });
      toast.success("Profile updated");
    } catch (error) {
      console.error("Profile update failed:", error);
      toast.error("Failed to update profile");
    }
  };

  const handleClearLocalData = () => {
    const keysToClear = [
      "AiReply",
      "userQuestion",
      "AiTasks",
      "pastDueTasks",
      "todoTasks",
      "calendarEvents",
    ];
    keysToClear.forEach((key) => localStorage.removeItem(key));
    toast.success("Local data cleared");
  };

  return (
    <main className="w-screen min-h-screen bg-background text-foreground p-6">
      <div className="max-w-5xl mx-auto flex flex-col gap-6">
        <header className="flex items-center justify-between gap-4">
          <div>
            <Typography variant="h4" className="text-foreground font-bold">
              Settings
            </Typography>
            <Typography variant="body2" className="text-muted-foreground">
              Manage your account, preferences, and privacy controls.
            </Typography>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outlined"
              color="inherit"
              onClick={() => navigate("/home")}
            >
              Back to Home
            </Button>
          </div>
        </header>

        <section className="rounded-md border border-border/50 bg-card p-5">
          <Typography variant="h6" className="text-card-foreground font-bold mb-2">
            Account
          </Typography>
          <Divider className="bg-border/50 mb-4" />

          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-2">
              <TextField
                label="Display name"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                inputProps={{ style: { color: "white" } }}
                InputLabelProps={{ style: { color: "#94a3b8" } }}
                className="bg-input"
                disabled={!isLoggedIn}
              />
              <div className="text-sm text-muted-foreground">
                {isLoggedIn && user?.email
                  ? `Signed in as ${user.email}`
                  : "You are not signed in"}
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="contained"
                  color="primary"
                  onClick={handleSaveProfile}
                  disabled={!isLoggedIn}
                >
                  Save Profile
                </Button>
                <Button
                  variant="outlined"
                  color="inherit"
                  onClick={handleResetPassword}
                  disabled={!isLoggedIn}
                >
                  Reset Password
                </Button>
                {isLoggedIn ? (
                  <Button variant="outlined" color="error" onClick={handleLogout}>
                    Log Out
                  </Button>
                ) : (
                  <>
                    <Button
                      variant="contained"
                      color="primary"
                      component={Link}
                      to="/login"
                    >
                      Log In
                    </Button>
                    <Button variant="outlined" component={Link} to="/register">
                      Register
                    </Button>
                  </>
                )}
              </div>
            </div>
          </div>
        </section>

        <section className="rounded-md border border-border/50 bg-card p-5">
          <Typography variant="h6" className="text-card-foreground font-bold mb-2">
            Preferences
          </Typography>
          <Divider className="bg-border/50 mb-4" />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <FormControl fullWidth>
              <Typography variant="caption" className="text-muted-foreground mb-1">
                Theme
              </Typography>
              <Select
                value={settings.theme}
                onChange={(e) =>
                  setSettings((prev) => ({ ...prev, theme: e.target.value }))
                }
                style={
                {
                  color:"white"
                }
              }
                size="small"
                className="bg-input text-foreground"
              >
                <MenuItem value="system">System</MenuItem>
                <MenuItem value="dark">Dark</MenuItem>
                <MenuItem value="light">Light</MenuItem>
              </Select>
            </FormControl>
            <FormControl fullWidth>
              <Typography variant="caption" className="text-muted-foreground mb-1">
                Language
              </Typography>
              <Select
                value={settings.language}
                onChange={(e) =>
                  setSettings((prev) => ({
                    ...prev,
                    language: e.target.value,
                  }))
                }
                style={{ color:"white" }}
                size="small"
                className="bg-input text-foreground"
              >
                <MenuItem value="en-GB">English (UK)</MenuItem>
                <MenuItem value="en-US">English (US)</MenuItem>
                <MenuItem value="fr-FR">French</MenuItem>
              </Select>
            </FormControl>
            <FormControl fullWidth 
            >
              <Typography variant="caption" className="text-muted-foreground mb-1">
                Timezone
              </Typography>
              <Select
                value={settings.timezone}
                onChange={(e) =>
                  setSettings((prev) => ({
                    ...prev,
                    timezone: e.target.value,
                  }))
                }
                style={{ color:"white" }}
                size="small"
                className="bg-input text-foreground"
              >
                <MenuItem value="auto" className="text-foreground">Auto</MenuItem>
                <MenuItem value="Europe/London" className="text-foreground">Europe/London</MenuItem>
                <MenuItem value="America/New_York" className="text-foreground">America/New York</MenuItem>
                <MenuItem value="Asia/Tokyo" className="text-foreground">Asia/Tokyo</MenuItem>
              </Select>
            </FormControl>
          </div>
          <div className="mt-4">
            <FormControlLabel
              control={
                <Switch
                  checked={settings.weekStartsOnMonday}
                  onChange={(e) =>
                    setSettings((prev) => ({
                      ...prev,
                      weekStartsOnMonday: e.target.checked,
                    }))
                  }
                />
              }
              label="Week starts on Monday"
            />
          </div>
        </section>

        <section className="rounded-md border border-border/50 bg-card p-5">
          <Typography variant="h6" className="text-card-foreground font-bold mb-2">
            Notifications
          </Typography>
          <Divider className="bg-border/50 mb-4" />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <FormControlLabel
              control={
                <Switch
                  checked={settings.notifications.inApp}
                  onChange={(e) =>
                    updateGroupSetting("notifications", "inApp", e.target.checked)
                  }
                />
              }
              label="In-app alerts"
            />
            <FormControlLabel
              control={
                <Switch
                  checked={settings.notifications.email}
                  onChange={(e) =>
                    updateGroupSetting(
                      "notifications",
                      "email",
                      e.target.checked
                    )
                  }
                />
              }
              label="Email notifications"
            />
            <FormControlLabel
              control={
                <Switch
                  checked={settings.notifications.sms}
                  onChange={(e) =>
                    updateGroupSetting("notifications", "sms", e.target.checked)
                  }
                />
              }
              label="SMS notifications"
            />
            <FormControlLabel
              control={
                <Switch
                  checked={settings.notifications.dailyDigest}
                  onChange={(e) =>
                    updateGroupSetting(
                      "notifications",
                      "dailyDigest",
                      e.target.checked
                    )
                  }
                />
              }
              label="Daily digest"
            />
          </div>
        </section>

        <section className="rounded-md border border-border/50 bg-card p-5">
          <Typography variant="h6" className="text-card-foreground font-bold mb-2">
            Privacy and Security
          </Typography>
          <Divider className="bg-border/50 mb-4" />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <FormControlLabel
              control={
                <Switch
                  checked={settings.privacy.locationAccess}
                  onChange={(e) =>
                    updateGroupSetting(
                      "privacy",
                      "locationAccess",
                      e.target.checked
                    )
                  }
                />
              }
              label="Allow location access"
            />
            <FormControlLabel
              control={
                <Switch
                  checked={settings.privacy.shareUsage}
                  onChange={(e) =>
                    updateGroupSetting("privacy", "shareUsage", e.target.checked)
                  }
                />
              }
              label="Share anonymous usage data"
            />
            <FormControlLabel
              control={
                <Switch
                  checked={settings.privacy.lockOnIdle}
                  onChange={(e) =>
                    updateGroupSetting("privacy", "lockOnIdle", e.target.checked)
                  }
                />
              }
              label="Auto-lock when idle"
            />
          </div>
        </section>

        <section className="rounded-md border border-border/50 bg-card p-5">
          <Typography variant="h6" className="text-card-foreground font-bold mb-2">
            Personalization
          </Typography>
          <Divider className="bg-border/50 mb-4" />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <FormControlLabel
              control={
                <Switch
                  checked={settings.personalization.smartReplies}
                  onChange={(e) =>
                    updateGroupSetting(
                      "personalization",
                      "smartReplies",
                      e.target.checked
                    )
                  }
                />
              }
              label="Smart replies"
            />
            <FormControlLabel
              control={
                <Switch
                  checked={settings.personalization.autoOutfit}
                  onChange={(e) =>
                    updateGroupSetting(
                      "personalization",
                      "autoOutfit",
                      e.target.checked
                    )
                  }
                />
              }
              label="Auto outfit suggestions"
            />
            <FormControlLabel
              control={
                <Switch
                  checked={settings.personalization.calendarSync}
                  onChange={(e) =>
                    updateGroupSetting(
                      "personalization",
                      "calendarSync",
                      e.target.checked
                    )
                  }
                />
              }
              label="Sync calendar data"
            />
          </div>
        </section>

        <section className="rounded-md border border-border/50 bg-card p-5">
          <Typography variant="h6" className="text-card-foreground font-bold mb-2">
            Data and Storage
          </Typography>
          <Divider className="bg-border/50 mb-4" />
          <div className="flex flex-wrap gap-2">
            <Button variant="outlined" color="inherit" onClick={handleClearLocalData}>
              Clear local data
            </Button>
            <Button
              variant="outlined"
              color="inherit"
              onClick={() => toast("Export coming soon")}
            >
              Export my data
            </Button>
          </div>
        </section>

        <section className="rounded-md border border-border/50 bg-card p-5">
          <Typography variant="h6" className="text-card-foreground font-bold mb-2">
            About
          </Typography>
          <Divider className="bg-border/50 mb-4" />
          <div className="flex flex-col gap-1 text-muted-foreground">
            <div>App version: 0.0.0</div>
            <div>Build: local</div>
            <div>
              Need help?{" "}
              <Link className="text-primary" to="/home">
                Contact support
              </Link>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}

export default Settings;
