# CyberMind Aviator

A comprehensive patent search and analysis web application built with Flask, JavaScript, and modern web technologies.

## Features

- **Patent Search**: Search through patent databases using various criteria
- **GPS Console**: Real-time GPS tracking and location monitoring
- **Surveillance System**: Advanced monitoring capabilities
- **Manual Control Interface**: Direct control over system functions
- **Alert System**: Real-time notifications and alerts
- **Responsive Design**: Works on desktop and mobile devices

## Technologies Used

- **Backend**: Python Flask
- **Frontend**: HTML, CSS, JavaScript
- **GPS Integration**: Real-time location services
- **Surveillance**: Live monitoring capabilities

## Installation

1. Clone the repository:
```bash
git clone https://github.com/ishyamprasath/cybermind_aviator.git
cd cybermind_aviator
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python app.py
```

4. Open your browser and navigate to `http://localhost:5000`

## Project Structure

```
├── app.py                 # Main Flask application
├── static/
│   ├── css/
│   │   └── style.css      # Styling for the application
│   └── js/
│       ├── main.js        # Core JavaScript functionality
│       ├── gps.js         # GPS tracking functionality
│       ├── joystick.js    # Control interface
│       └── surveillance.js # Monitoring system
└── templates/
    ├── base.html          # Base template
    ├── index.html         # Home page
    ├── gps_console.html   # GPS interface
    ├── surveillance.html  # Monitoring dashboard
    ├── manual_control.html # Control panel
    └── alerts.html        # Alert notifications
```

## Usage

1. **Home Page**: Overview of all system functions
2. **GPS Console**: Monitor real-time location data
3. **Surveillance**: View live camera feeds and monitoring data
4. **Manual Control**: Direct system control interface
5. **Alerts**: View and manage system notifications

## Configuration

The application can be configured through environment variables or by modifying the `app.py` file directly.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is for educational and research purposes.

## Contact

Created by [ishyamprasath](https://github.com/ishyamprasath)
