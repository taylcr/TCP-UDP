import socket
import os
import sys

# Default values and global variables
DEFAULT_IP = socket.gethostbyname(socket.gethostname())
DEFAULT_PORT = 1999
DEFAULT_DEBUG = False
IP = DEFAULT_IP
PORT = DEFAULT_PORT
DEBUG = DEFAULT_DEBUG

# Directory constants
UPLOAD_FOLDER = "to_upload"
DOWNLOAD_FOLDER_DESTINATION = "downloads"
BUFFER_SIZE = 1024
TIMEOUT = 2  # Timeout in seconds for UDP
FILE_INFO_SIZE = 1 

#-------------------------- UDP ----------------------------------

def udp_send_file(filename):
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.isfile(filepath):
        print(f"Error: The file '{filepath}' does not exist.")
        return

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_socket:
        udp_socket.settimeout(TIMEOUT)
        with open(filepath, 'rb') as f:
            udp_socket.sendto(f"put {os.path.basename(filename)}".encode(), (IP, PORT))
            while True:
                bytes_read = f.read(BUFFER_SIZE)
                if not bytes_read:
                    udp_socket.sendto(b'END', (IP, PORT))
                    break
                udp_socket.sendto(bytes_read, (IP, PORT))
                try:
                    _, _ = udp_socket.recvfrom(BUFFER_SIZE)  # Wait for ACK
                except socket.timeout:
                    print("Timeout, resending packet")
                    if f.tell() > BUFFER_SIZE:
                        f.seek(-BUFFER_SIZE, os.SEEK_CUR)  # Only move back if not at the start of the file
                    else:
                        print("Cannot resend - at the beginning of the file.")
                        break

def udp_receive_file(filename):
    download_path = os.path.join(DOWNLOAD_FOLDER_DESTINATION, filename)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_socket:
        udp_socket.settimeout(TIMEOUT)
        udp_socket.sendto(f"get {filename}".encode(), (IP, PORT))
        with open(download_path, 'wb') as f:
            while True:
                try:
                    bytes_read, _ = udp_socket.recvfrom(BUFFER_SIZE)
                    if bytes_read == b'END':
                        break
                    f.write(bytes_read)
                    udp_socket.sendto(b'ACK', (IP, PORT))
                except socket.timeout:
                    print("Failed to receive file.")
                    break


#-------------------------- UDP ----------------------------------
def get_user_protocol_choice():
    print("Choose the protocol for sending the file:")
    print("1: TCP")
    print("2: UDP")
    return input("Enter your choice (1 or 2): ")

def tcp_send_file(client, filename):
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    try:
        filesize = os.path.getsize(filepath)
        opcode = '000'
        filename_length = f'{len(filename):05b}'

        send_data = opcode + filename_length
        client.send(bytes([int(send_data, 2)]))
        client.send(filename.encode("utf-8"))
        client.send(filesize.to_bytes(4, 'big'))

        with open(filepath, "rb") as f:
            send_chunk(client, f, filesize)

        return client.recv(FILE_INFO_SIZE)
    except FileNotFoundError:
        print(f"File {filename} not found in {UPLOAD_FOLDER}.")
        return None

def get_file_response(client, filename):
    opcode = '001'
    filename_length = f'{len(filename):05b}'
    send_data = opcode + filename_length
    client.send(bytes([int(send_data, 2)]))
    client.send(filename.encode("utf-8"))
    return client.recv(FILE_INFO_SIZE)

def get_file(client, filename, filesize):
    filepath = os.path.join(DOWNLOAD_FOLDER_DESTINATION, filename)
    print(f"Starting to receive file: {filename} of size: {filesize} bytes.")
    with open(filepath, "wb") as f:
        receive_chunk(client, f, filesize)
    print(f"{filename} has been downloaded successfully to {filepath}")

def change_file_name(client, oldfilename, newfilename):
    opcode = '010'
    oldfilename_length = f'{len(oldfilename):05b}'
    newfilename_length = f'{len(newfilename):08b}'

    send_data = opcode + oldfilename_length
    client.send(bytes([int(send_data, 2)]))
    client.send(oldfilename.encode("utf-8"))
    client.send(bytes([int(newfilename_length, 2)]))
    client.send(newfilename.encode("utf-8"))

    return client.recv(FILE_INFO_SIZE)
def summary_file(client, filename):
    opcode = '011'  # Correct opcode for summary
    filename_length = f'{len(filename):05b}'
    send_data = opcode + filename_length

    client.send(bytes([int(send_data, 2)]))
    client.send(filename.encode("utf-8"))

    # Receive the response
    response = client.recv(FILE_INFO_SIZE)
    return response

def handle_summary_response(client, response):
    byteInfo = int.from_bytes(response, 'big')
    rescode = byteInfo >> 5

    if rescode == 0:  # Success response
        print("Summary operation completed successfully!")
        summary_length = byteInfo & 0b00011111
        summary = client.recv(summary_length).decode('utf-8')
        print("Summary of the file is as follows:")
        print(summary)
    elif rescode == 2:  # File not found
        print("Error: File not found")
    elif rescode == 3:  # Unknown request
        print("Error: Unknown request")
    else:
        print("Error occurred during summary operation")



def get_help(client):
    opcode = '110'  # Correct opcode for help (110 instead of 100)
    padding = '00000'

    send_data = opcode + padding
    client.send(bytes([int(send_data, 2)]))
    return client.recv(FILE_INFO_SIZE)

def unsupported_cmd(client):
    opcode = '100'  # Correct opcode for unsupported command
    padding = '00000'

    send_data = opcode + padding
    client.send(bytes([int(send_data, 2)]))
    return client.recv(FILE_INFO_SIZE)


def do_command(command, addr):
    vals = command.split(" ")
    cmd = vals[0]

    # Handle TCP commands
    if cmd in ["summary", "change", "help"]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
            client.connect(addr)

            if cmd == "summary" and len(vals) > 1:
                response = summary_file(client, vals[1])
                handle_summary_response(client, response)
            elif cmd == "change" and len(vals) > 2:
                response = change_file_name(client, vals[1], vals[2])
                print(response)  # Print the response from the server
            elif cmd == "help":
                response = get_help(client)
                print(response)  # Print the response from the server
            # Add additional TCP command handling here as needed

    # Handle File Transfer Commands (put/get) with TCP or UDP choice
    elif cmd in ["put", "get"] and len(vals) > 1:
        filename = vals[1]
        protocol = get_user_protocol_choice()

        if protocol == "1":  # TCP
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
                client.connect(addr)
                if cmd == "put":
                    tcp_send_file(client, filename)  # TCP file send
                elif cmd == "get":
                    response = get_file_response(client, filename)
                    # Further TCP file get logic
        elif protocol == "2":  # UDP
            if cmd == "put":
                udp_send_file(filename)  # UDP file send
            elif cmd == "get":
                udp_receive_file(filename)  # UDP file receive
        else:
            print("Invalid choice.")
    else:
        print("Invalid command or incorrect usage.")


    vals = command.split(" ")
    cmd = vals[0]

    # TCP commands that require a socket connection
    tcp_commands = ["summary", "change", "help", "put", "get"]

    # Create the TCP client socket for TCP-specific commands
    client = None
    if cmd in tcp_commands:
        client = socket.socket()
        client.connect(addr)

    try:
        if cmd == "summary" and len(vals) > 1:
            response = summary_file(client, vals[1])
            handle_summary_response(client, response)
        elif cmd == "put" and len(vals) > 1:
            protocol = get_user_protocol_choice()
            if protocol == "1":
                tcp_send_file(client, vals[1])  # TCP file send
            elif protocol == "2":
                udp_send_file(vals[1])  # UDP file send
        elif cmd == "get" and len(vals) > 1:
            protocol = get_user_protocol_choice()
            if protocol == "1":
                tcp_get_file(client, vals[1])  # TCP file get
            elif protocol == "2":
                udp_get_file(vals[1])  # UDP file get
        elif cmd == "change" and len(vals) > 2:
            response = change_file_name(client, vals[1], vals[2])
            print(response)  # Print the response from the server
        elif cmd == "help":
            response = get_help(client)
            print(response)  # Print the response from the server
        else:
            print("Invalid command or incorrect usage.")
    except Exception as e:
        print(f"Error during command execution: {e}")
    finally:
        # Close the TCP client socket if it was created
        if client:
            client.close()


    vals = command.split(" ")
    cmd = vals[0]
      #--------UDP-------------------
    if cmd == "put" and len(vals) > 1:
        filename = vals[1]
        protocol = get_user_protocol_choice()
        if protocol == "1":
            tcp_send_file(addr, filename)  # Function to send file via TCP
        elif protocol == "2":
            udp_send_file(filename)  # Function to send file via UDP
        else:
            print("Invalid choice.")

        client = socket.socket()
        print(f"Connecting to server at {addr}...")
        client.connect(addr)
        print(f"Connected. Executing command: {cmd}")

    response = None
    if cmd == "summary" and len(vals) > 1:
        response = summary_file(client, vals[1])
        handle_summary_response(client, response)
    elif cmd == "put" and len(vals) > 1:
        response = send_file(client, vals[1])
    elif cmd == "get" and len(vals) > 1:
        response = get_file_response(client, vals[1])
    elif cmd == "change" and len(vals) > 2:
        response = change_file_name(client, vals[1], vals[2])
    elif cmd == "help":
        response = get_help(client)
    else:
        response = unsupported_cmd(client)

    if response:
        work_with_response(client, response)
    client.close()

def work_with_response(client, response):
    byteInfo = int.from_bytes(response, 'big')
    rescode = byteInfo >> 5

    if rescode == 0:  # Success response for either put, get, change, or summary
        print("Operation completed successfully!")
        # Additional handling if this success response is for a summary operation
        if byteInfo & 0b00011111 > 0:  # Check if there is additional data for summary
            handle_summary_response(client, response)

    elif rescode == 1:  # File received
        print("Server indicates file is ready for download.")
        filenameSize = byteInfo & 0b00011111
        receivedFileName = client.recv(filenameSize).decode('utf-8')
        print(f"Receiving file: {receivedFileName}")
        receivedFileSize = int.from_bytes(client.recv(4), 'big')
        get_file(client, receivedFileName, receivedFileSize)

    elif rescode == 2:
        print("Error: File not found")

    elif rescode == 3:
        print("Error: Unknown request")

    elif rescode == 4:
        print("Error: Unsuccessful operation")

    elif rescode == 5:
        print("Error: Summary operation failed")

    elif rescode == 6:
        helpLength = byteInfo & 0b00011111
        helpMessage = client.recv(helpLength).decode('utf-8')
        print(helpMessage)

def send_chunk(client, file, total_size):
    bytes_sent = 0
    while bytes_sent < total_size:
        chunk = file.read(min(total_size - bytes_sent, 2048))
        client.send(chunk)
        bytes_sent += len(chunk)

def receive_chunk(client, file, total_size):
    bytes_recd = 0
    while bytes_recd < total_size:
        chunk = client.recv(min(total_size - bytes_recd, 2048))
        file.write(chunk)
        bytes_recd += len(chunk)

def display_welcome_message():
    print("Welcome to the FTP Client")
    print("Type 'help' to see the list of commands or 'exit' to quit")

def display_help():
    commands = {
        "put <filename>": "Upload a file to the server.",
        "get <filename>": "Download a file from the server.",
        "change <oldfilename> <newfilename>": "Rename a file on the server.",
        "summary <filename>": "Get statistical summary (max, min, avg) of a file.",
        "help": "Display this help message.",
        "exit": "Exit the application."
    }
    for cmd, desc in commands.items():
        print(f"{cmd}: {desc}")

def set_global_vars_from_args(args):
    global IP, PORT, DEBUG
    if len(args) > 1:
        IP = args[1]
    if len(args) > 2:
        PORT = int(args[2])
    if len(args) > 3:
        DEBUG = bool(int(args[3]))

def main():
    set_global_vars_from_args(sys.argv)
    if DEBUG:
        print(f"Debug mode is on. Connecting to {IP}:{PORT}")

    addr = (IP, PORT)
    display_welcome_message()

    while True:
        userInput = input("myftp> ").strip()
        if userInput.lower() == "exit":
            break
        else:
            do_command(userInput, (IP, PORT))

    
    print("Exiting client")

# Main Execution
if __name__ == "__main__":
    main()
