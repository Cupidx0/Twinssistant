// Import the functions you need from the SDKs you need
import { initializeApp } from "firebase/app";
import { getAnalytics } from "firebase/analytics";
import { getAuth } from "firebase/auth";
import { getFirestore } from "firebase/firestore";
import { getStorage } from "firebase/storage";
// TODO: Add SDKs for Firebase products that you want to use
// https://firebase.google.com/docs/web/setup#available-libraries

// Your web app's Firebase configuration
// For Firebase JS SDK v7.20.0 and later, measurementId is optional
const firebaseConfig = {
  apiKey: "AIzaSyAi3eES3_yX7ZOLfHJMO6UQKM9rdrRXPmw",
  authDomain: "job-app-5f841.firebaseapp.com",
  projectId: "job-app-5f841",
  storageBucket: "job-app-5f841.firebasestorage.app",
  messagingSenderId: "824131474376",
  appId: "1:824131474376:web:81cc71f360657266e3a6fd",
  measurementId: "G-4V0ZB3D9ND"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
export const analytics = getAnalytics(app);
export const auth = getAuth(app);
export const db = getFirestore(app);
export const store = getStorage(app);