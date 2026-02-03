# Security Considerations

## Service User Configuration

### Important: Never Run as Root

The gateway service **MUST** run as a non-privileged user for security reasons. Running as root creates significant security vulnerabilities.

### Default Configuration

The service file template (`systemd/lora-osmnotes.service`) uses `User=nobody` as a safe default. However, `nobody` may not have access to serial ports, so the install script automatically detects and sets the correct user.

### Automatic User Detection

The install script (`scripts/install_pi.sh`) automatically detects the appropriate user:

1. Checks for `pi` user (Raspberry Pi OS default)
2. Falls back to `ubuntu` user (Ubuntu Server default)
3. Falls back to current user (`$SUDO_USER` or `$USER`)

### Manual Installation

If installing manually without the install script:

1. **Never leave User=root or User unset**
2. **Always set User= to a non-privileged user**
3. **Ensure the user has access to serial ports** (add to `dialout` group)

Example:
```ini
[Service]
User=your_username  # Replace with actual non-root user
Group=dialout
```

### Verifying Service User

Check what user the service is running as:
```bash
# Check service configuration
sudo systemctl show lora-osmnotes.service | grep User

# Check running process
ps aux | grep gateway.main
```

### Fixing Incorrect User

If the service is running as root or wrong user:

```bash
# Use the fix script
sudo bash scripts/fix_service_user.sh

# Or manually edit
sudo systemctl edit --full lora-osmnotes.service
# Change User= to correct non-root user
sudo systemctl daemon-reload
sudo systemctl restart lora-osmnotes
```

## File Permissions

### Data Directory

The data directory (`/var/lib/lora-osmnotes`) should be owned by the service user:
```bash
sudo chown -R service_user:service_user /var/lib/lora-osmnotes
sudo chmod 700 /var/lib/lora-osmnotes
```

### Environment File

The `.env` file contains configuration and should be readable only by the service user:
```bash
sudo chmod 600 /var/lib/lora-osmnotes/.env
sudo chown service_user:service_user /var/lib/lora-osmnotes/.env
```

### Database File

The SQLite database should be readable/writable only by the service user:
```bash
sudo chmod 600 /var/lib/lora-osmnotes/gateway.db
sudo chown service_user:service_user /var/lib/lora-osmnotes/gateway.db
```

## Serial Port Access

The service user needs access to serial ports. This is typically granted by adding the user to the `dialout` group:

```bash
sudo usermod -a -G dialout service_user
```

**Note:** The user must log out and back in for group changes to take effect, or restart the service.

## Network Security

### Outbound Connections

The gateway makes outbound HTTPS connections to:
- `api.openstreetmap.org` (OSM Notes API)
- `www.google.com` (for Internet connectivity check)

Ensure firewall rules allow these connections.

### No Inbound Connections

The gateway does not listen on any network ports and does not accept inbound connections. It only makes outbound connections.

## Data Privacy

### User Messages

- User messages are stored in the SQLite database
- Messages are sent to OpenStreetMap (public platform)
- **Warning:** Do not send personal data or medical emergencies (as stated in all user messages)

### Logs

Logs may contain:
- Node IDs
- Message content
- GPS coordinates
- Error messages

Ensure log files are properly secured and rotated.

## Best Practices

1. **Always use the install script** - It handles user detection and security configuration automatically
2. **Never run as root** - Always verify the service user is non-privileged
3. **Regular updates** - Keep the system and dependencies updated
4. **Monitor logs** - Regularly check logs for security issues
5. **Backup database** - Regularly backup `/var/lib/lora-osmnotes/gateway.db`
6. **Restrict file permissions** - Use appropriate file permissions for all files
7. **Use DRY_RUN for testing** - Test changes in dry-run mode before production

## Reporting Security Issues

If you discover a security vulnerability, please:
1. Do not open a public issue
2. Contact the maintainers privately
3. Provide detailed information about the vulnerability
