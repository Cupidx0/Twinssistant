export const fetchAssistantResponse = async (question) => {
    try{
        const response = await fetch('http://127.0.0.1:5000/chat',{
            method:'POST',
            headers:{"Content-Type":"application/json"},
            body:JSON.stringify({question}),
        });
        if(!response.ok){
            const errorData = await response.json().catch(() => ({}));
            throw new Error(`HTTP error! status: ${response.status}, message: ${errorData.error||'Unknown error'}`);
        }
        const data = await response.json();
        return data.reply;
    }catch(error){
        console.error("Error fetching assistant response:", error);
        throw error;
    }
};