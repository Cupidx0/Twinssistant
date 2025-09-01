import React from "react";

function Footer() {
    const currentYear = new Date().getFullYear(); // Get the current year
  return (
    <footer className="bg-black text-white p-4 w-screen text-center mt-4">
      <p> My AI Assistant. All rights reserved. {currentYear}</p>
    </footer>
  );
}

export default Footer;
