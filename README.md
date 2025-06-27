# ?? Anavi Sensor Monitoring Application

## ?? Project Description

This is a robust and visually enhanced desktop application designed for monitoring various environmental sensors connected to a Raspberry Pi. It provides real-time data visualization through customizable gauges and plots, allowing users to track sensor trends, identify anomalies, and manage alert thresholds.  
The application is built using **PyQt5** for the graphical user interface and **Matplotlib** for data plotting, featuring a modular architecture that supports easy expansion with new sensors and themes.

---

## ?? Features

- **Real-time Sensor Monitoring**  
  Displays live data from connected HTU21D (Temperature, Humidity), BMP180 (Temperature, Pressure), and BH1750 (Light) sensors.

- **Customizable Gauges**  
  Supports multiple gauge types (Standard, Compact, Digital, Analog, Progress Bar) and styles (Flat, Shadowed, Raised, Inset, Heavy Border, Clean, Deep Shadow, Outline, Vintage, Subtle, Fresh, Bright, Bold).

- **Detailed Plotting**  
  Dedicated plots for each sensor metric, with a global time range control for historical data.

- **Theming Support**  
  Full QSS (Qt Style Sheet) theming, including pre-configured **Blue** and **Emerald Forest** themes.

- **Modular Architecture**  
  Easily expandable with new sensors and UI elements.

- **Persistent Settings**  
  Settings and sensor configurations are saved and restored.

- **Logging**  
  Comprehensive logging for debugging and monitoring.

---

## ?? User Interface (UI Preview)

> _**Placeholder for screenshots or UI images.**_  
> Add annotated screenshots below to visually represent:
>
> - The main dashboard with gauges  
> - Sensor detail plots  
> - Theming variations  
> - Settings and configuration tabs  

**Example:**
```markdown
![Dashboard View](resources/images/dashboard_sample.png)
![Sensor Details](resources/images/sensor_plot_sample.png)
```

---

## ??? Prerequisites

### ?? Hardware Requirements

- **Raspberry Pi 4 Model B** (recommended)
- **Raspberry Pi OS Bullseye** (64-bit Lite or Desktop)
- **SD Card**: Minimum 16GB (Class 10 or faster)
- **Power Supply**: 5.1V, 3.0A USB-C
- **Internet Connection** (for initial setup)
- **ANAVI Infrared pHAT** with onboard **BH1750 Light Sensor**
- Optional external sensors via I2C: **HTU21D**, **BMP180**

### ?? Software Requirements

- Python 3 (check with `python3 --version`)
- Pip (install: `sudo apt install python3-pip`)
- PyQt5 (install: `sudo apt install python3-pyqt5 python3-pyqt5.qtsvg`)
- Matplotlib (`sudo apt install python3-matplotlib`)
- NumPy (`sudo apt install python3-numpy`)
- smbus2 / I2C tools (`sudo apt install i2c-tools python3-smbus`)
- Pillow (`pip3 install Pillow`)

**Enable I2C**:  
```bash
sudo raspi-config
# Interface Options -> I2C -> Yes
sudo reboot
```

---

## ?? Installation Guide

```bash
# Clone the repository
git clone https://github.com/gr4ytips/Anavi.git
cd InfraredpHAT

# Install dependencies
pip3 install -r requirements.txt
# OR manually:
pip3 install matplotlib numpy smbus2 Pillow
```

**Enable I2C** if not already done:  
```bash
sudo raspi-config
# Interface Options -> I2C -> Yes
sudo reboot
```

**Verify I2C** (optional):
```bash
i2cdetect -y 1
# Expected sensor addresses: 0x40 (HTU21D), 0x77 (BMP180), 0x23 (BH1750)
```

---

## ?? Directory Structure

```
your_project_root/
+-- main.py
+-- ui.py
+-- data_management/
¦   +-- __init__.py
¦   +-- data_store.py
¦   +-- settings.py
¦   +-- logger.py
¦   +-- qss_parser.py
+-- sensors/
¦   +-- __init__.py
¦   +-- mock_sensors.py
¦   +-- sensor_reader.py
¦   +-- (htu21d_sensor.py, bmp180_sensor.py, bh1750_sensor.py)
+-- widgets/
¦   +-- __init__.py
¦   +-- dashboard_tab.py
¦   +-- sensor_details_tab.py
¦   +-- settings_tab.py
¦   +-- about_tab.py
¦   +-- sensor_display.py
¦   +-- matplotlib_widget.py
+-- themes/
¦   +-- blue_theme.qss
¦   +-- emerald_forest_theme.qss
+-- resources/
¦   +-- fonts/
¦   ¦   +-- digital-7.ttf
¦   +-- sounds/
¦   ¦   +-- alert.wav
¦   +-- images/
¦       +-- icon.png
¦       +-- logo.png
+-- config.ini
+-- Sensor_Logs/
+-- Archive_Sensor_Logs/
+-- Debug_Logs/
```

---

## ?? Usage

```bash
python3 main.py
```

The application will launch, displaying tabs for dashboard, sensor details, settings, and more.

---

## ?? Credits

- **Initial Code Generation**: Gemini (Google)
- **Enhancements**: UI and feature development guided by **gr4ytips**

---

## ?? License

This work is licensed under the **Creative Commons Attribution 4.0 International (CC BY 4.0)** license.

[![License: CC BY 4.0](https://img.shields.io/badge/License-CC%20BY%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)

You are free to:
- **Share** — copy and redistribute the material in any medium or format
- **Adapt** — remix, transform, and build upon the material for any purpose, even commercially.

Under the following terms:
- **Attribution** — You must give appropriate credit, provide a link to the license, and indicate if changes were made.

---

## ?? Liability

This software is provided **"as is"**, without any warranty—express or implied. Use at your own risk. The authors and contributors shall not be held liable for any damages or losses arising from its use.

---

## ?? Warning

- Double-check **GPIO/I2C wiring** to avoid hardware damage.
- Use a **stable power supply**.
- Ensure all **software dependencies** are installed.
- Sensor data is **raw and uncalibrated**.
- For **long-term use**, consider backups and watchdogs.

---

## ?? Disclaimer

This application is for **monitoring only**.  
Not for use in **critical or life-sustaining systems**.

---
