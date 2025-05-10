import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:mqtt_client/mqtt_client.dart';
import 'package:mqtt_client/mqtt_server_client.dart';

class AquariumData {
  double temperature;
  double humidity;
  double distance;
  bool heaterStatus;
  bool humidifierStatus;
  bool fanStatus;        // Added fan status
  bool servoStatus;
  bool takeOverMode;     // Added take over mode
  DateTime timestamp;

  AquariumData({
    this.temperature = 0.0,
    this.humidity = 0.0,
    this.distance = 0.0,
    this.heaterStatus = false,
    this.humidifierStatus = false,
    this.fanStatus = false,     // Initialize fan status
    this.servoStatus = false,
    this.takeOverMode = false,  // Initialize take over mode
    DateTime? timestamp,
  }) : this.timestamp = timestamp ?? DateTime.now();
}

class MqttService extends ChangeNotifier {
  final String broker = 'broker.hivemq.com';
  final int port = 1883;
  final String clientId = 'flutter_aquarium_${DateTime
      .now()
      .millisecondsSinceEpoch}';

  // Updated topic names to match ESP32 code
  final String dataTopic = 'environment/wiredin/data';
  final String controlTopic = 'environment/wiredin/control';

  MqttServerClient? client;
  AquariumData data = AquariumData();
  List<AquariumData> historicalData = []; // For storing historical data
  bool isConnected = false;
  bool isDeviceConnected = false; // Track if ESP32 is online
  DateTime? lastMessageTime; // Track the last message time from ESP32

  // For checking device connection status
  static const deviceTimeoutDuration = Duration(
      minutes: 2); // Consider device offline if no message for 2 minutes

  // Connect to MQTT broker
  Future<void> connect() async {
    client = MqttServerClient(broker, clientId);
    client!.port = port;
    client!.keepAlivePeriod = 60;
    client!.onDisconnected = _onDisconnected;
    client!.onConnected = _onConnected;
    client!.onSubscribed = _onSubscribed;

    final connMess = MqttConnectMessage()
        .withClientIdentifier(clientId)
        .withWillTopic('willtopic')
        .withWillMessage('Will message')
        .startClean()
        .withWillQos(MqttQos.atLeastOnce);
    client!.connectionMessage = connMess;

    try {
      await client!.connect();
    } catch (e) {
      print('Exception: $e');
      client!.disconnect();
    }

    if (client!.connectionStatus!.state == MqttConnectionState.connected) {
      print('Connected to MQTT broker');
      isConnected = true;
      notifyListeners();

      // Subscribe to data topic
      client!.subscribe(dataTopic, MqttQos.atLeastOnce);

      // Set up message handler
      client!.updates!.listen((
          List<MqttReceivedMessage<MqttMessage>> messages) {
        for (var msg in messages) {
          final recMess = msg.payload as MqttPublishMessage;
          final payload = MqttPublishPayload.bytesToStringAsString(
              recMess.payload.message);

          _handleMessage(msg.topic, payload);
        }
      });

      // Start device connection status checker
      _startDeviceConnectionChecker();
    } else {
      print('Connection failed');
      isConnected = false;
      notifyListeners();
    }
  }

  // Handle incoming messages
  void _handleMessage(String topic, String payload) {
    print('Received message: $payload from topic: $topic');

    // Update lastMessageTime whenever we receive a message from the device
    if (topic == dataTopic) {
      lastMessageTime = DateTime.now();
      isDeviceConnected = true;

      try {
        // First try normal JSON parsing
        try {
          final jsonData = json.decode(payload);
          final timestamp = jsonData['timestamp'] != null
              ? DateTime.fromMillisecondsSinceEpoch(
              (jsonData['timestamp'] * 1000).toInt())
              : DateTime.now();

          // Update data with available values
          if (jsonData['temperature'] != null) {
            data.temperature =
                jsonData['temperature']?.toDouble() ?? data.temperature;
          }

          if (jsonData['humidity'] != null) {
            data.humidity = jsonData['humidity']?.toDouble() ?? data.humidity;
          }

          if (jsonData['distance'] != null) {
            data.distance = jsonData['distance']?.toDouble() ?? data.distance;
          }

          data.heaterStatus = jsonData['heat_lamp'] ?? data.heaterStatus;
          data.humidifierStatus =
              jsonData['humidifier'] ?? data.humidifierStatus;
          data.fanStatus = jsonData['fan'] ?? data.fanStatus;
          data.servoStatus = jsonData['servo'] ?? data.servoStatus;
          data.takeOverMode = jsonData['take_over'] ?? data.takeOverMode;
          data.timestamp = timestamp;

          print('Parsed JSON data: Temperature=${data.temperature}, '
              'Humidity=${data.humidity}, Distance=${data.distance}, '
              'Take Over Mode=${data.takeOverMode}');
        } catch (e) {
          print('JSON parse error, trying manual parse: $e');

          // Try manual parsing for format like: "Temp: 25.3°C, Humidity: 45.2%, Distance: 15.7cm"
          if (payload.contains("Temp:") && payload.contains("Humidity:")) {
            try {
              // Extract temperature
              RegExp tempExp = RegExp(r'Temp:\s*(\d+\.?\d*)');
              var tempMatch = tempExp.firstMatch(payload);
              if (tempMatch != null && tempMatch.groupCount >= 1) {
                data.temperature = double.parse(tempMatch.group(1)!);
              }

              // Extract humidity
              RegExp humidExp = RegExp(r'Humidity:\s*(\d+\.?\d*)');
              var humidMatch = humidExp.firstMatch(payload);
              if (humidMatch != null && humidMatch.groupCount >= 1) {
                data.humidity = double.parse(humidMatch.group(1)!);
              }

              // Extract distance if present
              if (payload.contains("Distance:")) {
                RegExp distExp = RegExp(r'Distance:\s*(\d+\.?\d*)');
                var distMatch = distExp.firstMatch(payload);
                if (distMatch != null && distMatch.groupCount >= 1) {
                  data.distance = double.parse(distMatch.group(1)!);
                }
              }

              // Update status based on received data about actuators
              data.heaterStatus = payload.contains("heat_lamp: 1") ||
                  payload.contains("heat_lamp: true");
              data.humidifierStatus = payload.contains("humidifier: 1") ||
                  payload.contains("humidifier: true");
              data.fanStatus =
                  payload.contains("fan: 1") || payload.contains("fan: true");
              data.servoStatus = payload.contains("servo: 1") ||
                  payload.contains("servo: true");
              data.takeOverMode = payload.contains("take_over: 1") ||
                  payload.contains("take_over: true");

              data.timestamp = DateTime.now();

              print('Manually parsed data: Temperature=${data.temperature}, '
                  'Humidity=${data.humidity}, Distance=${data.distance}');
            } catch (e) {
              print('Error in manual parsing: $e');
            }
          }
        }

        // Add to historical data for graphing
        historicalData.add(AquariumData(
          temperature: data.temperature,
          humidity: data.humidity,
          distance: data.distance,
          heaterStatus: data.heaterStatus,
          humidifierStatus: data.humidifierStatus,
          fanStatus: data.fanStatus,
          servoStatus: data.servoStatus,
          takeOverMode: data.takeOverMode,
          timestamp: data.timestamp,
        ));

        // Limit historical data to 24 hours
        final twentyFourHoursAgo = DateTime.now().subtract(Duration(hours: 24));
        historicalData.removeWhere((item) =>
            item.timestamp.isBefore(twentyFourHoursAgo));

        notifyListeners();
      } catch (e) {
        print('Error handling data message: $e');
      }
    }
  }

  // Periodically check if the device is still connected
  void _startDeviceConnectionChecker() {
    Future.delayed(Duration(seconds: 30), () {
      if (isConnected) {
        if (lastMessageTime == null ||
            DateTime.now().difference(lastMessageTime!) >
                deviceTimeoutDuration) {
          isDeviceConnected = false;
          notifyListeners();
        }
        _startDeviceConnectionChecker(); // Schedule next check
      }
    });
  }

  // Send control commands
  void sendCommand(String key, dynamic value) {
    if (client?.connectionStatus?.state == MqttConnectionState.connected) {
      final builder = MqttClientPayloadBuilder();
      builder.addString(json.encode({key: value}));

      client!.publishMessage(
        controlTopic,
        MqttQos.atLeastOnce,
        builder.payload!,
      );
    }
  }

  // Toggle take over mode
  void setTakeOverMode(bool state) {
    sendCommand('take_over', state);
    data.takeOverMode = state;
    notifyListeners();
  }

  // Toggle heater
  void toggleHeater(bool state) {
    // If not in take over mode, enable it automatically
    if (!data.takeOverMode) {
      setTakeOverMode(true);
    }
    sendCommand('heat', state);
    data.heaterStatus = state;
    notifyListeners();
  }

  // Toggle fan
  void toggleFan(bool state) {
    // If not in take over mode, enable it automatically
    if (!data.takeOverMode) {
      setTakeOverMode(true);
    }
    sendCommand('fan', state);
    data.fanStatus = state;
    notifyListeners();
  }

  // Toggle humidifier
  void toggleHumidifier(bool state) {
    // If not in take over mode, enable it automatically
    if (!data.takeOverMode) {
      setTakeOverMode(true);
    }
    sendCommand('humid', state);
    data.humidifierStatus = state;
    notifyListeners();
  }

  // Toggle servo
  void toggleServo(bool state) {
    // If not in take over mode, enable it automatically
    if (!data.takeOverMode) {
      setTakeOverMode(true);
    }
    sendCommand('servo', state);
    data.servoStatus = state;
    notifyListeners();
  }

  // Update temperature thresholds
  void updateTempThreshold(String type, double value) {
    if (type == 'min') {
      sendCommand('temp_lower', value);
    } else if (type == 'max') {
      sendCommand('temp_upper', value);
    }
  }

  // Update humidity thresholds
  void updateHumidityThreshold(String type, double value) {
    if (type == 'min') {
      sendCommand('humid_lower', value);
    } else if (type == 'max') {
      sendCommand('humid_upper', value);
    }
  }

  // Update distance threshold
  void updateDistanceThreshold(double value) {
    sendCommand('distance_threshold', value);
  }

  // Disconnect from broker
  void disconnect() {
    if (client != null && isConnected) {
      client!.disconnect();
    }
  }

  // Callback for successful connection
  void _onConnected() {
    print('Connected to MQTT broker');
    isConnected = true;
    notifyListeners();
  }

  // Callback for disconnection
  void _onDisconnected() {
    print('Disconnected from MQTT broker');
    isConnected = false;
    isDeviceConnected = false;
    notifyListeners();
  }

  // Callback for successful subscription
  void _onSubscribed(String topic) {
    print('Subscribed to topic: $topic');
  }

  @override
  void dispose() {
    disconnect();
    super.dispose();
  }
}