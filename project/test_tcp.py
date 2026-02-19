import socket
s = socket.socket()
s.settimeout(5)
try:
    s.connect(('db', 3306))
    print('CONNECT_OK')
except Exception as e:
    print('CONNECT_FAIL:', e)
finally:
    s.close()