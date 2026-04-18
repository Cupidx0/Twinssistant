import React from "react";
import '../index.css'; // Ensure styles are applied
import { Link } from "react-router-dom";
function Header () {
  return (
    <header className="bg-zinc-950 text-white p-4 w-screen">
      <h1 className="text-2xl font-bold"><Link to="/" className="text-blue-500">My AI Assistant</Link></h1>
    </header>
  );
}
export default Header;
