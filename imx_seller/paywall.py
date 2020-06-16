import random
import requests
import datetime
from flask import Flask, jsonify, request

app = Flask(__name__)

SESSION_CONNECTION_ID = None

# Token that needs to be payed with
# FIXME We will need to change that Token Adress for our demo
token = "0x3ed0DaEDC3217615bde34FEDd023bC81ae49251B"
# Address of imx6 that should receive the payments
# FIXME We will need to change the imx6_address for our demo
buyer_address = "0xbD4B4C7155F55F6051A732772589C38480E58F71"
my_address = "0x5358D52F4a4728d34676454Bdbafd129f0095831"
# The URL of our Agent
agent_url = "http://seller_agent:5020"
raiden_url = "http://raiden:5001"

# A list of possible identifiers
possible_identifiers = list(range(1, 1000))
# Storing the pending identifiers
pending_identifiers = dict()
# Counts the remaining credit for time based payments
time_deposits = dict()
# Counts the remaining credit for pay-per-use based payments
ppu_deposits = dict()


def get_sensor_data():
    # FIXME This subprocess should be used instead of random data
    # p = subprocess.run([
    #    "/home/ubuntu/se050_mw_v02.10.01/simw-top_build/imx_native_se050_t1oi2c/bin/light_sensor"
    # ],
    #    stdout=subprocess.PIPE)#

    # sen_out = int(p.stdout)
    sen_out = random.randint(-10, 35)
    return sen_out


@app.route("/webhooks/<path:dummy>", methods=["GET", "POST"])
def handle_webhook(dummy):
    content = request.get_json()
    print(f"Dummy URL was {dummy}")
    print(f"Received content from aries: \n {content}")
    # If we get an connection request accept it
    if content["state"] == "request":
        complete_connection(content)
        return jsonify({'status': 'success'}), 200
    else:
        return jsonify({'status': 'success'}), 200


@app.route("/connect", methods=["GET"])
def send_invitation():
    create_invitation = requests.post(f"{agent_url}/connections/create-invitation").json()
    return {"invitation": create_invitation["invitation"]}


@app.route("/sensor", methods=["POST"])
# Generating and storing payment data
def request_data():
    content = request.get_json()

    # Make sure that the requester submits a valid "plan"
    try:
        if content["plan"] not in ("time", "ppu"):
            return "No valid Plan submitted", 400
    except TypeError:
        return "Please submit a desired plan {'plan': 'ppu/time'}", 400

    return payment_data(content)


def complete_connection(content):
    # Complete Connection with other peer
    SESSION_CONNECTION_ID = content['connection_id']
    connection = requests.post(
        f"{agent_url}/connections/{SESSION_CONNECTION_ID}/accept-request"
    )


def payment_data(content):
    # Pick an identifier that is used to match a transaction to a sender
    identifier = random.choice(possible_identifiers)
    # Remove used identifier to avoid reusing it
    possible_identifiers.remove(identifier)

    # There are two plans available: 1) Paying for a certain time, 2) Paying per use

    if content["plan"] == "time":
        # Add identifier to a list that tracks pending requests
        pending_identifiers[identifier] = "time"
        unit = "seconds"
        price = "1"

    if content["plan"] == "ppu":
        # Add identifier to a list that tracks pending requests
        pending_identifiers[identifier] = "ppu"
        unit = "request"
        price = "1"

    response = {
        # What unit are you paying for? - Can be seconds or usages
        "unit": unit,
        # The price per unit
        "price_per_unit": price,
        # The token address we want to get payed in
        "token": token,
        # The payment identifier the requester needs to use
        "identifier": identifier,
        # Our Address
        "recipient_address": buyer_address,
    }
    return jsonify(response)


@app.route("/sensor/<int:identifier>")
def is_payed(identifier):
    # Check processing of payment
    process_payment(identifier)

    # Check if credits are remaining
    if credits_available(identifier):
        light_data = get_sensor_data()  # random.randint(-10, 35) #Replace with c call
        return jsonify({"lux": light_data, "message": "Amount of light in Lux"})

    # 0.0.0.0:5000/sensor needs to be called first to request payment information
    else:
        if identifier not in possible_identifiers:
            return "You used up all your credit. Please request new payment credentials", 402
        else:
            return "Please request payment credentials by calling 0.0.0.0:5000/sensor", 402


def process_payment(identifier):
    if identifier in pending_identifiers.keys():
        # Check if we received the payment
        endpoint = f"http://{raiden_url}/api/v1/payments/{token}"
        req = requests.get(endpoint).json()

        for payment in req:
            # Find the right payment Event
            if int(identifier) == int(payment["identifier"]):
                # Find out how much was payed
                amount = int(payment["amount"])
                if pending_identifiers[identifier] == "time":
                    now = datetime.datetime.now()
                    time_deposits[identifier] = now + datetime.timedelta(seconds=amount)

                if pending_identifiers[identifier] == "ppu":
                    ppu_deposits[identifier] = amount

                del pending_identifiers[identifier]


def credits_available(identifier):
    # Make sure that the requester still has credit for accessing the data
    if identifier in time_deposits.keys():
        # If the requester payed until a later point in time grant access
        if time_deposits[identifier] > datetime.datetime.now():
            return True
        else:
            return False

    if identifier in ppu_deposits.keys():
        remaining_usages = ppu_deposits[identifier]
        # If the requester has usages remaining update the credits and grant access
        if remaining_usages > 0:
            ppu_deposits[identifier] = remaining_usages - 1
            return True
        else:
            return False

    else:
        return False


# Run the app
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
