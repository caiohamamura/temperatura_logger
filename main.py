import os
from datetime import datetime, timezone
from typing import List, Dict, Deque
from collections import defaultdict, deque
import json
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import paho.mqtt.client as mqtt


load_dotenv()

hivemq_user = os.getenv('HIVEMQ_USER')
hivemq_pass = os.getenv('HIVEMQ_PASSWORD')


def on_connect(client, userdata, flags, reason_code, properties):
    print(f"Connected with result code {reason_code}")
    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe("/chbr_topic")

def on_message(client, userdata, msg):
    '''
    The callback for when the client receives a CONNACK response from the server.
    '''
    now = datetime.now(timezone.utc)

    msg_dict = json.loads(msg.payload)
    for endereco, temperatura in msg_dict.items():
        if len(storage[endereco]) > 2:
            penultima_temp = storage[endereco][-2][1]
            ultima_temp = storage[endereco][-1][1]
            if temperatura == penultima_temp and temperatura == ultima_temp:
                storage[endereco][-1] = (now, temperatura)
            else:
                storage[endereco].append((now, temperatura))
        else:
            storage[endereco].append((now, temperatura))
        if len(storage[endereco]) > 1000:
            storage[endereco].popleft()


mqttc = mqtt.Client(client_id="", userdata=None, protocol=mqtt.MQTTv5)
mqttc.tls_set(tls_version=mqtt.ssl.PROTOCOL_TLS)

app = FastAPI()
mqttc.on_message = on_message
mqttc.on_connect = on_connect

mqttc.username_pw_set(hivemq_user, hivemq_pass)
mqttc.connect("74101a5cd6e04a08a2d360bb58565bea.s1.eu.hivemq.cloud", 8883, 60)


# --- Enable CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # Allow all origins, restrict if needed
    allow_credentials=True,
    allow_methods=["*"],       # Allow all HTTP methods
    allow_headers=["*"],       # Allow all headers
)

templates = Jinja2Templates(directory="frontend")


storage: Dict[str, Deque] = defaultdict(deque)

# enderecos = {
#     "sensor_1": "Sensor baixo",
#     "sensor_2": "Sensor cima"
# }


class Base(BaseModel):
    endereco: str
    temperatura: float

@app.post('/log')
async def log_post(data: List[Base]):
    now = datetime.now(timezone.utc)

    for ii in data:
        endereco = ii.endereco
        temperatura = ii.temperatura # ok
        if len(storage[endereco]) > 2:
            penultima_temp = storage[endereco][-2][1]
            ultima_temp = storage[endereco][-1][1]
            if temperatura == penultima_temp and temperatura == ultima_temp:
                storage[endereco][-1] = (now, temperatura)
            else:
                storage[endereco].append((now, temperatura))
        else:
            storage[endereco].append((now, temperatura))
        if len(storage[endereco]) > 1000:
            storage[endereco].popleft()
        # await fast_mqtt.publish("/mqtt", {
        #     "endereco": endereco, 
        #     "temperatura": temperatura, 
        #     "data": now.isoformat()
        # })
        
    return {"status": "ok", "endereco": endereco, "temperatura": temperatura, "time": now.isoformat()}


@app.get("/dados")
def dados():
    return [{"endereco": e, "temperatura": [temp for t, temp in vals], "data": [t.isoformat() for t, temp in vals]} for e, vals in storage.items()]


@app.get('/', response_class=HTMLResponse)
def index(req: Request):
    return templates.TemplateResponse(
        request=req, 
        name="index.html",
        context={
            "hivemq_user": hivemq_user, 
            "hivemq_pass": hivemq_pass
    })

mqttc.loop_start()