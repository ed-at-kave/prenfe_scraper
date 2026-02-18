# Systemd Service Setup for RENFE Scraper

## Installation

### 1. Copy service file to systemd directory:
```bash
sudo cp /home/eguiu/betas/Prenfe/infra/systemd/prenfe-scraper.service /etc/systemd/system/
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

The scraper has built-in dynamic scheduling based on Paris Time (CET):
- **05:00-05:59**: Every 5 minutes (low morning traffic)
- **06:00-09:59**: Every 2 minutes (high morning demand)
- **10:00-15:59**: Every 10 minutes (off-peak midday)
- **16:00-18:59**: Every 2 minutes (high evening demand)
- **19:00-23:59**: Every 5 minutes (low evening traffic)
- **00:00-04:59**: Sleep (no queries)

No additional cron jobs needed - scheduling is handled by `get_interval_for_time()` in scraper.py
