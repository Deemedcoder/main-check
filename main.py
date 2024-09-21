import json
import requests
from pysnmp.hlapi import *
import subprocess
import platform
import time

# API URL
fetch_url = "http://192.168.1.41:81/test-soft/api.php"


def fetch_api_data(url):
    """
    Fetches JSON data from a given API URL.
    """
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Failed to get data. Status code: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error fetching API data: {e}")
        return None


# Ping function
def ping_device(hostname, timeout=1, count=1):
    """
    Pings a device to check its reachability.
    """
    try:
        param = '-n' if platform.system().lower() == 'windows' else '-c'
        timeout_param = '-w' if platform.system().lower() == 'windows' else '-W'
        command = ["ping", param, str(count), timeout_param, str(timeout), hostname]
        output = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return output.returncode == 0
    except Exception as e:
        print(f"Error pinging device: {e}")
        return False


# SNMP GET function
def snmp_get(ip, port, community, *oids):
    try:
        object_types = [ObjectType(ObjectIdentity(oid)) for oid in oids]
        errorIndication, errorStatus, errorIndex, varBinds = next(
            getCmd(SnmpEngine(),
                   CommunityData(community, mpModel=1),
                   UdpTransportTarget((ip, port)),
                   ContextData(),
                   *object_types))

        if errorIndication:
            print(f"Error Indication: {errorIndication}")
            return [None] * len(oids)
        elif errorStatus:
            print(f"Error Status: {errorStatus.prettyPrint()} at {errorIndex}")
            return [None] * len(oids)
        else:
            return [varBind[1].prettyPrint() for varBind in varBinds]
    except Exception as e:
        print(f"Exception in SNMP GET: {e}")
        return [None] * len(oids)


# Function to process the data and query SNMP
def process_data_and_query_snmp(data_dict):
    result = {}

    if not isinstance(data_dict, dict):
        raise ValueError("Expected 'data_dict' to be a dictionary.")

    for hostname, device_data in data_dict.items():
        if not isinstance(device_data, dict):
            print(f"Expected a dictionary for device data: {device_data}")
            continue

        ip = device_data.get("ip")
        port = device_data.get("port", 161)
        community = device_data.get("community_string")
        oids_str = device_data.get("oids")

        print(f"Processing device: {hostname} ({ip})")

        if not ping_device(ip):
            print(f"Device {hostname} ({ip}) is not reachable. Skipping SNMP check.")
            continue

        print(f"Device {hostname} ({ip}) is reachable. Proceeding with SNMP check.")

        try:
            oids_dict = json.loads(oids_str)
        except json.JSONDecodeError as e:
            print(f"Error decoding OID string: {e}")
            continue

        oids = list(oids_dict.values())
        oids_name = list(oids_dict.keys())

        snmp_values = snmp_get(ip, port, community, *oids)

        device_result = {}
        for oid, value in zip(oids_name, snmp_values):
            device_result[oid] = value

        result[hostname] = device_result

    return result


# Get API endpoint function
def get_api_endpoint(url):
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an error for bad responses
        data = response.json()

        if data.get('is_enabled') == '1':
            return data.get('api_endpoint')
        else:
            return None
    except requests.RequestException as e:
        print(f"An error occurred: {e}")
        return None


# Send data to API function
def send_data_to_api(data, api_endpoint):
    try:
        print("Data type before sending:", type(data))
        response = requests.post(api_endpoint, json=data)  # JSON is passed automatically
        print("Response Code:", response.status_code)

        if response.status_code == 200:
            print("Data sent successfully!")
            print("Server response:", response.text)
        else:
            print("Failed to send data. Status code:", response.status_code)
            print("Response:", response.text)
    except Exception as e:
        print(f"Error sending data to server: {e}")


# Convert data to desired format
def convert_data_format(data):
    detail_parts = []

    for key, value in data.items():
        if isinstance(value, dict):
            joined_values = "_".join(value.values())
            detail_parts.append(f"{key}:{joined_values}")
        else:
            detail_parts.append(f"{key}:{value}")

    detail_string = "||".join(detail_parts)

    return {
        'mac': 1763377233,  # Keeping mac value fixed
        'detail': detail_string
    }


# Main function to continuously run the program
def run_continuously():
    while True:
        try:
            # Fetch data from the API
            data = fetch_api_data(fetch_url)
            if data:
                final_result = process_data_and_query_snmp(data)

                # Convert SNMP result into the desired format
                formatted_data = convert_data_format(final_result)

                # Get the API endpoint from the server
                endpoint_url = "http://192.168.1.41:81/test-soft/getapiendpoint.php"
                api_endpoint = get_api_endpoint(endpoint_url)

                if api_endpoint:
                    # Send the formatted data to the API
                    send_data_to_api(formatted_data, api_endpoint)
                else:
                    print("No API endpoint available or API is not enabled.")

            else:
                print("No data fetched from the API.")
        except Exception as e:
            print(f"An error occurred: {e}")

        # Wait for 60 seconds before running again
        time.sleep(1)


if __name__ == "__main__":
    run_continuously()
