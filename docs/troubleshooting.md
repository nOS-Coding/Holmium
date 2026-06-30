# Troubleshooting

## Common Issues

### "Cannot connect to server" on Android
1. Verify WireGuard is ON (key icon in status bar)
2. Check server IP in Settings: should be `10.0.0.1`
3. Verify auth token matches `/etc/holmium/token` on server
4. Test with `holmium status` from macOS CLI

### "Connection refused" on CLI
1. Is Holmium PC online? `ping 10.0.0.1`
2. Is WireGuard connected? `wg show`
3. Is the backend running? `rc-service holmium-backend status`
4. Check logs: `holmium status -l` or `tail -f /var/log/holmium/holmium.log`

### WireGuard won't connect
1. Verify server is reachable: `ping <server-public-ip>`
2. Check firewall: `iptables -L -n`
3. Verify IP forwarding: `sysctl net.ipv4.ip_forward`
4. Regenerate keys: `./wireguard/register_peers.sh`

### vLLM fails to start
1. Check ROCm: `rocminfo`
2. Verify VRAM: `rocm-smi`
3. Check socket: `ls -la /run/holmium/vllm.sock`
4. Logs at `/var/log/holmium/vllm.log`

### TTS not working (no audio)
1. Check Kokoro model downloaded: `ls /usr/lib/holmium/kokoro/`
2. Test: `curl -X POST -H "X-Holmium-Token: $TOKEN" -d '{"text":"hello"}' http://localhost:8765/tts`
3. Check PulseAudio/PipeWire: `pactl info`
4. Logs at `/var/log/holmium/holmium.log`

### STT returns empty transcript
1. Check Whisper model: `ls /usr/lib/holmium/whisper/`
2. Audio format must be WAV 16kHz mono 16-bit
3. Test with a known good audio file
4. Check GPU memory: `rocm-smi`

### Notifications not arriving on Android
1. Check ntfy topic in Android Settings
2. Verify FCM registration: `POST /register_device`
3. Test: `POST /notify` with `{"title":"test","body":"test"}`
4. Check ntfy.sh WebSocket connection in FcmService logs

### LanceDB errors
1. Verify directory: `ls /var/holmium/memory/lancedb/`
2. Check disk space: `df -h`
3. Embedding model at `/usr/lib/holmium/embeddings/model.onnx`

### "Token invalid" errors
1. Regenerate token: `openssl rand -hex 32 > /etc/holmium/token`
2. Update `~/.netsh/hosts.json` on CLI
3. Update Android Settings with new token

### Performance is slow
1. Check vLLM health: `ls -la /run/holmium/vllm.sock`
2. VRAM pressure: `rocm-smi`
3. CPU load: `htop`
4. Run `holmium benchmark` for diagnostics

## Emergency Recovery

```bash
# Restart all services
rc-service holmium-backend restart
rc-service holmium-vllm restart

# Check all logs
tail -f /var/log/holmium/*.log

# Full system restart
rc-service holmium-backend stop
rc-service holmium-vllm stop
rc-service holmium-wireguard restart
rc-service holmium-vllm start
rc-service holmium-backend start
```
