from time import sleep

import requests
import structlog
import logging

# Logging configuration
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
    format="%(message)s", level=logging.INFO
)

# Initialize logger
log = structlog.get_logger(__name__)
# Header for all requests
header = {'Content-Type': 'application/json', }
# FIXME the IP address of the paywall URL will change for our demo
sensor_url = "http://localhost:5000/sensor"
# FIXME the raiden_payment_endpoint will need to change for our dem (mostlikly to port 5001)
raiden_payment_endpoint = 'http://localhost:5002/api/v1/payments'


def run():
    # Scenario 1
    log.error("Starting Scenario 1 -- Pay for single usage")
    scenario_pay_per_use(1)
    log.error("Successfully ran Scenario 1")
    log.info("---------------------------")

    # Scenario 2
    log.error("Starting Scenario 2 -- Pay for sixteen usages")
    scenario_pay_per_use(16)
    log.error("Successfully ran Scenario 2")
    log.info("---------------------------")
    # Scenario 3
    log.error("Starting Scenario 3 -- Pay for 30 seconds")
    scenario_pay_per_time(30)
    log.error("Successfully ran Scenario 3")
    log.error("END OF DEMO")


def scenario_pay_per_time(time):
    price, token, receiver, identifier = get_payment_credentials({"plan": "time"})
    # We want to pay for 30 seconds
    payment_value = int(price) * time
    send_raiden_payment(payment_value, token, receiver, identifier)
    # Accessing the data
    for i in range(time):
        lux_value = request_sensor_data(identifier)
        adjust_motor(lux_value)
        log.info("---------------------------")
        sleep(1)


def scenario_pay_per_use(amount):
    price, token, receiver, identifier = get_payment_credentials({"plan": "ppu"})
    # We want to pay for 16 usages
    payment_value = int(price) * amount
    send_raiden_payment(payment_value, token, receiver, identifier)
    # Accessing the data
    for i in range(amount):
        lux_value = request_sensor_data(identifier)
        adjust_motor(lux_value)
        log.info("---------------------------")
        sleep(1)


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

    log.debug("Payment succeeded")

    # FIXME the sleep amount might need to be changed,
    # depending on how fast the data seller imx6 writes the successful transfer to its DB
    log.debug("Sleeping 1s to make sure the imx6 processed the payment")
    sleep(1)


def request_sensor_data(identifier):
    log.debug("Requesting Light sensor data")
    req = requests.get(f"{sensor_url}/{identifier}").json()
    log.debug(f"Received Light sensor data - The current lux value is {req['lux']}")
    return req['lux']


def adjust_motor(lux):
    log.info("Adjusting Motor according to Lux value")
    # FIXME @Krishna please add the motor command in here


# Run the app
if __name__ == "__main__":
    run()
