# Systemd Service Setup for RENFE Scraper

## Installation

### 1. Copy service file to systemd directory:
```bash
sudo cp /home/eguiu/betas/Prenfe/prenfe-scraper.service /etc/systemd/system/
```

### 2. Reload systemd daemon:
```bash
sudo systemctl daemon-reload
```

### 3. Enable service to start on boot:
```bash
sudo systemctl enable prenfe-scraper.service
```

### 4. Start the service:
```bash
sudo systemctl start prenfe-scraper.service
```

## Service Management

### Check status:
```bash
sudo systemctl status prenfe-scraper.service
```

### View logs (real-time):
```bash
sudo journalctl -u prenfe-scraper.service -f
```

### View logs (last 100 lines):
```bash
sudo journalctl -u prenfe-scraper.service -n 100
```

### Stop the service:
```bash
sudo systemctl stop prenfe-scraper.service
```

### Restart the service:
```bash
sudo systemctl restart prenfe-scraper.service
```

### Disable from auto-start:
```bash
sudo systemctl disable prenfe-scraper.service
```

### Check if enabled:
```bash
sudo systemctl is-enabled prenfe-scraper.service
```

## Service Configuration

The service file includes:
- **Auto-restart**: Restarts on failure (max 5 times per 60 seconds)
- **Resource limits**: 512MB memory, 50% CPU quota
- **Logging**: All output goes to journalctl
- **Security**: Runs as regular user (eguiu), isolated temp directory
- **Network**: Waits for network connectivity before starting

## Troubleshooting

### Service won't start:
```bash
sudo journalctl -u prenfe-scraper.service -n 50
```

### Check service syntax:
```bash
sudo systemd-analyze verify /etc/systemd/system/prenfe-scraper.service
```

### View service file:
```bash
cat /etc/systemd/system/prenfe-scraper.service
```

## Monitoring

### Watch service in real-time:
```bash
watch -n 1 'sudo systemctl status prenfe-scraper.service'
```

### Check if service is running:
```bash
sudo systemctl is-active prenfe-scraper.service
```

## Scheduling

The scraper has built-in dynamic scheduling:
- **05:50-09:30**: Every 1 minute (peak morning)
- **16:00-18:30**: Every 1 minute (peak evening)
- **09:30-16:00**: Every 10 minutes (daytime)
- **18:30-23:59**: Every 10 minutes (evening)
- **00:00-05:50**: Sleep (no queries)

No additional cron jobs needed!
