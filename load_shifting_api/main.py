import threading

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from .micro_model import micro_model_api, ModelResponse, Inputs

app = FastAPI()


@app.get("/", response_class=HTMLResponse)
async def root():
    return """<html><body>Welcome to the AMIRIS Load shifting API!<br>
    Please check the <a href="/docs">documentation</a></body></html>"""


@app.post("/load_shift")
async def call_micro_model(inputs: Inputs) -> ModelResponse:
    return micro_model_api(inputs)


def start_server():
    """Start web server"""
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")


class LoadShiftingApiThread(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)
        self.runnable = start_server
        self.daemon = True

    def run(self) -> None:
        self.runnable()


if __name__ == "__main__":
    start_server()
