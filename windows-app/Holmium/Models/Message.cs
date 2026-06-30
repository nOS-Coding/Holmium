namespace Holmium.Models;

public class Message
{
    public string Role { get; set; } = "user";
    public string Content { get; set; } = "";
    public DateTime Timestamp { get; set; } = DateTime.Now;
    public bool IsUser => Role == "user";
}
