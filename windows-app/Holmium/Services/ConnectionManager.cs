using System.Net.WebSockets;
using System.Text;
using System.Text.Json;
using Holmium.Models;

namespace Holmium.Services;

public class ConnectionManager : IDisposable
{
    private ClientWebSocket? _ws;
    private CancellationTokenSource? _cts;
    private Timer? _reconnectTimer;
    private int _reconnectAttempt;
    private bool _disposed;
    private const int MaxReconnectDelay = 30000;

    public ConnectionState State { get; private set; } = ConnectionState.Disconnected;

    public event Action<ConnectionState>? StateChanged;
    public event Action<Message>? MessageReceived;
    public event Action<string>? ErrorOccurred;

    public string ServerUrl { get; set; } = "holmium.local";
    public int ServerPort { get; set; } = 443;
    public string AuthToken { get; set; } = "";

    public async Task ConnectAsync()
    {
        if (_disposed) return;
        await DisconnectAsync();

        SetState(ConnectionState.Connecting);

        try
        {
            var host = ServerUrl;
            if (!host.StartsWith("https://") && !host.StartsWith("http://"))
                host = "https://" + host;
            var wsHost = host.Replace("https://", "wss://").Replace("http://", "ws://");
            var uri = new Uri($"{wsHost}/ws/chat");

            _ws = new ClientWebSocket();
            if (!string.IsNullOrEmpty(AuthToken))
                _ws.Options.SetRequestHeader("X-Holmium-Token", AuthToken);

            _cts = new CancellationTokenSource();
            await _ws.ConnectAsync(uri, _cts.Token);

            _reconnectAttempt = 0;
            SetState(ConnectionState.Connected);
            _ = ReceiveLoopAsync(_cts.Token);
        }
        catch (Exception ex)
        {
            SetState(ConnectionState.Error);
            ErrorOccurred?.Invoke($"Connection failed: {ex.Message}");
            ScheduleReconnect();
        }
    }

    public async Task DisconnectAsync()
    {
        _reconnectTimer?.Dispose();
        _reconnectTimer = null;
        _cts?.Cancel();

        if (_ws?.State == WebSocketState.Open)
        {
            try
            {
                await _ws.CloseAsync(WebSocketCloseStatus.NormalClosure, "Closing", CancellationToken.None);
            }
            catch { }
        }

        _ws?.Dispose();
        _ws = null;
        _cts?.Dispose();
        _cts = null;

        if (State != ConnectionState.Disconnected)
            SetState(ConnectionState.Disconnected);
    }

    public async Task SendMessageAsync(string text)
    {
        if (_ws?.State != WebSocketState.Open) return;

        var payload = JsonSerializer.Serialize(new { message = text, mode = "work" });
        var bytes = Encoding.UTF8.GetBytes(payload);
        await _ws.SendAsync(new ArraySegment<byte>(bytes), WebSocketMessageType.Text, true, CancellationToken.None);
    }

    private async Task ReceiveLoopAsync(CancellationToken ct)
    {
        var buffer = new byte[65536];
        var sb = new StringBuilder();

        try
        {
            while (!ct.IsCancellationRequested && _ws?.State == WebSocketState.Open)
            {
                var result = await _ws.ReceiveAsync(new ArraySegment<byte>(buffer), ct);
                if (result.MessageType == WebSocketMessageType.Close) break;

                var text = Encoding.UTF8.GetString(buffer, 0, result.Count);
                sb.Append(text);

                if (result.EndOfMessage)
                {
                    ProcessMessage(sb.ToString());
                    sb.Clear();
                }
            }
        }
        catch (OperationCanceledException) { }
        catch (Exception ex)
        {
            ErrorOccurred?.Invoke($"Connection lost: {ex.Message}");
        }
        finally
        {
            if (!ct.IsCancellationRequested)
            {
                SetState(ConnectionState.Disconnected);
                ScheduleReconnect();
            }
        }
    }

    private void ProcessMessage(string raw)
    {
        try
        {
            using var doc = JsonDocument.Parse(raw);
            var type = doc.RootElement.GetProperty("type").GetString();

            switch (type)
            {
                case "token":
                    var content = doc.RootElement.GetProperty("content").GetString() ?? "";
                    MessageReceived?.Invoke(new Message { Role = "assistant", Content = content });
                    break;
                case "done":
                    MessageReceived?.Invoke(new Message { Role = "assistant", Content = "" });
                    break;
                case "error":
                    var err = doc.RootElement.GetProperty("content").GetString() ?? "unknown";
                    ErrorOccurred?.Invoke($"Server error: {err}");
                    break;
            }
        }
        catch { }
    }

    private void ScheduleReconnect()
    {
        if (_disposed) return;
        _reconnectTimer?.Dispose();

        var delay = Math.Min(1000 * (1 << _reconnectAttempt), MaxReconnectDelay);
        _reconnectAttempt++;

        _reconnectTimer = new Timer(async _ => await ConnectAsync(), null, delay, Timeout.Infinite);
    }

    private void SetState(ConnectionState state)
    {
        if (State == state) return;
        State = state;
        StateChanged?.Invoke(state);
    }

    public void Dispose()
    {
        _disposed = true;
        _reconnectTimer?.Dispose();
        _cts?.Cancel();
        _cts?.Dispose();
        _ws?.Dispose();
    }
}
