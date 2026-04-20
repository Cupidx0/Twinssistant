import React from "react";

function Footer() {
    const currentYear = new Date().getFullYear(); // Get the current year
  return (
    <footer className="mt-4 h-[fit-content] w-screen border-t border-border bg-sidebar-background p-4 text-center text-sidebar-foreground">
      <p> My AI Assistant. All rights reserved. {currentYear}</p>
    </footer>
  );
}

export default Footer;
