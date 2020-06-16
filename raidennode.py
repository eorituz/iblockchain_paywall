import pathlib
import subprocess
from time import sleep, monotonic
import sys

import requests


class RaidenNode:
    def __init__(self, address: str, token: str, api_endpoint: str, keystore: str):
        self.address = address
        self.api_endpoint = api_endpoint
        self.token = token
        self.keystore = keystore
        self._raiden_process = None

    def start(self):
        index_path = pathlib.Path(__file__).parent.absolute().joinpath(
            "light-client/raiden-cli/build/index.js")
        raiden = f"node {index_path} " + \
                 " --token " + self.token + \
                 " --ethNode " + "http://parity.goerli.ethnodes.brainbot.com:8545" + \
                 " --store " + f"./store_{self.address}" + \
                 " --password " + "raiden" + \
                 " --serve " + self.api_endpoint + \
                 " --privateKey " + f"./raiden_config/{self.keystore}" + " & "
        print("Starting Raiden")
        with open('./raiden.log', 'w') as logfile:
            self._raiden_process = subprocess.Popen(
                raiden,
                shell=True,
                stdout=logfile,
                stderr=logfile
            )

        # Wait up to 2 mins for raiden to get started
        start_time = monotonic()
        while monotonic() <= start_time + 120:
            sleep(1)
            try:
                resp = requests.get(f"http://localhost:{self.api_endpoint}/api/v1/channels")
            except:
                continue
            if resp.status_code == 200:
                print("Raiden successfully started")
                break
            else:
                self.stop()
                sys.exit("Raiden couldn't be started, check log files")

    def stop(self):
        print("Stopping Raiden")
        self._raiden_process.terminate()
