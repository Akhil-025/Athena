export async function askQuestionStreamRaw(url, payload, onChunk) {
  // Try fetch streaming (POST, chunked)
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify(payload)
    });
    if(!res.ok) throw new Error(`HTTP ${res.status}`);
    if(!res.body) throw new Error("No stream body");

    const reader = res.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let finalText = "";
    while(true) {
      const { value, done } = await reader.read();
      if(done) break;
      if(value) {
        const chunk = decoder.decode(value, { stream: true });
        finalText += chunk;
        onChunk(chunk);
      }
    }
    try {
      return JSON.parse(finalText);
    } catch (e) {
      return { text: finalText };
    }
  } catch (e) {
    throw e;
  }
}
export default askQuestionStreamRaw;
