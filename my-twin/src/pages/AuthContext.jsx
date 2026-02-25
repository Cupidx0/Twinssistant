import { createContext, useContext, useEffect, useState } from 'react';
import { onAuthStateChanged } from 'firebase/auth';
import { auth } from '../Utils/Firebase'; // adjust if your firebase config is elsewhere

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [user, setUser] = useState(null);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (firebaseUser) => {
      setIsLoggedIn(!!firebaseUser);
      setUser(firebaseUser);
    });

    return () => unsubscribe();
  }, []);

  return (
    <AuthContext.Provider value={{ isLoggedIn, user }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
