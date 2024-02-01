
import socket
import os
import sys
import threading

# Default values for IP, port, and debug flag
IP = "127.0.0.1"
TCP_PORT = 1999
UDP_PORT = 12346  # Different port for UDP server
DEBUG = True

# Constants for file storage
UPLOAD_FOLDER_DESTINATION = "uploads"
DOWNLOAD_FOLDER_DESTINATION = "downloads"
BUFFER_SIZE = 1024
FILE_INFO_SIZE = 1  # Byte size for file info

# Constants
UPLOAD_FOLDER_DESTINATION = "uploads"
FILE_INFO_SIZE = 1  # Byte size for file info

#-------------------------- UDP ----------------------------------
# Function to receive file via UDP
def udp_receive_file(server_socket, filename, client_addr):
    filepath = os.path.join(UPLOAD_FOLDER_DESTINATION, filename)
    with open(filepath, 'wb') as f:
        while True:
            bytes_read, _ = server_socket.recvfrom(BUFFER_SIZE)
            if bytes_read == b'END':
                break
            f.write(bytes_read)
            server_socket.sendto(b'ACK', client_addr)

# Function to send file via UDP
def udp_send_file(server_socket, filename, client_addr):
    filepath = os.path.join(UPLOAD_FOLDER_DESTINATION, filename)
    if not os.path.isfile(filepath):
        server_socket.sendto(b'File not found', client_addr)
        return

    with open(filepath, 'rb') as f:
        while True:
            bytes_read = f.read(BUFFER_SIZE)
            if not bytes_read:
                server_socket.sendto(b'END', client_addr)
                break
            server_socket.sendto(bytes_read, client_addr)
            _, _ = server_socket.recvfrom(BUFFER_SIZE)  # Wait for ACK


# Function for the UDP server thread
def udp_server():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_socket:
        udp_socket.bind((IP, UDP_PORT))
        print(f"[*] UDP Server is listening on {IP}:{UDP_PORT}")

        while True:
            msg, client_addr = udp_socket.recvfrom(BUFFER_SIZE)
            command, filename = msg.decode().split()
            if command == 'put':
                udp_receive_file(udp_socket, filename, client_addr)
            elif command == 'get':
                udp_send_file(udp_socket, filename, client_addr)





#-------------------------- UDP ----------------------------------

# Function to handle the PUT command
def put_file(client, filename, received_file_size):
    filepath = os.path.join(UPLOAD_FOLDER_DESTINATION, filename)
    with open(filepath, "wb") as f:
        bytes_recd = 0
        while bytes_recd < received_file_size:
            chunk = client.recv(min(received_file_size - bytes_recd, 2048))
            if not chunk:
                raise RuntimeError("Socket connection broken")
            f.write(chunk)
            bytes_recd += len(chunk)
    return '000' + '00000'  # Successful PUT

# Function to handle the GET command
def get_file(client, filename):
    filepath = os.path.join(UPLOAD_FOLDER_DESTINATION, filename)
    if not os.path.exists(filepath):
        return '010' + '00000'  # File not found
    file_size = os.path.getsize(filepath)
    filename_length = len(filename)
    response = '001' + f'{filename_length:05b}'
    client.send(bytes([int(response, 2)]))
    client.send(filename.encode('utf-8'))
    client.send(file_size.to_bytes(4, 'big'))
    with open(filepath, 'rb') as f:
        while True:
            chunk = f.read(2048)
            if not chunk:
                break
            client.send(chunk)
    return '001' + '00000'  # Successful GET

# Function to handle the CHANGE command
def change_name(client, old_filename, new_filename):
    old_filepath = os.path.join(UPLOAD_FOLDER_DESTINATION, old_filename)
    new_filepath = os.path.join(UPLOAD_FOLDER_DESTINATION, new_filename)
    if not os.path.exists(old_filepath):
        return '010' + '00000'  # File not found
    os.rename(old_filepath, new_filepath)
    return '000' + '00000'  # Successful CHANGE

# Function to handle the HELP command
def help_command():
    commands = "Available commands: PUT, GET, CHANGE, SUMMARY, HELP"
    return '110' + f'{len(commands):05b}', commands

# Function to handle the SUMMARY command
def handle_summary(client, filename):
    filepath = os.path.join(UPLOAD_FOLDER_DESTINATION, filename)
    if not os.path.exists(filepath):
        return '011' + '00000'  # File not found
    try:
        with open(filepath, 'r') as f:
            numbers = [float(line.strip()) for line in f if line.strip()]
        maximum = max(numbers)
        minimum = min(numbers)
        average = sum(numbers) / len(numbers)
        summary_data = f"Max: {maximum}, Min: {minimum}, Avg: {average}\n"
        summary_length = len(summary_data)
        response = '010' + f'{summary_length:05b}'
        client.send(bytes([int(response, 2)]))
        client.send(summary_data.encode('utf-8'))
    except Exception as e:
        if DEBUG:
            print(f"Error while summarizing file: {e}")
        return '011' + '00000'  # Error during summary operation
    return '010' + '00000'  # Successful SUMMARY

# Main server function
def start_server():
    os.makedirs(UPLOAD_FOLDER_DESTINATION, exist_ok=True)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((IP, TCP_PORT))  # Use TCP_PORT here instead of PORT
        s.listen(2)
        if DEBUG:
            print(f"[*] Server is listening on {IP}:{TCP_PORT}")  # Use TCP_PORT here
        while True:
            client_socket, address = s.accept()
            if DEBUG:
                print(f"[+] Connection established with {address}")
            try:
                received_info = client_socket.recv(FILE_INFO_SIZE)
                byte_info = int.from_bytes(received_info, 'big')
                opcode = byte_info >> 5
                response = ""
                if opcode == 0:  # PUT
                    filename_size = byte_info & 0b11111
                    filename = client_socket.recv(filename_size).decode('utf-8')
                    file_size = int.from_bytes(client_socket.recv(4), 'big')
                    response = put_file(client_socket, filename, file_size)
                elif opcode == 1:  # GET
                    filename_size = byte_info & 0b11111
                    filename = client_socket.recv(filename_size).decode('utf-8')
                    response = get_file(client_socket, filename)
                elif opcode == 2:  # CHANGE
                    old_filename_size = byte_info & 0b11111
                    old_filename = client_socket.recv(old_filename_size).decode('utf-8')
                    new_filename_size = int.from_bytes(client_socket.recv(1), 'big')
                    new_filename = client_socket.recv(new_filename_size).decode('utf-8')
                    response = change_name(client_socket, old_filename, new_filename)
                elif opcode == 3:  # SUMMARY
                    filename_size = byte_info & 0b11111
                    filename = client_socket.recv(filename_size).decode('utf-8')
                    response = handle_summary(client_socket, filename)
                elif opcode == 4:  # HELP
                    response, help_text = help_command()
                    client_socket.send(bytes([int(response, 2)]))
                    client_socket.send(help_text.encode('utf-8'))
                    continue
                client_socket.send(bytes([int(response, 2)]))
            except Exception as e:
                if DEBUG:
                    print(f"Error: {e}")
            finally:
                client_socket.close()

if __name__ == "__main__":
    if len(sys.argv) > 2:
        TCP_PORT = int(sys.argv[1])  # This sets TCP_PORT based on command-line argument
        DEBUG = bool(int(sys.argv[2]))
    start_server()