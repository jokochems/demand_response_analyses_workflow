import socket
import threading
from contextlib import closing

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from .micro_model import micro_model_api, ModelResponse, Inputs

HOST = "127.0.0.1"
END_POINT = "/load_shift"

app = FastAPI()


@app.get("/", response_class=HTMLResponse)
async def root():
    return """<html><body>Welcome to the AMIRIS Load shifting API!<br>
    Please check the <a href="/docs">documentation</a></body></html>"""


@app.post(END_POINT)
async def call_micro_model(inputs: Inputs) -> ModelResponse:
    return micro_model_api(inputs)


def start_server(port: int):
    """Start web server"""
    uvicorn.run(app, host=HOST, port=port, log_level="info")


def find_free_port() -> int:
    """Check for a free port and return it"""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


class LoadShiftingApiThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.runnable = start_server
        self.daemon = True
        self.port = find_free_port()

    def run(self) -> None:
        self.runnable(self.port)

    def get_url(self):
        return f"http://{HOST}:{self.port}{END_POINT}/"


if __name__ == "__main__":
    start_server(port=find_free_port())
