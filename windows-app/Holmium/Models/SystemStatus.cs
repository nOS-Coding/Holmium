namespace Holmium.Models;

public class SystemStatus
{
    public double GpuPercent { get; set; }
    public double RamPercent { get; set; }
    public double DiskPercent { get; set; }
    public string Uptime { get; set; } = "";
}
