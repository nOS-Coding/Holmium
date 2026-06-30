using System.Windows;
using System.Windows.Input;

namespace Holmium.Views;

public partial class MainWindow : Window
{
    public MainWindow()
    {
        InitializeComponent();
    }

    private async void OnTestConnection(object sender, RoutedEventArgs e)
    {
        TestConnectionButton.IsEnabled = false;
        var vm = (ViewModels.MainViewModel)DataContext;
        vm.SetAuthToken(AuthTokenBox.Password);
        await vm.TestConnectionAsync(AuthTokenBox.Password);
        TestConnectionButton.IsEnabled = true;
    }

    protected override void OnClosing(System.ComponentModel.CancelEventArgs e)
    {
        var vm = DataContext as ViewModels.MainViewModel;
        vm?.SaveSettings();
        base.OnClosing(e);
    }
}
