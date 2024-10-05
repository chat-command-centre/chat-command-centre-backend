from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from .llm_integration import process_user_input

app = FastAPI()


@app.post("/chat")
async def chat(request: Request):
    data = await request.json()
    user_input = data.get("message")
    response = await process_user_input(user_input)
    return JSONResponse({"response": response})
