import React from "react";
import '../index.css'; // Ensure styles are applied
import { Link } from "react-router-dom";
function Header () {
  return (
    <header className="w-screen border-b border-sidebar-border bg-sidebar-background p-4 text-sidebar-foreground">
      <h1 className="text-2xl font-bold"><Link to="/" className="text-gradient-primary">My AI Assistant</Link></h1>
    </header>
  );
}
export default Header;
