import paho.mqtt.client as mqtt
import json
import ssl
import uuid

class MQTTWebSocketClient:
    def __init__(self, host, port, username, password, use_ssl=True, qos=0, clean_session=True, retained=False, use_creds=True):
        """
        Initialize MQTT WebSocket Client
        
        :param host: MQTT broker host
        :param port: MQTT broker port (443 for WSS, 1884 for WS)
        :param username: MQTT broker username
        :param password: MQTT broker password
        :param use_ssl: Whether to use SSL/TLS (True for wss://, False for ws://)
        :param qos: Quality of Service level (0, 1, or 2)
        :param clean_session: Whether to use a clean session (True or False)
        :param retained: Whether messages are retained (True or False)
        """
        
        self.qos = qos
        self.retained = retained
        self.clean_session = clean_session
        
        # Dictionary to store topic values
        self.buttons = ["D1", "D2", "D3", "D4", "online"]
        
        # Use a unique client_id to avoid duplicate connections
        self.client = mqtt.Client(
            client_id="python_websocket_client_" + uuid.uuid4().hex, 
            transport="websockets",
            clean_session=self.clean_session
        )
        
        # Set credentials
        if use_creds:
            self.client.username_pw_set(username, password)
        
        # SSL/TLS Configuration
        if use_ssl:
            self.client.tls_set(
                cert_reqs=ssl.CERT_NONE,
                tls_version=ssl.PROTOCOL_TLS
            )
            self.client.tls_insecure_set(True)
        
        # Set WebSocket Connection Parameters
        self.host = host
        self.port = port
        
        # Callback setup
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_subscribe = self.on_subscribe
        self.client.on_message = self.on_message
    
    def connect(self):
        """
        Establish connection to MQTT broker
        """
        try:
            print(f"Connecting to {self.host}:{self.port}")
            self.client.connect(self.host, self.port, keepalive=60)
            self.client.loop_start()
        except Exception as e:
            print(f"Connection Error: {e}")
    
    def disconnect(self):
        """
        Disconnect from MQTT broker
        """
        self.client.loop_stop()
        self.client.disconnect()
    
    def update_topic_value(self, topic, value):
        """
        Update value of a specific topic
        
        :param topic: Topic to update
        :param value: New value for the topic
        """
        button = topic.split("/")
        if button[1] in self.buttons:
            # Publish updated value back to broker
            self.client.publish(topic, str(value), qos=self.qos, retain=self.retained)
    
    def on_connect(self, client, userdata, flags, rc):
        """
        Connection callback
        
        :param rc: Result code (0 = successful)
        """
        if rc == 0:
            print("Connected successfully")
        else:
            print(f"Connection failed with code {rc}")
    
    def on_disconnect(self, client, userdata, rc):
        """
        Disconnection callback
        """
        print(f"Disconnected with code {rc}")
    
    def on_subscribe(self, client, userdata, mid, granted_qos):
        """
        Subscription callback
        """
        print("Subscribed to topics successfully")
    
    def on_message(self, client, userdata, message):
        """
        Message receive callback
        
        :param message: Received MQTT message
        """
        topic = message.topic
        payload = message.payload.decode('utf-8')
        
        # Validate payload is 0 or 1
        if payload in ['0', '1']:
            print(f"Received on {topic}: {payload}")
    
    def get_topic_values(self):
        """
        Retrieve current topic values as JSON
        
        :return: JSON string of topic values
        """
        return json.dumps(self.topic_values)

    def subscribe_topics(self, token):
        # Topics to subscribe to
        topics = [
            f'{token}/D1',
            f'{token}/D2',
            f'{token}/D3', 
            f'{token}/D4',
            f'{token}/online'
        ]
        for topic in topics:
            self.client.subscribe(topic, qos=self.qos)
            print(f"Subscribed to {topic} with QoS {self.qos}")
   
    def unsubscribe_topics(self, token):
        # Topics to unsubscribe to
        topics = [
            f'{token}/D1',
            f'{token}/D2',
            f'{token}/D3', 
            f'{token}/D4',
            f'{token}/online'
        ]
        for topic in topics:
            self.client.unsubscribe(topic)
            print(f"Unsubscribed to {topic}") 
