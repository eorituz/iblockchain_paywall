# Adding upper direcotry to PYTHONPATH
import sys

sys.path.append("..")
from raidennode import RaidenNode
from time import sleep
import subprocess
import requests
import structlog
import logging
import click
import sys
from flask import Flask, jsonify, request

app = Flask(__name__)

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M.%S"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)
logging.basicConfig(
    format="%(message)s", level=logging.DEBUG
)

# Initialize logger
log = structlog.get_logger(__name__)
# Header for all requests
header = {'Content-Type': 'application/json', }
# FIXME the IP address of the paywall URL will change for our demo
sensor_url = "http://localhost:5000/sensor"
# FIXME the raiden_payment_endpoint will need to change for our dem (most likely to port 5001)
raiden_port = "5002"
raiden_payment_endpoint = f'http://localhost:{raiden_port}/api/v1/payments'
# The URL of our Agent
agent_url = "http://localhost:5010/"
# The payers ethereum address
my_address = "0xbD4B4C7155F55F6051A732772589C38480E58F71"
token = "0x3ed0DaEDC3217615bde34FEDd023bC81ae49251B"

SESSION_CONNECTION_ID = None


@app.route("/webhooks/<path:dummy>", methods=["GET", "POST"])
def handle_webhook(dummy):
    print(f"Dummy URL was {dummy}")
    content = request.get_json()
    print(f"Conten was {content}")
    return jsonify({'status': 'success'}), 200


@click.command()
@click.option('--plan', default='ppu', help='Can be "ppu" (pay-per-use) or "time"')
@click.option('--duration',
              default=1,
              help='Duration that should be payed for. '
                   'Dimension is either seconds or number of uses'
              )
@click.option('--update',
              default=1.0,
              help='The interval in which the motor updates its position'
              )
@click.option('--interactive/--noninteracitve',
              default=False,
              help='If set, the motor only updates after user input'
              )
def run(plan, duration, update, interactive):
    if plan != 'ppu' or plan != 'time':
        print(plan, isinstance(plan, str))
        raise click.BadParameter('Please use "--plan ppu" or "--plan time".')

    invitation = request_connection()

    connection_id = establish_connection(invitation)

    if plan == 'ppu':
        scenario_pay_per_use(duration, update, interactive, connection_id)

    if plan == 'time':
        scenario_pay_per_time(duration, update, interactive, connection_id)


# Requestion a connection to seller
def request_connection():
    req = requests.get(sensor_url)
    # FIXME not sure if this returns the right thing
    return req.json()["invitation"]


def establish_connection(invitation):
    # TODO here we need to establish the connection with the buyer on our side
    # Receive the invitation and store it in our wallet
    receive_invitaion = requests.post(f"{agent_url}connections/receive-invitation",
                                      json=invitation).json()
    SESSION_CONNECTION_ID = receive_invitaion['connection_id']
    # Accept invitation
    accept_invitaion = requests.post(
        f"{agent_url}connections/{SESSION_CONNECTION_ID}/accept-invitation"
    )

    return accept_invitaion["connection_id"]


def scenario_pay_per_time(duration, update, interactive):
    price, token, receiver, identifier = get_payment_credentials({"plan": "time"})
    # We want to pay for 30 seconds
    payment_value = int(price) * duration
    send_raiden_payment(payment_value, token, receiver, identifier)
    # Accessing the data until we're out of credit
    while True:
        if interactive:
            if not click.confirm('Query light sensor data'):
                continue
        else:
            sleep(update)
        lux_value = request_sensor_data(identifier)
        adjust_motor(lux_value)
        log.info("---------------------------")


def scenario_pay_per_use(duration, update, interactive, connection_id):
    price, token, receiver, identifier = get_payment_credentials({"plan": "ppu"})
    # We want to pay for 16 usages
    payment_value = int(price) * duration
    send_raiden_payment(payment_value, token, receiver, identifier)
    # Accessing the data until we're out of credit
    while True:
        if interactive:
            if not click.confirm('Query light sensor data'):
                continue
        else:
            sleep(update)
        lux_value = request_sensor_data(identifier)
        adjust_motor(lux_value)
        log.info("---------------------------")


def get_payment_credentials(json_dict):
    log.info("Requesting payment credentials from data seller")
    req = requests.post(sensor_url, headers=header, json=json_dict).json()
    price = req["price_per_unit"]
    token = req["token"]
    receiver = req["recipient_address"]
    identifier = req["identifier"]
    log.debug(f"The data seller told us that the price per unit will be: {price}.")
    log.debug(f"We should use the token: {token}")
    log.debug(f"Tha data sellers Address is {receiver}")
    log.debug(f"The transaction should use the identifier {identifier}")
    return price, token, receiver, identifier


def send_raiden_payment(payment_value, token, receiver, identifier):
    log.info("Sending payment instructions to our Raiden client.")
    req = requests.post(
        f"{raiden_payment_endpoint}/{token}/{receiver}",
        headers=header,
        json={'amount': payment_value,
              'identifier': identifier,
              }
    )

    # TODO we should add a test here if the request returned successful later

    log.debug(f"Status code is: {req.status_code}")
    log.debug(f"Request message is: {req.text}")

    # FIXME the sleep amount might need to be changed,
    # depending on how fast the data seller imx6 writes the successful transfer to its DB
    log.debug("Sleeping 1s to make sure the imx6 processed the payment")
    sleep(5)


def request_sensor_data(identifier):
    log.debug("Requesting Light sensor data")
    req = requests.get(f"{sensor_url}/{identifier}")
    if req.status_code == 402:
        log.debug(f"Status code is: {req.status_code}")
        log.debug(f"Request message is: {req.text}")
        log.error("Access to light data denied. "
                  "We either used up all our credit or the payment didn't succeed")
        sys.exit("We're out of credit. - Shutting down")
    else:
        req = req.json()
    log.debug(f"Received Light sensor data - The current lux value is {req['lux']}")
    return req['lux']


def adjust_motor(lux):
    log.info(f"Lux received: {lux}")
    # Translate value in lux range to motor range
    motor_position = int(((lux - 0) / (1000 - 0)) * (500 - 100) + 100)
    # Set motor to translated range
    log.info(f"Setting motor position to {motor_position}")
    set_motor_position(motor_position)


def set_motor_position(position):
    # This function sets the motor position
    subprocess.run(
        ["/home/ubuntu/se050_mw_v02.10.01/simw-top_build/imx_native_se050_t1oi2c/bin/servo_motor"],
        stdout=subprocess.PIPE,
        input=str(position),
        encoding='ascii')


# Run the app
if __name__ == "__main__":
    raiden = RaidenNode(
        address=my_address,
        token=token,
        api_endpoint=raiden_port,
        keystore="UTC--2020-06-08T13-23-34Z--5911d88e-22ad-848a-664f-7628cfad3a63"
    )
    # raiden.start()
    app.run(host="0.0.0.0", port=5001)
    # run()
