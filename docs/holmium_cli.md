# holmium CLI — Full Command Reference

## Interactive Shell
```
holmium
```
Opens REPL shell. Prompt: `> ` (right-angle bracket).
Multi-line input, readline history, Ctrl+C to cancel stream, Ctrl+D to exit.

## General Commands

| Command | Description |
|---------|-------------|
| `holmium status` | Dashboard: CPU%, GPU%, RAM, VRAM, uptime, vLLM, WG |
| `holmium status -p` | Ping check only |
| `holmium status -l` | Stream live logs |
| `holmium status -s` | System stats only |
| `holmium send <local> <remote>` | Upload file with progress bar |
| `holmium send <remote> <local>` | Download file |
| `holmium mode <think\|work\|image>` | Switch conversation mode |
| `holmium briefing` | Generate spoken briefing |
| `holmium benchmark` | Full benchmark suite |
| `holmium benchmark --quick` | vLLM + TTS only |
| `holmium benchmark --history` | Past results trend |
| `holmium stats` | Usage statistics today |
| `holmium stats --week` | Weekly summary |
| `holmium stats --history` | History of stats |
| `holmium backup` | Trigger USB backup |
| `holmium update` | Self-update from git |
| `holmium version` | Version info |
| `holmium --help` | Rich table by category |
| `holmium --tools` | Live tool registry |
| `holmium --vault add <key> <value>` | Add vault entry |
| `holmium --vault get <key>` | Read vault entry |
| `holmium --vault list` | List vault keys |
| `holmium --vault delete <key>` | Delete vault entry |
| `holmium --key create <label>` | Generate API key |
| `holmium --key list` | List API keys |
| `holmium --key revoke <label>` | Revoke API key |

## Memory Commands
| Command | Description |
|---------|-------------|
| `holmium -m edit` | Open facts in $EDITOR |
| `holmium -m list` | List all facts |
| `holmium -m forget <key>` | Delete fact |
| `holmium -m search <query>` | Search facts |

## Notes Commands
| Command | Description |
|---------|-------------|
| `holmium -n list` | List notes |
| `holmium -n add "<title>"` | Create note |

## Todo Commands
| Command | Description |
|---------|-------------|
| `holmium -t list` | List todos |
| `holmium -t done "<title>"` | Mark todo done |

## Contacts Commands
| Command | Description |
|---------|-------------|
| `holmium -c list` | List contacts |
| `holmium -c add "<name>" <email>` | Add contact |
| `holmium -c search <query>` | Search contacts |

## Session Commands
| Command | Description |
|---------|-------------|
| `holmium -s list` | List recent sessions |
| `holmium -s show <id>` | View session replay |

## Vision Doc Commands
| Command | Description |
|---------|-------------|
| `holmium -v list` | List vision docs |
| `holmium -v show <slug>` | View vision doc |
| `holmium -v delete <slug>` | Delete vision doc |
| `holmium send vd-<slug>` | Export single vision doc |
| `holmium send vd-all` | Export all as zip |

## Action History
| Command | Description |
|---------|-------------|
| `holmium -a list` | Recent actions |
| `holmium -a search <query>` | Search actions |

## Portfolio Commands
| Command | Description |
|---------|-------------|
| `holmium -f report` | Portfolio report |
| `holmium -f history <ticker>` | Ticker history |

## Image Commands
| Command | Description |
|---------|-------------|
| `holmium -i list` | List generated images |
