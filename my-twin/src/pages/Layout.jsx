import React,{useState} from "react";
import { Outlet } from "react-router-dom";
import Header from "./header";
import Footer from "./footer";
import {Toaster} from "react-hot-toast";
function Layout() {
    const [isOpen, setIsOpen] = useState(false);
    return (
        <>
            <Header isOpen={isOpen} setIsOpen={setIsOpen} />
            <main>
            <Toaster
                position="top-right"
                reverseOrder={false}
                toastOptions={{
                    duration:1500,
                    style: {
                        background: '#363636',
                        color: '#fff',
                    },
                }}
            />
            <Outlet />
            </main>
            <Footer />
        </>
    );
}
export default Layout;
