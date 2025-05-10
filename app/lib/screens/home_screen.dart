import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/mqtt_service.dart';
import 'package:intl/intl.dart';
import 'package:fl_chart/fl_chart.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Terrarium Monitor'),
        actions: [
          Consumer<MqttService>(
            builder: (context, mqttService, child) {
              return IconButton(
                icon: Icon(
                  mqttService.isDeviceConnected ? Icons.cloud_done : Icons.cloud_off,
                  color: mqttService.isDeviceConnected ? Colors.green : Colors.red,
                ),
                onPressed: () {
                  if (mqttService.isConnected) {
                    mqttService.disconnect();
                  } else {
                    mqttService.connect();
                  }
                },
              );
            },
          ),
        ],
      ),
      body: Consumer<MqttService>(
        builder: (context, mqttService, child) {
          return Padding(
            padding: const EdgeInsets.all(16.0),
            child: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Connection status
                  Card(
                    child: ListTile(
                      leading: Icon(
                        mqttService.isConnected ? Icons.wifi : Icons.wifi_off,
                        color: mqttService.isConnected ? Colors.green : Colors.red,
                      ),
                      title: Text(
                        mqttService.isConnected
                            ? (mqttService.isDeviceConnected
                            ? 'Connected to ESP32'
                            : 'Connected to broker, but ESP32 is offline')
                            : 'Disconnected',
                        style: TextStyle(
                          color: mqttService.isDeviceConnected ? Colors.green : Colors.red,
                        ),
                      ),
                      trailing: ElevatedButton(
                        onPressed: () {
                          if (mqttService.isConnected) {
                            mqttService.disconnect();
                          } else {
                            mqttService.connect();
                          }
                        },
                        child: Text(mqttService.isConnected ? 'Disconnect' : 'Connect'),
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),

                  // Take Over Mode Switch
                  Card(
                    color: mqttService.data.takeOverMode ? Colors.amber.shade100 : null,
                    child: Padding(
                      padding: const EdgeInsets.all(16.0),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Row(
                            children: [
                              Icon(
                                Icons.touch_app,
                                color: mqttService.data.takeOverMode ? Colors.amber.shade800 : Colors.grey,
                              ),
                              const SizedBox(width: 8),
                              Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  const Text(
                                    'Take Over Mode',
                                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                                  ),
                                  Text(
                                    mqttService.data.takeOverMode
                                        ? 'Manual control enabled'
                                        : 'Automatic control active',
                                    style: TextStyle(
                                      fontSize: 12,
                                      color: mqttService.data.takeOverMode ? Colors.amber.shade800 : Colors.grey,
                                    ),
                                  ),
                                ],
                              ),
                            ],
                          ),
                          Switch(
                            value: mqttService.data.takeOverMode,
                            activeColor: Colors.amber,
                            onChanged: (value) => mqttService.setTakeOverMode(value),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),

                  // Current readings
                  const Text(
                    'Current Readings',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 8),
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(16.0),
                      child: Column(
                        children: [
                          _buildReadingRow(
                            'Temperature',
                            '${mqttService.data.temperature.toStringAsFixed(1)}°C',
                            Icons.thermostat,
                            mqttService.data.temperature < 15 ? Colors.blue :
                            mqttService.data.temperature > 25 ? Colors.red : Colors.green,
                          ),
                          const Divider(),
                          _buildReadingRow(
                            'Humidity',
                            '${mqttService.data.humidity.toStringAsFixed(1)}%',
                            Icons.water_drop,
                            mqttService.data.humidity < 35 ? Colors.orange :
                            mqttService.data.humidity > 65 ? Colors.blue : Colors.green,
                          ),
                          const Divider(),
                          _buildReadingRow(
                            'Food',
                            '${_calculateFoodPercentage(mqttService.data.distance).toStringAsFixed(1)}%',
                            Icons.restaurant,
                            _calculateFoodPercentage(mqttService.data.distance) < 20 ? Colors.red :
                            _calculateFoodPercentage(mqttService.data.distance) < 40 ? Colors.orange : Colors.green,
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),

                  // Controls
                  const Text(
                    'Controls',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 8),
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(16.0),
                      child: Column(
                        children: [
                          _buildSwitchRow(
                            'Heat Lamp',
                            mqttService.data.heaterStatus,
                                (value) => mqttService.toggleHeater(value),
                            Icons.whatshot,
                            Colors.red,
                          ),
                          const Divider(),
                          _buildSwitchRow(
                            'Fan',
                            mqttService.data.fanStatus,
                                (value) => mqttService.toggleFan(value),
                            Icons.air,
                            Colors.lightBlue,
                          ),
                          const Divider(),
                          _buildSwitchRow(
                            'Humidifier',
                            mqttService.data.humidifierStatus,
                                (value) => mqttService.toggleHumidifier(value),
                            Icons.water_drop,
                            Colors.blue,
                          ),
                          const Divider(),
                          _buildSwitchRow(
                            'Food Door',
                            mqttService.data.servoStatus,
                                (value) => mqttService.toggleServo(value),
                            Icons.dining,
                            Colors.purple,
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  // Calculate food percentage based on distance
  double _calculateFoodPercentage(double distance) {
    double percentage = (14 - distance) / 14 * 100;
    // If negative, return 0
    return percentage < 0 ? 0 : percentage;
  }

  Widget _buildReadingRow(String label, String value, IconData icon, Color valueColor) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Row(
          children: [
            Icon(icon),
            const SizedBox(width: 8),
            Text(label),
          ],
        ),
        Text(
          value,
          style: TextStyle(
            fontWeight: FontWeight.bold,
            color: valueColor,
          ),
        ),
      ],
    );
  }

  Widget _buildSwitchRow(String label, bool value, Function(bool) onChanged, IconData icon, Color activeColor) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Row(
          children: [
            Icon(
              icon,
              color: value ? activeColor : Colors.grey,
            ),
            const SizedBox(width: 8),
            Text(
              label,
              style: TextStyle(
                fontWeight: value ? FontWeight.bold : FontWeight.normal,
              ),
            ),
          ],
        ),
        Switch(
          value: value,
          activeColor: activeColor,
          onChanged: onChanged,
        ),
      ],
    );
  }
}