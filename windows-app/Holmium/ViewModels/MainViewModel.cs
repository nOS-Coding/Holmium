using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Runtime.CompilerServices;
using System.Windows.Input;
using Holmium.Models;
using Holmium.Services;

namespace Holmium.ViewModels;

public class MainViewModel : INotifyPropertyChanged
{
    private readonly ConnectionManager _connection;
    private string _inputText = "";
    private string _gpuPercent = "--";
    private string _ramPercent = "--";
    private string _diskPercent = "--";
    private string _uptime = "--";
    private string _serverUrl = "holmium.local";
    private int _serverPort = 443;
    private bool _autoConnect;
    private bool _clipboardSync;
    private bool _notifications = true;
    private bool _startOnBoot;
    private string? _testResult;

    public ObservableCollection<Message> Messages { get; } = new();

    private ConnectionState _connectionState = ConnectionState.Disconnected;
    public ConnectionState ConnectionState
    {
        get => _connectionState;
        set
        {
            _connectionState = value;
            OnPropertyChanged();
            OnPropertyChanged(nameof(StatusText));
            OnPropertyChanged(nameof(StatusColor));
        }
    }

    public string StatusText => ConnectionState switch
    {
        Models.ConnectionState.Connected => "Connected",
        Models.ConnectionState.Connecting => "Connecting...",
        Models.ConnectionState.Error => "Error",
        _ => "Disconnected"
    };

    public string StatusColor => ConnectionState switch
    {
        Models.ConnectionState.Connected => "#4CAF50",
        Models.ConnectionState.Connecting => "#FFC107",
        Models.ConnectionState.Error => "#FF4444",
        _ => "#888888"
    };

    public string InputText
    {
        get => _inputText;
        set { _inputText = value; OnPropertyChanged(); }
    }

    public string GpuPercent
    {
        get => _gpuPercent;
        set { _gpuPercent = value; OnPropertyChanged(); }
    }

    public string RamPercent
    {
        get => _ramPercent;
        set { _ramPercent = value; OnPropertyChanged(); }
    }

    public string DiskPercent
    {
        get => _diskPercent;
        set { _diskPercent = value; OnPropertyChanged(); }
    }

    public string Uptime
    {
        get => _uptime;
        set { _uptime = value; OnPropertyChanged(); }
    }

    public string ServerUrl
    {
        get => _serverUrl;
        set { _serverUrl = value; OnPropertyChanged(); }
    }

    public int ServerPort
    {
        get => _serverPort;
        set { _serverPort = value; OnPropertyChanged(); }
    }

    public bool AutoConnect
    {
        get => _autoConnect;
        set { _autoConnect = value; OnPropertyChanged(); }
    }

    public bool ClipboardSync
    {
        get => _clipboardSync;
        set { _clipboardSync = value; OnPropertyChanged(); }
    }

    public bool Notifications
    {
        get => _notifications;
        set { _notifications = value; OnPropertyChanged(); }
    }

    public bool StartOnBoot
    {
        get => _startOnBoot;
        set { _startOnBoot = value; OnPropertyChanged(); }
    }

    public string? TestResult
    {
        get => _testResult;
        set { _testResult = value; OnPropertyChanged(); }
    }

    public ICommand SendCommand { get; }
    public ICommand ConnectCommand { get; }
    public ICommand DisconnectCommand { get; }
    public ICommand ToggleConnectionCommand { get; }
    public ICommand ScreenshotCommand { get; }
    public ICommand ClipboardSyncCommand { get; }
    public ICommand OpenBrowserCommand { get; }
    public ICommand TestConnectionCommand { get; }
    public ICommand SaveSettingsCommand { get; }

    public MainViewModel()
    {
        _connection = new ConnectionManager();
        _connection.StateChanged += OnStateChanged;
        _connection.MessageReceived += OnMessage;
        _connection.ErrorOccurred += OnError;

        LoadSettings();
        ApplySettings();

        SendCommand = new RelayCommand(async _ => await SendAsync(),
            _ => ConnectionState == Models.ConnectionState.Connected && !string.IsNullOrWhiteSpace(InputText));
        ConnectCommand = new RelayCommand(async _ => await _connection.ConnectAsync());
        DisconnectCommand = new RelayCommand(async _ => await _connection.DisconnectAsync());
        ToggleConnectionCommand = new RelayCommand(async _ =>
        {
            if (ConnectionState == Models.ConnectionState.Connected)
                await _connection.DisconnectAsync();
            else
                await _connection.ConnectAsync();
        });
        ScreenshotCommand = new RelayCommand(async _ => await Task.CompletedTask);
        ClipboardSyncCommand = new RelayCommand(async _ => await Task.CompletedTask);
        OpenBrowserCommand = new RelayCommand(async _ =>
        {
            var url = $"https://{ServerUrl}:{ServerPort}";
            System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo
            {
                FileName = url,
                UseShellExecute = true
            });
            await Task.CompletedTask;
        });
        TestConnectionCommand = new RelayCommand<object>(async param =>
        {
            var token = param as string ?? "";
            await TestConnectionAsync(token);
        });
        SaveSettingsCommand = new RelayCommand(_ => SaveSettings());

        if (AutoConnect)
            _ = _connection.ConnectAsync();
    }

    public void ApplySettings()
    {
        _connection.ServerUrl = ServerUrl;
        _connection.ServerPort = ServerPort;
    }

    public void SetAuthToken(string token)
    {
        _connection.AuthToken = token;
    }

    public async Task TestConnectionAsync(string authToken)
    {
        TestResult = null;
        OnPropertyChanged(nameof(TestResult));

        var oldUrl = _connection.ServerUrl;
        var oldPort = _connection.ServerPort;
        var oldToken = _connection.AuthToken;

        _connection.ServerUrl = ServerUrl;
        _connection.ServerPort = ServerPort;
        _connection.AuthToken = authToken;

        try
        {
            await _connection.DisconnectAsync();
            await _connection.ConnectAsync();
            await Task.Delay(3000);
            var success = _connection.State == Models.ConnectionState.Connected;
            if (success)
            {
                TestResult = "Success";
                await _connection.DisconnectAsync();
            }
            else
            {
                TestResult = "Failed";
            }
        }
        catch
        {
            TestResult = "Failed";
        }

        OnPropertyChanged(nameof(TestResult));

        _connection.ServerUrl = oldUrl;
        _connection.ServerPort = oldPort;
        _connection.AuthToken = oldToken;
    }

    private async Task SendAsync()
    {
        var text = InputText.Trim();
        if (string.IsNullOrEmpty(text)) return;
        InputText = "";
        Messages.Add(new Message { Role = "user", Content = text });
        await _connection.SendMessageAsync(text);
    }

    private void OnStateChanged(ConnectionState state)
    {
        System.Windows.Application.Current.Dispatcher.Invoke(() => ConnectionState = state);
    }

    private void OnMessage(Message msg)
    {
        System.Windows.Application.Current.Dispatcher.Invoke(() =>
        {
            var last = Messages.LastOrDefault();
            if (msg.Role == "assistant" && string.IsNullOrEmpty(msg.Content) && last?.Role == "assistant")
                return;
            if (last?.Role == "assistant" && msg.Role == "assistant" && !string.IsNullOrEmpty(msg.Content))
            {
                var updated = new Message
                {
                    Role = "assistant",
                    Content = last.Content + msg.Content,
                    Timestamp = msg.Timestamp
                };
                Messages[Messages.Count - 1] = updated;
                return;
            }
            Messages.Add(msg);
        });
    }

    private void OnError(string error)
    {
        System.Windows.Application.Current.Dispatcher.Invoke(() =>
            Messages.Add(new Message { Role = "system", Content = $"⚠ {error}" }));
    }

    private void LoadSettings()
    {
        ServerUrl = Properties.Settings.Default.ServerUrl;
        ServerPort = Properties.Settings.Default.ServerPort;
        AutoConnect = Properties.Settings.Default.AutoConnect;
        ClipboardSync = Properties.Settings.Default.ClipboardSync;
        Notifications = Properties.Settings.Default.Notifications;
        StartOnBoot = Properties.Settings.Default.StartOnBoot;
    }

    public void SaveSettings()
    {
        Properties.Settings.Default.ServerUrl = ServerUrl;
        Properties.Settings.Default.ServerPort = ServerPort;
        Properties.Settings.Default.AutoConnect = AutoConnect;
        Properties.Settings.Default.ClipboardSync = ClipboardSync;
        Properties.Settings.Default.Notifications = Notifications;
        Properties.Settings.Default.StartOnBoot = StartOnBoot;
        Properties.Settings.Default.Save();
        ApplySettings();
    }

    public event PropertyChangedEventHandler? PropertyChanged;

    protected void OnPropertyChanged([CallerMemberName] string? name = null)
        => PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(name));
}

public class RelayCommand : ICommand
{
    private readonly Func<object?, Task> _execute;
    private readonly Func<object?, bool>? _canExecute;

    public RelayCommand(Func<object?, Task> execute, Func<object?, bool>? canExecute = null)
    {
        _execute = execute;
        _canExecute = canExecute;
    }

    public bool CanExecute(object? parameter) => _canExecute?.Invoke(parameter) ?? true;

    public event EventHandler? CanExecuteChanged
    {
        add => CommandManager.RequerySuggested += value;
        remove => CommandManager.RequerySuggested -= value;
    }

    public async void Execute(object? parameter) => await _execute(parameter);
}

public class RelayCommand<T> : ICommand
{
    private readonly Func<T?, Task> _execute;
    private readonly Func<T?, bool>? _canExecute;

    public RelayCommand(Func<T?, Task> execute, Func<T?, bool>? canExecute = null)
    {
        _execute = execute;
        _canExecute = canExecute;
    }

    public bool CanExecute(object? parameter) => _canExecute?.Invoke((T?)parameter) ?? true;

    public event EventHandler? CanExecuteChanged
    {
        add => CommandManager.RequerySuggested += value;
        remove => CommandManager.RequerySuggested -= value;
    }

    public async void Execute(object? parameter) => await _execute((T?)parameter);
}
